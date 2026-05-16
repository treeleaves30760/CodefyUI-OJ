from pathlib import Path

from app.config import get_settings


def get_problem_dir(slug: str) -> Path:
    return get_settings().problem_assets_dir / slug


def get_test_data_dir(slug: str) -> Path:
    return get_settings().test_data_dir / slug


def get_submission_dir(submission_id: int) -> Path:
    return get_settings().submissions_dir / str(submission_id)


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path
