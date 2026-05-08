from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import HTTPException

from ..database import connection_scope
from .common import fetch_all, fetch_one, now_text


def _sync_patient_snapshot(conn, patient_id: int) -> None:
    latest_run = fetch_one(
        conn,
        """
        SELECT status, risk_level
        FROM diagnosis_runs
        WHERE patient_id = ?
        ORDER BY created_at DESC, id DESC
        LIMIT 1
        """,
        (patient_id,),
    )
    if latest_run:
        status = '已分析' if latest_run['status'] == 'done' else '待分析'
        risk = latest_run['risk_level'] or '待评估'
    else:
        status = '待分析'
        risk = '待评估'

    conn.execute(
        'UPDATE patients SET status = ?, current_risk = ?, updated_at = ? WHERE id = ?',
        (status, risk, now_text(), patient_id),
    )


def _collect_run_storage(conn, run_id: int, run_code: str) -> tuple[set[Path], set[Path]]:
    file_rows = fetch_all(
        conn,
        'SELECT stored_path FROM diagnosis_files WHERE run_id = ?',
        (run_id,),
    )

    paths_to_remove: set[Path] = set()
    dirs_to_remove: set[Path] = set()
    for row in file_rows:
        stored_path = Path(row['stored_path'])
        paths_to_remove.add(stored_path)
        parent = stored_path.parent
        if parent.name == run_code:
            dirs_to_remove.add(parent)
    return paths_to_remove, dirs_to_remove


def _cleanup_storage(paths_to_remove: set[Path], dirs_to_remove: set[Path]) -> None:
    for path in sorted(paths_to_remove, key=lambda item: len(str(item)), reverse=True):
        try:
            if path.exists() and path.is_file():
                path.unlink()
        except OSError:
            pass

    for folder in sorted(dirs_to_remove, key=lambda item: len(str(item)), reverse=True):
        try:
            if folder.exists():
                shutil.rmtree(folder, ignore_errors=True)
        except OSError:
            pass


def delete_run_by_id(conn, run_id: int, patient_id: int | None = None, sync_snapshot: bool = True) -> None:
    run = fetch_one(
        conn,
        'SELECT id, run_code, patient_id FROM diagnosis_runs WHERE id = ?',
        (run_id,),
    )
    if not run:
        raise HTTPException(status_code=404, detail='未找到历史记录。')

    paths_to_remove, dirs_to_remove = _collect_run_storage(conn, run['id'], run['run_code'])
    conn.execute('DELETE FROM diagnosis_runs WHERE id = ?', (run['id'],))

    target_patient_id = patient_id if patient_id is not None else run['patient_id']
    if sync_snapshot:
        _sync_patient_snapshot(conn, target_patient_id)

    _cleanup_storage(paths_to_remove, dirs_to_remove)


def delete_history_record(run_code: str) -> dict[str, bool]:
    with connection_scope() as conn:
        run = fetch_one(
            conn,
            'SELECT id, patient_id FROM diagnosis_runs WHERE run_code = ?',
            (run_code,),
        )
        if not run:
            raise HTTPException(status_code=404, detail='未找到历史记录。')

        delete_run_by_id(conn, run['id'], patient_id=run['patient_id'], sync_snapshot=True)

    return {'ok': True}
