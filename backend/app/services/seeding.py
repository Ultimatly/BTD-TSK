from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from ..config import LEGACY_MODEL_ROOT
from ..database import connection_scope
from ..ml.rule_utils import extract_rules_from_model, load_joblib_model
from ..seed_data import PATIENT_SEED, SEEDED_HISTORY
from .common import fetch_all, fetch_one, now_text

PATIENT_SEED_META_KEY = 'patients_seeded_v2'
MODEL_SEED_META_KEY = 'models_seeded_v2'
HISTORY_SEED_META_KEY = 'history_seeded_v2'
PATIENT_CODE_REPAIR_META_KEY = 'patient_code_repaired_v1'


def ensure_seeded() -> None:
    with connection_scope() as conn:
        _repair_invalid_patient_codes_once(conn)
        _seed_patients(conn)
        model_rows = _seed_models(conn)
        _seed_history(conn, model_rows)


def _set_meta(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        """
        INSERT INTO app_meta (meta_key, meta_value, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(meta_key) DO UPDATE SET meta_value = excluded.meta_value, updated_at = excluded.updated_at
        """,
        (key, value, now_text()),
    )


def _repair_invalid_patient_codes_once(conn: sqlite3.Connection) -> None:
    repaired_flag = fetch_one(conn, 'SELECT meta_value FROM app_meta WHERE meta_key = ?', (PATIENT_CODE_REPAIR_META_KEY,))
    if repaired_flag:
        return

    invalid_rows = fetch_all(
        conn,
        """
        SELECT id, patient_code
        FROM patients
        WHERE patient_code IS NULL
           OR trim(patient_code) = ''
           OR lower(trim(patient_code)) = 'none'
        ORDER BY id
        """,
    )
    if not invalid_rows:
        _set_meta(conn, PATIENT_CODE_REPAIR_META_KEY, 'true')
        return

    existing_rows = fetch_all(conn, 'SELECT patient_code FROM patients ORDER BY id')
    used_numbers: set[int] = set()
    for row in existing_rows:
        code = str(row['patient_code'] or '').strip()
        if code.startswith('P-'):
            try:
                used_numbers.add(int(code.split('-')[-1]))
            except ValueError:
                continue

    next_number = 1
    for row in invalid_rows:
        while next_number in used_numbers:
            next_number += 1
        new_code = f'P-{next_number:03d}'
        conn.execute(
            'UPDATE patients SET patient_code = ?, updated_at = ? WHERE id = ?',
            (new_code, now_text(), row['id']),
        )
        used_numbers.add(next_number)
        next_number += 1

    _set_meta(conn, PATIENT_CODE_REPAIR_META_KEY, 'true')


def _seed_patients(conn: sqlite3.Connection) -> None:
    seeded_flag = fetch_one(conn, 'SELECT meta_value FROM app_meta WHERE meta_key = ?', (PATIENT_SEED_META_KEY,))
    if seeded_flag:
        return

    if fetch_one(conn, 'SELECT id FROM patients LIMIT 1'):
        _set_meta(conn, PATIENT_SEED_META_KEY, 'true')
        return

    for item in PATIENT_SEED:
        current_time = now_text()
        cur = conn.execute(
            """
            INSERT INTO patients (patient_code, name, gender, age, status, current_risk, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item['patient_code'],
                item['name'],
                item['gender'],
                item['age'],
                item['status'],
                item['current_risk'],
                current_time,
                current_time,
            ),
        )
        patient_id = cur.lastrowid
        for modality in item['modalities']:
            conn.execute(
                'INSERT OR IGNORE INTO patient_modalities (patient_id, modality) VALUES (?, ?)',
                (patient_id, modality),
            )

    _set_meta(conn, PATIENT_SEED_META_KEY, 'true')


def _get_existing_models(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return fetch_all(conn, 'SELECT * FROM models ORDER BY created_at, id')


def _build_model_metadata(model_file: Path) -> dict[str, Any]:
    model = load_joblib_model(model_file)
    file_stem = model_file.stem
    dataset_name = file_stem.split('_')[-1]
    rules = extract_rules_from_model(model, model_id=-1)
    return {
        'model_code': file_stem,
        'name': f'BTD-TSK {dataset_name}',
        'version': 'v1.0.0',
        'status': '主模型' if dataset_name == 'Data-A' else '备用模型',
        'model_type': 'BiLSTM教师蒸馏零阶TSK',
        'file_path': str(model_file.resolve()),
        'notes': f'当前保留的最终蒸馏学生模型，来源于 {dataset_name} 数据分组训练结果。',
        'input_dim': int(model.a.shape[1]),
        'class_count': int(getattr(model, 'num_classes', model.beta.shape[1])),
        'rules': rules,
    }


def _seed_models(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    seeded_flag = fetch_one(conn, 'SELECT meta_value FROM app_meta WHERE meta_key = ?', (MODEL_SEED_META_KEY,))
    if seeded_flag:
        return _get_existing_models(conn)

    existing_models = _get_existing_models(conn)
    if existing_models:
        _set_meta(conn, MODEL_SEED_META_KEY, 'true')
        return existing_models

    model_rows: list[dict[str, Any]] = []
    for model_file in sorted(LEGACY_MODEL_ROOT.glob('btd_tsk_student_Data-*.joblib')):
        metadata = _build_model_metadata(model_file)
        current_time = now_text()
        cur = conn.execute(
            """
            INSERT INTO models (model_code, name, version, status, model_type, file_path, notes, input_dim, class_count, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                metadata['model_code'],
                metadata['name'],
                metadata['version'],
                metadata['status'],
                metadata['model_type'],
                metadata['file_path'],
                metadata['notes'],
                metadata['input_dim'],
                metadata['class_count'],
                current_time,
                current_time,
            ),
        )
        model_id = cur.lastrowid
        for rule in metadata['rules']:
            rule_cur = conn.execute(
                """
                INSERT INTO model_rules
                (model_id, rule_no, layer_index, rule_type, target_class, short_description, detail_title, consequence_label, consequence_p)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    model_id,
                    rule['rule_no'],
                    rule['layer_index'],
                    rule['rule_type'],
                    rule['target_class'],
                    rule['short_description'],
                    rule['detail_title'],
                    rule['consequence_label'],
                    rule['consequence_p'],
                ),
            )
            rule_id = rule_cur.lastrowid
            for condition in rule['conditions']:
                conn.execute(
                    """
                    INSERT INTO model_rule_conditions
                    (rule_id, feature_key, feature_label, linguistic_level, a_value, sigma_value, sort_order)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        rule_id,
                        condition['feature_key'],
                        condition['feature_label'],
                        condition['linguistic_level'],
                        condition['a_value'],
                        condition['sigma_value'],
                        condition['sort_order'],
                    ),
                )
        model_rows.append(fetch_one(conn, 'SELECT * FROM models WHERE id = ?', (model_id,)))

    _set_meta(conn, MODEL_SEED_META_KEY, 'true')
    return model_rows


