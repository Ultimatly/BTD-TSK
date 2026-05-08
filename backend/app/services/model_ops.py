from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import HTTPException, UploadFile

from ..config import MODEL_STORAGE_ROOT
from ..database import connection_scope
from ..ml.rule_utils import extract_rules_from_model, load_joblib_model
from .common import fetch_one, now_text


ALLOWED_MODEL_STATUSES = {'主模型', '备用模型', '测试模型'}
ALLOWED_MODEL_SUFFIXES = {'.joblib', '.pkl'}


def _normalize_model_status(status: str) -> str:
    clean_status = status.strip()
    if clean_status == '当前启用':
        clean_status = '主模型'
    if clean_status not in ALLOWED_MODEL_STATUSES:
        raise HTTPException(status_code=400, detail='模型状态仅支持“主模型”“备用模型”或“测试模型”。')
    return clean_status


def _normalize_model_fields(
    name: str,
    version: str,
    model_type: str,
    notes: str,
    status: str,
) -> tuple[str, str, str, str, str]:
    clean_name = name.strip()
    clean_version = version.strip()
    clean_type = model_type.strip()
    clean_notes = notes.strip()
    clean_status = _normalize_model_status(status)

    if not clean_name:
        raise HTTPException(status_code=400, detail='请填写模型名称。')
    if not clean_version:
        raise HTTPException(status_code=400, detail='请填写模型版本。')
    if not clean_type:
        raise HTTPException(status_code=400, detail='请填写模型类型。')
    if not clean_notes:
        raise HTTPException(status_code=400, detail='请填写模型说明。')
    return clean_name, clean_version, clean_type, clean_notes, clean_status


def _validate_uploaded_model(model) -> None:
    required_attrs = ['predict_proba', 'compute_rule_activations', 'a', 'sigma', 'beta']
    if not all(hasattr(model, item) for item in required_attrs):
        raise HTTPException(status_code=400, detail='上传文件不是可用的 BTD-TSK 学生模型。')


def _validate_suffix(upload: UploadFile) -> str:
    suffix = Path(upload.filename or '').suffix.lower()
    if suffix not in ALLOWED_MODEL_SUFFIXES:
        raise HTTPException(status_code=400, detail='当前仅支持上传 .joblib 或 .pkl 模型文件。')
    return suffix


def _copy_upload_to_path(upload: UploadFile, target_path: Path) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    upload.file.seek(0)
    with target_path.open('wb') as fout:
        shutil.copyfileobj(upload.file, fout)


def _insert_model_rules(conn, model_id: int, rules: list[dict]) -> None:
    for rule in rules:
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


def save_uploaded_model(
    upload: UploadFile,
    name: str,
    version: str,
    model_type: str,
    notes: str,
    status: str,
) -> dict[str, str]:
    name, version, model_type, notes, status = _normalize_model_fields(
        name,
        version,
        model_type,
        notes,
        status,
    )
    _validate_suffix(upload)

    stamp = now_text().replace('-', '').replace(':', '').replace(' ', '')
    model_code = f'uploaded-btd-tsk-{stamp}'
    target_dir = MODEL_STORAGE_ROOT / model_code
    target_path = target_dir / (upload.filename or f'{model_code}.joblib')
    _copy_upload_to_path(upload, target_path)

    model = load_joblib_model(target_path)
    _validate_uploaded_model(model)
    rules = extract_rules_from_model(model, model_id=-1)
    current_time = now_text()

    with connection_scope() as conn:
        cur = conn.execute(
            """
            INSERT INTO models (model_code, name, version, status, model_type, file_path, notes, input_dim, class_count, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                model_code,
                name,
                version,
                status,
                model_type,
                str(target_path),
                notes,
                int(model.a.shape[1]),
                int(getattr(model, 'num_classes', model.beta.shape[1])),
                current_time,
                current_time,
            ),
        )
        _insert_model_rules(conn, cur.lastrowid, rules)
    return {'modelCode': model_code}


def update_model(
    model_code: str,
    name: str,
    version: str,
    model_type: str,
    notes: str,
    status: str,
    upload: UploadFile | None = None,
) -> dict[str, str]:
    name, version, model_type, notes, status = _normalize_model_fields(
        name,
        version,
        model_type,
        notes,
        status,
    )

    current_time = now_text()
    new_file_path: str | None = None
    new_input_dim: int | None = None
    new_class_count: int | None = None
    new_rules: list[dict] | None = None
    old_file_path: Path | None = None
    final_target_path: Path | None = None
    temp_upload_path: Path | None = None

    with connection_scope() as conn:
        model_row = fetch_one(
            conn,
            'SELECT id, file_path FROM models WHERE model_code = ?',
            (model_code,),
        )
        if not model_row:
            raise HTTPException(status_code=404, detail='未找到模型。')

        old_file_path = Path(model_row['file_path'])

        if upload is not None and upload.filename:
            _validate_suffix(upload)
            target_dir = MODEL_STORAGE_ROOT / model_code
            final_target_path = target_dir / upload.filename
            temp_upload_path = target_dir / f'__updating__{upload.filename}'
            _copy_upload_to_path(upload, temp_upload_path)

            parsed_model = load_joblib_model(temp_upload_path)
            _validate_uploaded_model(parsed_model)
            new_rules = extract_rules_from_model(parsed_model, model_id=-1)
            new_file_path = str(final_target_path)
            new_input_dim = int(parsed_model.a.shape[1])
            new_class_count = int(getattr(parsed_model, 'num_classes', parsed_model.beta.shape[1]))

        if new_rules is not None:
            conn.execute('DELETE FROM model_rules WHERE model_id = ?', (model_row['id'],))

        conn.execute(
            """
            UPDATE models
            SET name = ?, version = ?, status = ?, model_type = ?, notes = ?, file_path = COALESCE(?, file_path),
                input_dim = COALESCE(?, input_dim), class_count = COALESCE(?, class_count), updated_at = ?
            WHERE model_code = ?
            """,
            (
                name,
                version,
                status,
                model_type,
                notes,
                new_file_path,
                new_input_dim,
                new_class_count,
                current_time,
                model_code,
            ),
        )

        if new_rules is not None:
            _insert_model_rules(conn, model_row['id'], new_rules)

    if temp_upload_path and final_target_path:
        if old_file_path and old_file_path.exists() and old_file_path != final_target_path and str(old_file_path).startswith(str(MODEL_STORAGE_ROOT)):
            old_file_path.unlink(missing_ok=True)
        if final_target_path.exists() and final_target_path != temp_upload_path:
            final_target_path.unlink()
        temp_upload_path.replace(final_target_path)

    return {'modelCode': model_code}


def delete_model(model_code: str) -> None:
    with connection_scope() as conn:
        model = fetch_one(conn, 'SELECT id, file_path FROM models WHERE model_code = ?', (model_code,))
        if not model:
            raise HTTPException(status_code=404, detail='未找到模型。')
        ref = fetch_one(conn, 'SELECT COUNT(*) AS c FROM diagnosis_runs WHERE model_id = ?', (model['id'],))
        if ref and ref['c'] > 0:
            raise HTTPException(status_code=409, detail='该模型已被历史诊断记录引用，暂时不能删除。')
        conn.execute('DELETE FROM models WHERE id = ?', (model['id'],))

    file_path = Path(model['file_path'])
    if file_path.exists() and str(file_path).startswith(str(MODEL_STORAGE_ROOT)):
        shutil.rmtree(file_path.parent, ignore_errors=True)
