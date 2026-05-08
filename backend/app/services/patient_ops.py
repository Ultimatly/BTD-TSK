from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import HTTPException

from ..database import connection_scope
from .common import fetch_one, now_text
from .history_ops import delete_run_by_id


def _normalize_modalities(modalities: list[str] | None) -> list[str]:
    valid = {'EEG', 'ECG'}
    cleaned = []
    for item in modalities or ['EEG']:
        text = str(item).strip().upper()
        if text in valid and text not in cleaned:
            cleaned.append(text)
    if not cleaned:
        cleaned.append('EEG')
    return cleaned


def _clean_optional_text(value: Any) -> str:
    if value is None:
        return ''
    text = str(value).strip()
    if text.lower() == 'none':
        return ''
    return text


def _next_patient_code(conn: sqlite3.Connection) -> str:
    row = fetch_one(
        conn,
        """
        SELECT patient_code
        FROM patients
        WHERE patient_code LIKE 'P-%'
        ORDER BY patient_code DESC
        LIMIT 1
        """,
    )
    if not row:
        return 'P-001'
    try:
        number = int(str(row['patient_code']).split('-')[-1])
    except ValueError:
        number = 0
    return f'P-{number + 1:03d}'


def _save_modalities(conn: sqlite3.Connection, patient_id: int, modalities: list[str]) -> None:
    conn.execute('DELETE FROM patient_modalities WHERE patient_id = ?', (patient_id,))
    for modality in modalities:
        conn.execute(
            'INSERT INTO patient_modalities (patient_id, modality) VALUES (?, ?)',
            (patient_id, modality),
        )


def create_patient(payload: dict[str, Any]) -> dict[str, Any]:
    name = str(payload.get('name', '')).strip()
    gender = str(payload.get('gender', '')).strip()
    status = str(payload.get('status', '待分析')).strip() or '待分析'
    risk = str(payload.get('risk', '待评估')).strip() or '待评估'
    patient_code = _clean_optional_text(payload.get('patient_code'))
    modalities = _normalize_modalities(payload.get('modalities'))

    if not name:
        raise HTTPException(status_code=400, detail='患者姓名不能为空。')
    if gender not in {'男', '女'}:
        raise HTTPException(status_code=400, detail='性别必须为“男”或“女”。')

    try:
        age = int(payload.get('age'))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail='年龄必须为有效整数。')
    if age <= 0 or age > 120:
        raise HTTPException(status_code=400, detail='年龄超出合理范围。')

    with connection_scope() as conn:
        if not patient_code:
            patient_code = _next_patient_code(conn)
        exists = fetch_one(conn, 'SELECT id FROM patients WHERE patient_code = ?', (patient_code,))
        if exists:
            raise HTTPException(status_code=400, detail='患者编号已存在。')

        now = now_text()
        conn.execute(
            """
            INSERT INTO patients
            (patient_code, name, gender, age, status, current_risk, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (patient_code, name, gender, age, status, risk, now, now),
        )
        patient = fetch_one(conn, 'SELECT id FROM patients WHERE patient_code = ?', (patient_code,))
        _save_modalities(conn, patient['id'], modalities)

    return {'ok': True, 'id': patient_code}


def update_patient(patient_code: str, payload: dict[str, Any]) -> dict[str, Any]:
    with connection_scope() as conn:
        patient = fetch_one(
            conn,
            'SELECT id, patient_code, name, gender, age, status, current_risk FROM patients WHERE patient_code = ?',
            (patient_code,),
        )
        if not patient:
            raise HTTPException(status_code=404, detail='未找到该患者。')

        name = str(payload.get('name', patient['name'])).strip()
        gender = str(payload.get('gender', patient['gender'])).strip()
        status = str(payload.get('status', patient['status'])).strip() or patient['status']
        risk = str(payload.get('risk', patient['current_risk'])).strip() or patient['current_risk']
        new_code = _clean_optional_text(payload.get('patient_code')) or patient['patient_code']
        modalities = _normalize_modalities(payload.get('modalities'))
        if 'modalities' not in payload:
            modality_rows = conn.execute(
                'SELECT modality FROM patient_modalities WHERE patient_id = ? ORDER BY id',
                (patient['id'],),
            ).fetchall()
            modalities = [row['modality'] for row in modality_rows] or ['EEG']

        if not name:
            raise HTTPException(status_code=400, detail='患者姓名不能为空。')
        if gender not in {'男', '女'}:
            raise HTTPException(status_code=400, detail='性别必须为“男”或“女”。')

        try:
            age = int(payload.get('age', patient['age']))
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail='年龄必须为有效整数。')
        if age <= 0 or age > 120:
            raise HTTPException(status_code=400, detail='年龄超出合理范围。')

        duplicate = fetch_one(
            conn,
            'SELECT id FROM patients WHERE patient_code = ? AND id <> ?',
            (new_code, patient['id']),
        )
        if duplicate:
            raise HTTPException(status_code=400, detail='新的患者编号已存在。')

        conn.execute(
            """
            UPDATE patients
            SET patient_code = ?, name = ?, gender = ?, age = ?, status = ?, current_risk = ?, updated_at = ?
            WHERE id = ?
            """,
            (new_code, name, gender, age, status, risk, now_text(), patient['id']),
        )
        _save_modalities(conn, patient['id'], modalities)

    return {'ok': True, 'id': new_code}


def delete_patient(patient_code: str) -> dict[str, Any]:
    with connection_scope() as conn:
        patient = fetch_one(conn, 'SELECT id FROM patients WHERE patient_code = ?', (patient_code,))
        if not patient:
            raise HTTPException(status_code=404, detail='未找到该患者。')

        run_rows = conn.execute(
            'SELECT id FROM diagnosis_runs WHERE patient_id = ? ORDER BY created_at DESC, id DESC',
            (patient['id'],),
        ).fetchall()

        for row in run_rows:
            delete_run_by_id(conn, row['id'], patient_id=patient['id'], sync_snapshot=False)

        conn.execute('DELETE FROM patient_modalities WHERE patient_id = ?', (patient['id'],))
        conn.execute('DELETE FROM patients WHERE id = ?', (patient['id'],))

    return {'ok': True}