def _seed_history(conn: sqlite3.Connection, model_rows: list[dict[str, Any]]) -> None:
    seeded_flag = fetch_one(conn, 'SELECT meta_value FROM app_meta WHERE meta_key = ?', (HISTORY_SEED_META_KEY,))
    if seeded_flag:
        return

    if fetch_one(conn, 'SELECT id FROM diagnosis_runs LIMIT 1'):
        _set_meta(conn, HISTORY_SEED_META_KEY, 'true')
        return

    if not model_rows or not fetch_one(conn, 'SELECT id FROM patients LIMIT 1'):
        _set_meta(conn, HISTORY_SEED_META_KEY, 'true')
        return

    model_by_code = {item['model_code']: item for item in model_rows}
    patient_by_code = {item['patient_code']: item for item in fetch_all(conn, 'SELECT id, patient_code FROM patients')}

    for item in SEEDED_HISTORY:
        patient = patient_by_code[item['patient_code']]
        model = model_by_code.get(item['model_code']) or model_rows[0]
        cur = conn.execute(
            """
            INSERT INTO diagnosis_runs
            (run_code, patient_id, model_id, status, risk_level, dominant_stage, focus_class, conclusion, summary, advice, metrics_json, created_at, started_at, finished_at, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item['run_code'],
                patient['id'],
                model['id'],
                item['status'],
                item['risk_level'],
                item['dominant_stage'],
                item['focus_class'],
                item['conclusion'],
                item['summary'],
                item['advice'],
                None,
                item['created_at'],
                item['created_at'],
                item['finished_at'],
                None,
            ),
        )
        run_id = cur.lastrowid
        for label, percentage in item['stage_stats'].items():
            conn.execute(
                'INSERT INTO diagnosis_stage_stats (run_id, stage_label, percentage) VALUES (?, ?, ?)',
                (run_id, label, float(percentage)),
            )

        available_rules = fetch_all(
            conn,
            'SELECT id, layer_index, rule_no, target_class FROM model_rules WHERE model_id = ? ORDER BY rule_no',
            (model['id'],),
        )
        lookup = {(row['layer_index'], row['rule_no']): row for row in available_rules}
        for rank_order, ref in enumerate(item['rule_refs'], start=1):
            row = lookup.get(tuple(ref))
            if not row:
                continue
            conn.execute(
                """
                INSERT INTO diagnosis_rule_activations (run_id, model_rule_id, activation_strength, target_class, rank_order)
                VALUES (?, ?, ?, ?, ?)
                """,
                (run_id, row['id'], 0.75 - (rank_order - 1) * 0.08, row['target_class'], rank_order),
            )

    _set_meta(conn, HISTORY_SEED_META_KEY, 'true')
