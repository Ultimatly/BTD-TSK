from __future__ import annotations

import json
import shutil
import threading
from datetime import datetime
from pathlib import Path

from fastapi import HTTPException, UploadFile

from ..config import LEGACY_MODEL_ROOT, MODEL_STORAGE_ROOT, UPLOAD_ROOT, resolve_runtime_path
from ..database import connection_scope
from ..ml.inference import run_diagnosis
from .common import fetch_all, fetch_one, now_text
from .read_api import get_history_artifact_csv_path, get_history_detail, get_history_rules, get_history_waveform


RUN_THREADS: dict[str, threading.Thread] = {}


def create_diagnosis_run(patient_code: str, model_code: str, files: list[UploadFile]) -> dict[str, str]:
    if not files:
        raise HTTPException(status_code=400, detail='请至少上传一组 .dat + .hea 文件，或单个 .edf 文件。')

    now = datetime.now()
    run_code = f"run-{now.strftime('%Y%m%d-%H%M%S')}"
    upload_dir = UPLOAD_ROOT / run_code
    upload_dir.mkdir(parents=True, exist_ok=True)

    file_records = []
    for upload in files:
        if not upload.filename:
            continue
        target_path = upload_dir / upload.filename
        with target_path.open('wb') as fout:
            shutil.copyfileobj(upload.file, fout)
        file_records.append((upload.filename, target_path))

    uploaded_exts = {path.suffix.lower() for _, path in file_records}
    has_edf = '.edf' in uploaded_exts
    has_wfdb_pair = '.dat' in uploaded_exts and '.hea' in uploaded_exts
    if not has_edf and not has_wfdb_pair:
        raise HTTPException(status_code=400, detail='请上传一组 .dat + .hea 文件，或单个 .edf 文件。')

    with connection_scope() as conn:
        patient = fetch_one(conn, 'SELECT id FROM patients WHERE patient_code = ?', (patient_code,))
        model = fetch_one(conn, 'SELECT id, file_path FROM models WHERE model_code = ?', (model_code,))
        if not patient:
            raise HTTPException(status_code=404, detail='未找到患者。')
        if not model:
            raise HTTPException(status_code=404, detail='未找到模型。')
        resolved_model_path = resolve_runtime_path(
            model['file_path'],
            search_roots=(MODEL_STORAGE_ROOT, LEGACY_MODEL_ROOT),
        )
        if not resolved_model_path or not resolved_model_path.exists():
            raise HTTPException(status_code=500, detail='模型文件不存在，无法启动诊断。')
        conn.execute(
            """
            INSERT INTO diagnosis_runs
            (run_code, patient_id, model_id, status, risk_level, dominant_stage, focus_class, conclusion, summary, advice, metrics_json, created_at, started_at, finished_at, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_code,
                patient['id'],
                model['id'],
                'queued',
                '待评估',
                None,
                None,
                '等待诊断开始',
                '等待诊断开始',
                '请上传数据并启动诊断。',
                None,
                now_text(),
                None,
                None,
                None,
            ),
        )
        run = fetch_one(conn, 'SELECT id FROM diagnosis_runs WHERE run_code = ?', (run_code,))
        for filename, path in file_records:
            ext = path.suffix.lower()
            role = f"record_{ext[1:]}"
            conn.execute(
                'INSERT INTO diagnosis_files (run_id, file_role, original_name, stored_path, created_at) VALUES (?, ?, ?, ?, ?)',
                (run['id'], role, filename, str(path), now_text()),
            )

    thread = threading.Thread(
        target=_execute_diagnosis_background,
        args=(run_code, str(resolved_model_path), upload_dir),
        daemon=True,
    )
    RUN_THREADS[run_code] = thread
    thread.start()
    return {'runCode': run_code, 'status': 'queued'}


def _execute_diagnosis_background(run_code: str, model_path: str, upload_dir: Path) -> None:
    with connection_scope() as conn:
        conn.execute(
            'UPDATE diagnosis_runs SET status = ?, started_at = ?, summary = ?, conclusion = ? WHERE run_code = ?',
            ('processing', now_text(), '模型推理中', '模型推理中', run_code),
        )

    try:
        result = run_diagnosis(model_path, upload_dir, run_code)
        with connection_scope() as conn:
            run = fetch_one(conn, 'SELECT id, patient_id, model_id FROM diagnosis_runs WHERE run_code = ?', (run_code,))
            conn.execute(
                """
                UPDATE diagnosis_runs
                SET status=?, risk_level=?, dominant_stage=?, focus_class=?, conclusion=?, summary=?, advice=?, metrics_json=?, finished_at=?, error_message=?
                WHERE run_code=?
                """,
                (
                    'done',
                    result['summary']['risk'],
                    result['summary']['dominant_stage'],
                    result['summary']['focus_class'],
                    result['summary']['conclusion'],
                    result['summary']['summary'],
                    result['summary']['advice'],
                    None if result['metrics'] is None else json.dumps(result['metrics'], ensure_ascii=False),
                    now_text(),
                    None,
                    run_code,
                ),
            )
            conn.execute('DELETE FROM diagnosis_stage_stats WHERE run_id = ?', (run['id'],))
            conn.execute('DELETE FROM diagnosis_rule_activations WHERE run_id = ?', (run['id'],))
            conn.execute('DELETE FROM diagnosis_predictions WHERE run_id = ?', (run['id'],))

            for stage in result['stage_stats']:
                conn.execute(
                    'INSERT INTO diagnosis_stage_stats (run_id, stage_label, percentage) VALUES (?, ?, ?)',
                    (run['id'], stage['label'], stage['value']),
                )

            db_rules = fetch_all(
                conn,
                """
                SELECT mr.id, mr.layer_index, mr.rule_no
                FROM model_rules mr
                WHERE mr.model_id = ?
                """,
                (run['model_id'],),
            )
            db_rule_lookup = {(item['layer_index'], item['rule_no']): item['id'] for item in db_rules}
            for activation in result['rule_activations']:
                rule_id = db_rule_lookup.get((activation['layer_index'], activation['rule_no']))
                if not rule_id:
                    continue
                conn.execute(
                    """
                    INSERT INTO diagnosis_rule_activations (run_id, model_rule_id, activation_strength, target_class, rank_order)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        run['id'],
                        rule_id,
                        activation['activation_strength'],
                        activation['target_class'],
                        activation['rank_order'],
                    ),
                )

            for pred in result['predictions']:
                conn.execute(
                    """
                    INSERT INTO diagnosis_predictions
                    (run_id, epoch_index, sample_index, time_sec, true_label, pred_raw, pred_final, prob_w, prob_n1, prob_n2, prob_n3, prob_r)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run['id'],
                        pred['epoch_index'],
                        pred['sample_index'],
                        pred['time_sec'],
                        pred['true_label'],
                        pred['pred_raw'],
                        pred['pred_final'],
                        pred['prob_w'],
                        pred['prob_n1'],
                        pred['prob_n2'],
                        pred['prob_n3'],
                        pred['prob_r'],
                    ),
                )

            conn.execute(
                'INSERT INTO diagnosis_files (run_id, file_role, original_name, stored_path, created_at) VALUES (?, ?, ?, ?, ?)',
                (run['id'], 'artifact_csv', 'predictions.csv', result['artifact_csv_path'], now_text()),
            )
            conn.execute(
                'UPDATE patients SET status = ?, current_risk = ?, updated_at = ? WHERE id = ?',
                ('已分析', result['summary']['risk'], now_text(), run['patient_id']),
            )
    except Exception as exc:
        with connection_scope() as conn:
            conn.execute(
                'UPDATE diagnosis_runs SET status = ?, error_message = ?, finished_at = ? WHERE run_code = ?',
                ('failed', str(exc), now_text(), run_code),
            )


def get_diagnosis_status(run_code: str) -> dict[str, str | int]:
    with connection_scope() as conn:
        run = fetch_one(conn, 'SELECT status, error_message FROM diagnosis_runs WHERE run_code = ?', (run_code,))
        if not run:
            raise HTTPException(status_code=404, detail='未找到诊断任务。')
    progress = {'queued': 10, 'processing': 60, 'done': 100, 'failed': 100}.get(run['status'], 0)
    message = {
        'queued': '任务已创建，等待执行',
        'processing': '模型推理中',
        'done': '诊断完成',
        'failed': run['error_message'] or '诊断失败',
    }.get(run['status'], '')
    return {'runCode': run_code, 'status': run['status'], 'progress': progress, 'message': message}


def get_diagnosis_result(run_code: str) -> dict:
    return get_history_detail(run_code)


def get_diagnosis_rules(run_code: str) -> list[dict]:
    return get_history_rules(run_code)


def get_diagnosis_waveform(run_code: str) -> dict:
    return get_history_waveform(run_code)


def get_diagnosis_artifact_csv_path(run_code: str) -> Path:
    return get_history_artifact_csv_path(run_code)
