from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = Path(__file__).resolve().parents[1]
STORAGE_ROOT = PROJECT_ROOT / 'backend' / 'storage'
DB_PATH = STORAGE_ROOT / 'somnolight_live.db'
UPLOAD_ROOT = STORAGE_ROOT / 'uploads'
MODEL_STORAGE_ROOT = STORAGE_ROOT / 'models'
ARTIFACT_ROOT = STORAGE_ROOT / 'artifacts'
TEMP_ROOT = STORAGE_ROOT / 'temp'

LEGACY_MODEL_ROOT = PROJECT_ROOT / 'models'
LEGACY_RESULT_ROOT = PROJECT_ROOT / 'result'
DATA_ROOT = PROJECT_ROOT / 'data'

API_PREFIX = '/api'
CLASS_LABELS = ['W', 'N1', 'N2', 'N3', 'R']
DEFAULT_CORS_ORIGINS = [
    'http://127.0.0.1:5173',
    'http://localhost:5173',
]


def _map_legacy_path(raw_path: str, marker: str, target_root: Path) -> Path | None:
    normalized = raw_path.replace('\\', '/')
    lowered = normalized.lower()
    marker_lower = marker.lower()
    if marker_lower not in lowered:
        return None
    start = lowered.index(marker_lower) + len(marker_lower)
    suffix = normalized[start:].lstrip('/')
    return target_root / Path(suffix) if suffix else target_root


def resolve_runtime_path(path_value: str | Path | None, *, search_roots: tuple[Path, ...] = ()) -> Path | None:
    if path_value is None:
        return None

    raw_path = str(path_value).strip()
    if not raw_path:
        return None

    direct_path = Path(raw_path)
    if direct_path.exists():
        return direct_path

    candidates: list[Path] = []
    for marker, root in (
        ('/backend/storage/', STORAGE_ROOT),
        ('/models/', LEGACY_MODEL_ROOT),
        ('/result/', LEGACY_RESULT_ROOT),
        ('/data/', DATA_ROOT),
    ):
        mapped = _map_legacy_path(raw_path, marker, root)
        if mapped is not None:
            candidates.append(mapped)

    file_name = Path(raw_path.replace('\\', '/')).name
    if file_name:
        for search_root in search_roots:
            if not search_root.exists():
                continue
            found = next(search_root.rglob(file_name), None)
            if found is not None:
                candidates.append(found)
                break

    for candidate in candidates:
        if candidate.exists():
            return candidate

    return candidates[0] if candidates else direct_path
