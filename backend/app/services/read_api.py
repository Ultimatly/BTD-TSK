from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from ..config import ARTIFACT_ROOT, MODEL_STORAGE_ROOT, UPLOAD_ROOT, resolve_runtime_path
from ..database import connection_scope
from ..ml.inference import extract_rule_activations, extract_waveform_preview, repair_diagnosis_texts
from .common import fetch_all, fetch_one


def _normalize_model_status(status: str) -> str:
    return '主模型' if status == '当前启用' else status


def _resolve_upload_dir(conn, run_id: int) -> Path | None:
    record_files = fetch_all(
        conn,
        'SELECT stored_path FROM diagnosis_files WHERE run_id = ? AND file_role LIKE ? ORDER BY id',
        (run_id, 'record_%'),
    )
    if not record_files:
        return None
    resolved_record = resolve_runtime_path(record_files[0]['stored_path'], search_roots=(UPLOAD_ROOT,))
    if not resolved_record:
        return None
    upload_dir = resolved_record.parent
    return upload_dir if upload_dir.exists() else None


def _store_rebuilt_rule_rows(conn, run_id: int, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    existing = fetch_one(conn, 'SELECT COUNT(*) AS c FROM diagnosis_rule_activations WHERE run_id = ?', (run_id,))
    if existing and existing['c']:
        return
    for row in rows:
        conn.execute(
            """
            INSERT INTO diagnosis_rule_activations (run_id, model_rule_id, activation_strength, target_class, rank_order)
            VALUES (?, ?, ?, ?, ?)
            """,
            (run_id, int(row['id']), float(row['activation_strength']), str(row['target_class']), int(row['rank_order'])),
        )


def _rebuild_rule_rows(conn, run: dict[str, Any]) -> list[dict[str, Any]]:
    upload_dir = _resolve_upload_dir(conn, run['id'])
    if upload_dir is None:
        return []
    model_row = fetch_one(conn, 'SELECT file_path FROM models WHERE id = ?', (run['model_id'],))
    if not model_row:
        return []

    activations = extract_rule_activations(model_row['file_path'], upload_dir)
    if not activations:
        return []

    db_rules = fetch_all(
        conn,
        """
        SELECT mr.id, mr.rule_no, mr.layer_index, mr.rule_type, mr.target_class,
               mr.short_description, mr.detail_title, mr.consequence_label, mr.consequence_p,
               m.model_code
        FROM model_rules mr
        JOIN models m ON m.id = mr.model_id
        WHERE mr.model_id = ?
        ORDER BY mr.layer_index, mr.rule_no
        """,
        (run['model_id'],),
    )
    db_rule_map = {(row['layer_index'], row['rule_no']): row for row in db_rules}

    rows: list[dict[str, Any]] = []
    for activation in activations:
        rule = db_rule_map.get((activation['layer_index'], activation['rule_no']))
        if not rule:
            continue
        merged = dict(rule)
        merged['activation_strength'] = float(activation['activation_strength'])
        merged['rank_order'] = int(activation['rank_order'])
        rows.append(merged)
    return rows


def _load_rule_rows_with_activation(conn, run: dict[str, Any]) -> list[dict[str, Any]]:
    rows = fetch_all(
        conn,
        """
        SELECT mr.id, mr.rule_no, mr.layer_index, mr.rule_type, mr.target_class,
               mr.short_description, mr.detail_title, mr.consequence_label, mr.consequence_p,
               dra.activation_strength, dra.rank_order,
               m.model_code
        FROM diagnosis_rule_activations dra
        JOIN model_rules mr ON mr.id = dra.model_rule_id
        JOIN models m ON m.id = mr.model_id
        WHERE dra.run_id = ?
        ORDER BY dra.rank_order ASC, mr.layer_index ASC, mr.rule_no ASC
        """,
        (run['id'],),
    )
    if rows:
        return rows

    rebuilt_rows = _rebuild_rule_rows(conn, run)
    _store_rebuilt_rule_rows(conn, run['id'], rebuilt_rows)
    return rebuilt_rows


def _load_rule_conditions(conn, rule_ids: list[int]) -> dict[int, list[dict[str, Any]]]:
    if not rule_ids:
        return {}
    placeholders = ','.join('?' for _ in rule_ids)
    rows = fetch_all(
        conn,
        f"""
        SELECT rule_id, feature_key, feature_label, linguistic_level, a_value, sigma_value, sort_order
        FROM model_rule_conditions
        WHERE rule_id IN ({placeholders})
        ORDER BY rule_id, sort_order
        """,
        tuple(rule_ids),
    )
    grouped: dict[int, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(row['rule_id'], []).append(
            {
                'featureKey': row['feature_key'],
                'featureLabel': row['feature_label'],
                'linguisticLevel': row['linguistic_level'],
                'aValue': row['a_value'],
                'sigmaValue': row['sigma_value'],
                'sortOrder': row['sort_order'],
            }
        )
    return grouped


def _build_rule_payload(row: dict[str, Any], conditions: list[dict[str, Any]], model_code: str | None = None) -> dict[str, Any]:
    payload = {
        'id': row['id'],
        'ruleNo': row['rule_no'],
        'layerIndex': row['layer_index'],
        'ruleType': row['rule_type'],
        'targetClass': row['target_class'],
        'shortDescription': row['short_description'],
        'detailTitle': row['detail_title'],
        'consequenceLabel': row['consequence_label'],
        'consequenceP': float(row['consequence_p']),
        'conditions': conditions,
    }
    if 'activation_strength' in row and row['activation_strength'] is not None:
        payload['activationStrength'] = float(row['activation_strength'])
    if 'rank_order' in row and row['rank_order'] is not None:
        payload['rankOrder'] = int(row['rank_order'])
    if model_code is not None:
        payload['modelCode'] = model_code
    return payload


def get_home_overview() -> list[dict[str, Any]]:
    with connection_scope() as conn:
        patient_count = fetch_one(conn, 'SELECT COUNT(*) AS c FROM patients')['c']
        model_count = fetch_one(conn, 'SELECT COUNT(*) AS c FROM models')['c']
        history_count = fetch_one(conn, 'SELECT COUNT(*) AS c FROM diagnosis_runs')['c']
        high_risk_count = fetch_one(
            conn,
            """
            SELECT COUNT(*) AS c
            FROM (
                SELECT r1.patient_id, r1.risk_level
                FROM diagnosis_runs r1
                JOIN (
                    SELECT patient_id, MAX(created_at) AS max_created_at
                    FROM diagnosis_runs
                    GROUP BY patient_id
                ) latest_run
                  ON latest_run.patient_id = r1.patient_id
                 AND latest_run.max_created_at = r1.created_at
            ) latest
            WHERE latest.risk_level = '高风险'
            """,
        )['c']
    return [
        {'label': '患者总数', 'value': str(patient_count), 'note': '当前系统已建档患者数量。', 'icon': 'patients'},
        {'label': '高风险患者数', 'value': str(high_risk_count), 'note': '按每位患者最新一次诊断结果统计高风险人数。', 'icon': 'risk'},
        {'label': '模型数量', 'value': str(model_count), 'note': '当前可用于诊断的已注册模型数量。', 'icon': 'models'},
        {'label': '历史记录数', 'value': str(history_count), 'note': '可回看的历史诊断任务数量。', 'icon': 'history'},
    ]


def get_home_trend(days: int = 7) -> dict[str, Any]:
    with connection_scope() as conn:
        rows = fetch_all(
            conn,
            """
            SELECT substr(created_at, 6, 5) AS label, COUNT(*) AS value
            FROM diagnosis_runs
            WHERE status = 'done'
            GROUP BY substr(created_at, 1, 10)
            ORDER BY substr(created_at, 1, 10) DESC
            LIMIT ?
            """,
            (days,),
        )
    rows = list(reversed(rows))
    total = sum(int(item['value']) for item in rows) if rows else 0
    peak = max(rows, key=lambda item: int(item['value'])) if rows else {'label': '--', 'value': 0}
    return {'total': total, 'peak': peak, 'series': rows}


def get_recent_runs(limit: int = 3) -> list[dict[str, Any]]:
    with connection_scope() as conn:
        rows = fetch_all(
            conn,
            """
            SELECT r.run_code AS historyId, p.patient_code, p.name, substr(r.created_at, 1, 10) AS date,
                   r.risk_level AS risk, r.summary,
                   r.focus_class AS focusClass,
                   r.dominant_stage AS dominantStage
            FROM diagnosis_runs r
            JOIN patients p ON p.id = r.patient_id
            ORDER BY r.created_at DESC
            LIMIT ?
            """,
            (limit,),
        )
    return [
        {
            'historyId': row['historyId'],
            'name': f"{row['patient_code']} · {row['name']}",
            'date': row['date'],
            'risk': row['risk'],
            'summary': row['summary'],
            'focusClass': row['focusClass'],
            'dominantStage': row['dominantStage'],
        }
        for row in rows
    ]


def get_patients() -> list[dict[str, Any]]:
    with connection_scope() as conn:
        rows = fetch_all(
            conn,
            """
            SELECT p.id, p.patient_code, p.name, p.gender, p.age,
                   p.status, p.current_risk, p.created_at, p.updated_at,
                   latest.created_at AS latest_run_at,
                   latest.risk_level AS latest_risk
            FROM patients p
            LEFT JOIN (
                SELECT r1.patient_id, r1.created_at, r1.risk_level
                FROM diagnosis_runs r1
                JOIN (
                    SELECT patient_id, MAX(created_at) AS max_created_at
                    FROM diagnosis_runs
                    GROUP BY patient_id
                ) latest_run
                  ON latest_run.patient_id = r1.patient_id
                 AND latest_run.max_created_at = r1.created_at
            ) latest ON latest.patient_id = p.id
            ORDER BY p.created_at DESC, p.patient_code
            """
        )
        modalities = fetch_all(conn, 'SELECT patient_id, modality FROM patient_modalities ORDER BY id')

    modality_map: dict[int, list[str]] = {}
    for row in modalities:
        modality_map.setdefault(row['patient_id'], []).append(row['modality'])
    return [
        {
            'id': row['patient_code'],
            'name': row['name'],
            'gender': row['gender'],
            'age': row['age'],
            'status': row['status'],
            'risk': row['latest_risk'] or row['current_risk'],
            'modalities': modality_map.get(row['id'], []),
            'latestRunAt': row['latest_run_at'],
            'createdAt': row['created_at'],
            'updatedAt': row['updated_at'],
        }
        for row in rows
    ]


def get_patient_history(patient_code: str) -> list[dict[str, Any]]:
    with connection_scope() as conn:
        patient = fetch_one(conn, 'SELECT id FROM patients WHERE patient_code = ?', (patient_code,))
        if not patient:
            raise HTTPException(status_code=404, detail='未找到该患者。')
        rows = fetch_all(
            conn,
            """
            SELECT r.run_code AS id,
                   substr(r.created_at, 1, 10) AS date,
                   r.created_at,
                   r.finished_at,
                   r.conclusion,
                   r.risk_level AS risk,
                   r.summary,
                   r.focus_class AS focusClass,
                   r.dominant_stage AS dominantStage
            FROM diagnosis_runs r
            WHERE r.patient_id = ?
            ORDER BY r.created_at DESC
            """,
            (patient['id'],),
        )
    return [
        {
            'id': row['id'],
            'date': row['date'],
            'created_at': row['created_at'],
            'finished_at': row['finished_at'],
            'conclusion': row['conclusion'],
            'risk': row['risk'],
            'summary': row['summary'],
            'focusClass': row['focusClass'],
            'dominantStage': row['dominantStage'],
        }
        for row in rows
    ]


def get_models() -> list[dict[str, Any]]:
    with connection_scope() as conn:
        rows = fetch_all(
            conn,
            """
            SELECT *
            FROM models
            ORDER BY
                CASE
                    WHEN status IN ('主模型', '当前启用') THEN 0
                    WHEN status = '备用模型' THEN 1
                    WHEN status = '测试模型' THEN 2
                    ELSE 3
                END,
                updated_at DESC,
                created_at DESC,
                id DESC
            """,
        )
    return [
        {
            'id': row['model_code'],
            'name': row['name'],
            'version': row['version'],
            'status': _normalize_model_status(row['status']),
            'type': row['model_type'],
            'updatedAt': row['updated_at'],
            'notes': row['notes'],
            'inputDim': row['input_dim'],
            'classCount': row['class_count'],
            'uploadFormats': ['.joblib', '.pkl'],
        }
        for row in rows
    ]


def get_model_detail(model_code: str) -> dict[str, Any]:
    with connection_scope() as conn:
        row = fetch_one(conn, 'SELECT * FROM models WHERE model_code = ?', (model_code,))
        if not row:
            raise HTTPException(status_code=404, detail='未找到模型。')
    return {
        'id': row['model_code'],
        'code': row['model_code'],
        'name': row['name'],
        'version': row['version'],
        'status': _normalize_model_status(row['status']),
        'type': row['model_type'],
        'notes': row['notes'],
        'updatedAt': row['updated_at'],
        'inputDim': row['input_dim'],
        'classCount': row['class_count'],
        'uploadFormats': ['.joblib', '.pkl'],
    }


def get_rules(model_code: str | None = None) -> list[dict[str, Any]]:
    with connection_scope() as conn:
        params: tuple[Any, ...] = ()
        sql = """
            SELECT mr.id, mr.rule_no, mr.layer_index, mr.rule_type, mr.target_class,
                   mr.short_description, mr.detail_title, mr.consequence_label, mr.consequence_p,
                   m.model_code
            FROM model_rules mr
            JOIN models m ON m.id = mr.model_id
        """
        if model_code:
            sql += ' WHERE m.model_code = ?'
            params = (model_code,)
        sql += ' ORDER BY m.model_code, mr.layer_index, mr.rule_no'
        rows = fetch_all(conn, sql, params)
        condition_map = _load_rule_conditions(conn, [row['id'] for row in rows])
    return [
        _build_rule_payload(row, condition_map.get(row['id'], []), model_code=row['model_code'])
        for row in rows
    ]


def get_rule_detail(rule_id: int) -> dict[str, Any]:
    with connection_scope() as conn:
        row = fetch_one(
            conn,
            """
            SELECT mr.id, mr.rule_no, mr.layer_index, mr.rule_type, mr.target_class,
                   mr.short_description, mr.detail_title, mr.consequence_label, mr.consequence_p,
                   m.model_code
            FROM model_rules mr
            JOIN models m ON m.id = mr.model_id
            WHERE mr.id = ?
            """,
            (rule_id,),
        )
        if not row:
            raise HTTPException(status_code=404, detail='未找到规则。')
        condition_map = _load_rule_conditions(conn, [rule_id])
    return _build_rule_payload(row, condition_map.get(rule_id, []), model_code=row['model_code'])


def get_history_list() -> list[dict[str, Any]]:
    with connection_scope() as conn:
        rows = fetch_all(
            conn,
            """
            SELECT r.run_code AS id, substr(r.created_at, 1, 10) AS date, p.patient_code, p.name,
                   r.summary, r.conclusion, r.status, r.risk_level AS risk,
                   r.focus_class AS focusClass, r.dominant_stage AS dominantStage, r.advice
            FROM diagnosis_runs r
            JOIN patients p ON p.id = r.patient_id
            ORDER BY r.created_at DESC, r.id DESC
            """
        )
    return [
        {
            'id': row['id'],
            'date': row['date'],
            'title': f"{row['patient_code']} · {row['name']}",
            'summary': row['summary'],
            'conclusion': row['conclusion'],
            'status': row['status'],
            'risk': row['risk'],
            'focusClass': row['focusClass'],
            'dominantStage': row['dominantStage'],
            'advice': row['advice'],
        }
        for row in rows
    ]


def get_history_overview(run_code: str) -> dict[str, Any]:
    with connection_scope() as conn:
        row = fetch_one(
            conn,
            """
            SELECT r.run_code AS id, substr(r.created_at, 1, 10) AS date, p.patient_code, p.name,
                   r.summary, r.conclusion, r.status, r.risk_level AS risk,
                   r.focus_class AS focusClass, r.dominant_stage AS dominantStage, r.advice
            FROM diagnosis_runs r
            JOIN patients p ON p.id = r.patient_id
            WHERE r.run_code = ?
            """,
            (run_code,),
        )
    if not row:
        raise HTTPException(status_code=404, detail='未找到历史记录。')
    return {
        'id': row['id'],
        'date': row['date'],
        'title': f"{row['patient_code']} · {row['name']}",
        'summary': row['summary'],
        'conclusion': row['conclusion'],
        'status': row['status'],
        'risk': row['risk'],
        'focusClass': row['focusClass'],
        'dominantStage': row['dominantStage'],
        'advice': row['advice'],
    }


def get_history_detail(run_code: str) -> dict[str, Any]:
    with connection_scope() as conn:
        run = fetch_one(
            conn,
            """
            SELECT r.id, r.run_code, r.model_id, r.status, r.risk_level, r.dominant_stage, r.focus_class,
                   r.conclusion, r.summary, r.advice, r.metrics_json, r.created_at, r.started_at, r.finished_at,
                   p.patient_code, p.name AS patient_name, p.gender, p.age,
                   m.model_code, m.name AS model_name, m.version AS model_version, m.status AS model_status
            FROM diagnosis_runs r
            JOIN patients p ON p.id = r.patient_id
            JOIN models m ON m.id = r.model_id
            WHERE r.run_code = ?
            """,
            (run_code,),
        )
        if not run:
            raise HTTPException(status_code=404, detail='未找到历史记录。')

        repaired = repair_diagnosis_texts(
            run['risk_level'],
            run['dominant_stage'],
            run['focus_class'],
            run['conclusion'],
            run['summary'],
            run['advice'],
        )
        stage_rows = fetch_all(
            conn,
            'SELECT stage_label, percentage FROM diagnosis_stage_stats WHERE run_id = ? ORDER BY id',
            (run['id'],),
        )
        prediction_rows = fetch_all(
            conn,
            """
            SELECT epoch_index, sample_index, time_sec, true_label, pred_raw, pred_final,
                   prob_w, prob_n1, prob_n2, prob_n3, prob_r
            FROM diagnosis_predictions
            WHERE run_id = ?
            ORDER BY epoch_index
            """,
            (run['id'],),
        )
        rule_rows = _load_rule_rows_with_activation(conn, run)
        condition_map = _load_rule_conditions(conn, [row['id'] for row in rule_rows])
        file_rows = fetch_all(
            conn,
            'SELECT file_role, original_name, stored_path FROM diagnosis_files WHERE run_id = ? ORDER BY id',
            (run['id'],),
        )

    metrics = None
    if run['metrics_json']:
        try:
            metrics = json.loads(run['metrics_json'])
        except json.JSONDecodeError:
            metrics = None

    rules = [_build_rule_payload(row, condition_map.get(row['id'], []), model_code=row['model_code']) for row in rule_rows]
    artifacts = []
    for row in file_rows:
        resolved = resolve_runtime_path(row['stored_path'], search_roots=(UPLOAD_ROOT, MODEL_STORAGE_ROOT, ARTIFACT_ROOT))
        artifacts.append(
            {
                'role': row['file_role'],
                'name': row['original_name'],
                'path': str(resolved or row['stored_path']),
            }
        )

    return {
        'runCode': run['run_code'],
        'status': run['status'],
        'risk': repaired['risk'],
        'dominantStage': repaired['dominant_stage'],
        'focusClass': repaired['focus_class'],
        'conclusion': repaired['conclusion'],
        'summary': repaired['summary'],
        'advice': repaired['advice'],
        'createdAt': run['created_at'],
        'startedAt': run['started_at'],
        'finishedAt': run['finished_at'],
        'metrics': metrics,
        'predictionCount': len(prediction_rows),
        'stageStats': [{'label': row['stage_label'], 'value': float(row['percentage'])} for row in stage_rows],
        'stageTimeline': [
            {
                'epochIndex': row['epoch_index'],
                'sampleIndex': row['sample_index'],
                'timeSec': float(row['time_sec']),
                'stage': row['pred_final'],
                'rawStage': row['pred_raw'],
            }
            for row in prediction_rows
        ],
        'rules': rules,
        'patient': {
            'code': run['patient_code'],
            'name': run['patient_name'],
            'gender': run['gender'],
            'age': run['age'],
        },
        'model': {
            'code': run['model_code'],
            'name': run['model_name'],
            'version': run['model_version'],
            'status': _normalize_model_status(run['model_status']),
        },
        'artifacts': artifacts,
    }


def get_history_rules(run_code: str) -> list[dict[str, Any]]:
    return get_history_detail(run_code)['rules']


def get_history_waveform(run_code: str) -> dict[str, Any]:
    with connection_scope() as conn:
        run = fetch_one(conn, 'SELECT id FROM diagnosis_runs WHERE run_code = ?', (run_code,))
        if not run:
            raise HTTPException(status_code=404, detail='未找到历史记录。')
        upload_dir = _resolve_upload_dir(conn, run['id'])
    if upload_dir is None:
        return {}
    return extract_waveform_preview(upload_dir)


def get_history_artifact_csv_path(run_code: str) -> Path:
    with connection_scope() as conn:
        run = fetch_one(conn, 'SELECT id FROM diagnosis_runs WHERE run_code = ?', (run_code,))
        if not run:
            raise HTTPException(status_code=404, detail='未找到历史记录。')
        file_row = fetch_one(
            conn,
            'SELECT stored_path FROM diagnosis_files WHERE run_id = ? AND file_role = ? ORDER BY id DESC LIMIT 1',
            (run['id'], 'artifact_csv'),
        )
    if not file_row:
        raise HTTPException(status_code=404, detail='当前记录没有可下载的预测结果文件。')
    path = resolve_runtime_path(file_row['stored_path'], search_roots=(ARTIFACT_ROOT,))
    if not path or not path.exists():
        raise HTTPException(status_code=404, detail='预测结果文件不存在。')
    return path
