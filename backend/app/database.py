import sqlite3
from contextlib import contextmanager

from .config import ARTIFACT_ROOT, DB_PATH, MODEL_STORAGE_ROOT, STORAGE_ROOT, TEMP_ROOT, UPLOAD_ROOT


SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS patients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    gender TEXT NOT NULL,
    age INTEGER NOT NULL,
    status TEXT NOT NULL,
    current_risk TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS patient_modalities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL,
    modality TEXT NOT NULL,
    UNIQUE(patient_id, modality),
    FOREIGN KEY(patient_id) REFERENCES patients(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS app_meta (
    meta_key TEXT PRIMARY KEY,
    meta_value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS models (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    version TEXT NOT NULL,
    status TEXT NOT NULL,
    model_type TEXT NOT NULL,
    file_path TEXT NOT NULL,
    notes TEXT NOT NULL,
    input_dim INTEGER NOT NULL,
    class_count INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS model_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_id INTEGER NOT NULL,
    rule_no INTEGER NOT NULL,
    layer_index INTEGER NOT NULL,
    rule_type TEXT NOT NULL,
    target_class TEXT NOT NULL,
    short_description TEXT NOT NULL,
    detail_title TEXT NOT NULL,
    consequence_label TEXT NOT NULL,
    consequence_p REAL NOT NULL,
    UNIQUE(model_id, layer_index, rule_no),
    FOREIGN KEY(model_id) REFERENCES models(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS model_rule_conditions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_id INTEGER NOT NULL,
    feature_key TEXT NOT NULL,
    feature_label TEXT NOT NULL,
    linguistic_level TEXT NOT NULL,
    a_value REAL NOT NULL,
    sigma_value REAL NOT NULL,
    sort_order INTEGER NOT NULL,
    FOREIGN KEY(rule_id) REFERENCES model_rules(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS diagnosis_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_code TEXT NOT NULL UNIQUE,
    patient_id INTEGER NOT NULL,
    model_id INTEGER NOT NULL,
    status TEXT NOT NULL,
    risk_level TEXT NOT NULL,
    dominant_stage TEXT,
    focus_class TEXT,
    conclusion TEXT NOT NULL,
    summary TEXT NOT NULL,
    advice TEXT NOT NULL,
    metrics_json TEXT,
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    error_message TEXT,
    FOREIGN KEY(patient_id) REFERENCES patients(id) ON DELETE RESTRICT,
    FOREIGN KEY(model_id) REFERENCES models(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS diagnosis_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    file_role TEXT NOT NULL,
    original_name TEXT NOT NULL,
    stored_path TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(run_id) REFERENCES diagnosis_runs(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS diagnosis_stage_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    stage_label TEXT NOT NULL,
    percentage REAL NOT NULL,
    FOREIGN KEY(run_id) REFERENCES diagnosis_runs(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS diagnosis_rule_activations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    model_rule_id INTEGER NOT NULL,
    activation_strength REAL NOT NULL,
    target_class TEXT NOT NULL,
    rank_order INTEGER NOT NULL,
    FOREIGN KEY(run_id) REFERENCES diagnosis_runs(id) ON DELETE CASCADE,
    FOREIGN KEY(model_rule_id) REFERENCES model_rules(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS diagnosis_predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    epoch_index INTEGER NOT NULL,
    sample_index INTEGER NOT NULL,
    time_sec REAL NOT NULL,
    true_label TEXT,
    pred_raw TEXT NOT NULL,
    pred_final TEXT NOT NULL,
    prob_w REAL NOT NULL,
    prob_n1 REAL NOT NULL,
    prob_n2 REAL NOT NULL,
    prob_n3 REAL NOT NULL,
    prob_r REAL NOT NULL,
    FOREIGN KEY(run_id) REFERENCES diagnosis_runs(id) ON DELETE CASCADE
);
"""


def ensure_storage_dirs() -> None:
    for path in (STORAGE_ROOT, UPLOAD_ROOT, MODEL_STORAGE_ROOT, ARTIFACT_ROOT, TEMP_ROOT):
        path.mkdir(parents=True, exist_ok=True)


def get_connection() -> sqlite3.Connection:
    ensure_storage_dirs()
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    # F 盘当前环境下 SQLite 默认 journal 模式会触发 disk I/O error，
    # 切到 MEMORY 模式后可以稳定把数据库保存在项目目录内。
    conn.execute('PRAGMA journal_mode = MEMORY')
    conn.execute('PRAGMA synchronous = NORMAL')
    return conn


@contextmanager
def connection_scope():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with connection_scope() as conn:
        conn.executescript(SCHEMA_SQL)
