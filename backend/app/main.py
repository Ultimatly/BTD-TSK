from __future__ import annotations

from typing import Annotated

from fastapi import Body, FastAPI, File, Form, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .config import API_PREFIX, DEFAULT_CORS_ORIGINS, STORAGE_ROOT
from .database import init_db
from .services.diagnosis_ops import (
    create_diagnosis_run,
    get_diagnosis_artifact_csv_path,
    get_diagnosis_result,
    get_diagnosis_rules,
    get_diagnosis_status,
    get_diagnosis_waveform,
)
from .services.model_ops import delete_model, save_uploaded_model, update_model
from .services.history_ops import delete_history_record
from .services.patient_ops import create_patient, delete_patient, update_patient
from .services.read_api import (
    get_history_artifact_csv_path,
    get_history_detail,
    get_history_list,
    get_history_overview,
    get_history_rules,
    get_history_waveform,
    get_home_overview,
    get_home_trend,
    get_models,
    get_model_detail,
    get_patient_history,
    get_patients,
    get_recent_runs,
    get_rule_detail,
    get_rules,
)
from .services.seeding import ensure_seeded


class PatientPayload(BaseModel):
    patient_code: str | None = None
    name: str = Field(..., min_length=1)
    gender: str
    age: int = Field(..., ge=1, le=120)


app = FastAPI(title='SomnoLight Backend', version='1.0.0')
app.add_middleware(
    CORSMiddleware,
    allow_origins=DEFAULT_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)
app.mount('/storage', StaticFiles(directory=STORAGE_ROOT), name='storage')


@app.on_event('startup')
def on_startup():
    init_db()
    ensure_seeded()


@app.get('/health')
def health():
    return {'status': 'ok'}


@app.get(f'{API_PREFIX}/home/overview')
def api_home_overview():
    return get_home_overview()


@app.get(f'{API_PREFIX}/home/trend')
def api_home_trend(days: int = Query(7, ge=1, le=90)):
    return get_home_trend(days)


@app.get(f'{API_PREFIX}/home/recent-runs')
def api_home_recent_runs(limit: int = Query(3, ge=1, le=20)):
    return get_recent_runs(limit)


@app.get(f'{API_PREFIX}/patients')
def api_patients():
    return get_patients()


@app.post(f'{API_PREFIX}/patients')
def api_create_patient(payload: PatientPayload = Body(...)):
    return create_patient(payload.model_dump(exclude_none=True))


@app.put(f'{API_PREFIX}/patients/{{patient_code}}')
def api_update_patient(patient_code: str, payload: PatientPayload = Body(...)):
    return update_patient(patient_code, payload.model_dump(exclude_none=True))


@app.delete(f'{API_PREFIX}/patients/{{patient_code}}')
def api_delete_patient(patient_code: str):
    return delete_patient(patient_code)


@app.get(f'{API_PREFIX}/patients/{{patient_code}}/history')
def api_patient_history(patient_code: str):
    return get_patient_history(patient_code)


@app.get(f'{API_PREFIX}/models')
def api_models():
    return get_models()


@app.get(f'{API_PREFIX}/models/{{model_code}}')
def api_model_detail(model_code: str):
    return get_model_detail(model_code)


@app.post(f'{API_PREFIX}/models/upload')
def api_model_upload(
    name: Annotated[str, Form(...)],
    version: Annotated[str, Form(...)],
    status: Annotated[str, Form(...)],
    model_type: Annotated[str, Form(...)],
    notes: str = Form(''),
    file: UploadFile = File(...),
):
    return save_uploaded_model(file, name, version, model_type, notes, status)


@app.put(f'{API_PREFIX}/models/{{model_code}}')
def api_update_model(
    model_code: str,
    name: Annotated[str, Form(...)],
    version: Annotated[str, Form(...)],
    status: Annotated[str, Form(...)],
    model_type: Annotated[str, Form(...)],
    notes: str = Form(''),
    file: UploadFile | None = File(None),
):
    return update_model(model_code, name, version, model_type, notes, status, file)


@app.delete(f'{API_PREFIX}/models/{{model_code}}')
def api_delete_model(model_code: str):
    delete_model(model_code)
    return {'ok': True}


@app.get(f'{API_PREFIX}/rules')
def api_rules(model_code: str | None = Query(None)):
    return get_rules(model_code)


@app.get(f'{API_PREFIX}/rules/{{rule_id}}')
def api_rule_detail(rule_id: int):
    return get_rule_detail(rule_id)


@app.get(f'{API_PREFIX}/history')
def api_history():
    return get_history_list()


@app.delete(f'{API_PREFIX}/history/{{run_code}}')
def api_delete_history(run_code: str):
    return delete_history_record(run_code)


@app.get(f'{API_PREFIX}/history/{{run_code}}/overview')
def api_history_overview(run_code: str):
    return get_history_overview(run_code)


@app.get(f'{API_PREFIX}/history/{{run_code}}/detail')
def api_history_detail(run_code: str):
    return get_history_detail(run_code)


@app.get(f'{API_PREFIX}/history/{{run_code}}/rules')
def api_history_rules(run_code: str):
    return get_history_rules(run_code)


@app.get(f'{API_PREFIX}/history/{{run_code}}/waveform')
def api_history_waveform(run_code: str):
    return get_history_waveform(run_code)


@app.get(f'{API_PREFIX}/history/{{run_code}}/artifact-csv')
def api_history_artifact_csv(run_code: str):
    file_path = get_history_artifact_csv_path(run_code)
    return FileResponse(file_path, media_type='text/csv', filename=file_path.name)


@app.post(f'{API_PREFIX}/diagnosis')
def api_create_diagnosis(
    patient_code: Annotated[str, Form(...)],
    model_code: Annotated[str, Form(...)],
    files: list[UploadFile] = File(...),
):
    return create_diagnosis_run(patient_code, model_code, files)


@app.get(f'{API_PREFIX}/diagnosis/{{run_code}}/status')
def api_diagnosis_status(run_code: str):
    return get_diagnosis_status(run_code)


@app.get(f'{API_PREFIX}/diagnosis/{{run_code}}/result')
def api_diagnosis_result(run_code: str):
    return get_diagnosis_result(run_code)


@app.get(f'{API_PREFIX}/diagnosis/{{run_code}}/rules')
def api_diagnosis_rules(run_code: str):
    return get_diagnosis_rules(run_code)


@app.get(f'{API_PREFIX}/diagnosis/{{run_code}}/waveform')
def api_diagnosis_waveform(run_code: str):
    return get_diagnosis_waveform(run_code)


@app.get(f'{API_PREFIX}/diagnosis/{{run_code}}/artifact-csv')
def api_diagnosis_artifact_csv(run_code: str):
    file_path = get_diagnosis_artifact_csv_path(run_code)
    return FileResponse(file_path, media_type='text/csv', filename=file_path.name)

