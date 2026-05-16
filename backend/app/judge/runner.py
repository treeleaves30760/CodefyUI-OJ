"""Orchestrates a single judge run.

Two backends:
  - subprocess (dev): runs sandbox/run_judge.py as a Python subprocess on
    the host, with OJ_CDUI_PATH pointing at the cdui repo.
  - docker (prod, Phase 4): runs the sandbox Docker image with
    --network=none, resource limits, and the workspace bind-mounted.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.core.storage import get_submission_dir

logger = logging.getLogger(__name__)


_BACKEND_DIR = Path(__file__).resolve().parents[2]
_SANDBOX_RUNNER = _BACKEND_DIR / "sandbox" / "run_judge.py"


def prepare_workspace(
    submission_id: int,
    submission_graph: dict[str, Any],
    judge_spec: dict[str, Any],
    test_data_source: Path | None,
) -> Path:
    workspace = get_submission_dir(submission_id) / "workspace"
    if workspace.exists():
        shutil.rmtree(workspace)
    workspace.mkdir(parents=True, exist_ok=True)

    (workspace / "submission.json").write_text(
        json.dumps(submission_graph, ensure_ascii=False), encoding="utf-8"
    )
    (workspace / "judge_spec.json").write_text(
        json.dumps(judge_spec, ensure_ascii=False), encoding="utf-8"
    )
    test_dir = workspace / "test_data"
    test_dir.mkdir(exist_ok=True)
    if test_data_source is not None and test_data_source.exists():
        if test_data_source.is_dir():
            for child in test_data_source.iterdir():
                if child.is_file():
                    shutil.copy2(child, test_dir / child.name)
                elif child.is_dir():
                    shutil.copytree(child, test_dir / child.name)
        elif test_data_source.suffix.lower() in {".zip"}:
            import zipfile

            with zipfile.ZipFile(test_data_source) as zf:
                zf.extractall(test_dir)
    return workspace


def run_judge_subprocess(workspace: Path, timeout_seconds: int) -> dict[str, Any]:
    settings = get_settings()
    cdui_backend = (settings.cdui_repo_path / "backend").resolve()

    env = os.environ.copy()
    env["OJ_WORKSPACE"] = str(workspace.resolve())
    env["OJ_CDUI_PATH"] = str(cdui_backend)
    env["PYTHONPATH"] = os.pathsep.join(
        [str(cdui_backend), str(_BACKEND_DIR)] + [env.get("PYTHONPATH", "")]
    )

    try:
        proc = subprocess.run(  # noqa: S603
            [sys.executable, str(_SANDBOX_RUNNER)],
            env=env,
            timeout=timeout_seconds + 30,
            capture_output=True,
            text=True,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {
            "status": "timeout",
            "score": 0.0,
            "log": f"Judge exceeded {timeout_seconds}s timeout",
            "runtime_ms": timeout_seconds * 1000,
        }

    result_file = workspace / "result.json"
    if result_file.exists():
        try:
            return json.loads(result_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            return {
                "status": "error",
                "score": 0.0,
                "log": f"Could not parse result.json: {e}\nstdout: {proc.stdout}\nstderr: {proc.stderr}",
                "runtime_ms": 0,
            }

    return {
        "status": "error",
        "score": 0.0,
        "log": f"Judge produced no result.json. exit={proc.returncode}\n"
               f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}",
        "runtime_ms": 0,
    }


def run_judge(
    submission_id: int,
    submission_graph: dict[str, Any],
    judge_spec: dict[str, Any],
    test_data_source: Path | None,
    timeout_seconds: int = 60,
) -> dict[str, Any]:
    settings = get_settings()
    workspace = prepare_workspace(
        submission_id, submission_graph, judge_spec, test_data_source
    )
    if settings.judge_use_docker:
        return run_judge_docker(workspace, timeout_seconds)
    return run_judge_subprocess(workspace, timeout_seconds)


def run_judge_docker(workspace: Path, timeout_seconds: int) -> dict[str, Any]:
    """Phase 4: run the sandbox Docker image.

    Wires:
      - workspace mounted read-write at /workspace
      - --network=none
      - --cpus=1 --memory=2g
      - --read-only rootfs (workspace is the only writable mount)
    """
    settings = get_settings()
    image = settings.sandbox_image

    cmd = [
        "docker",
        "run",
        "--rm",
        "--network=none",
        "--cpus=1",
        "--memory=2g",
        "--pids-limit=100",
        "--read-only",
        "--tmpfs=/tmp:size=128m",
        "-e",
        "OJ_WORKSPACE=/workspace",
        "-e",
        "OJ_CDUI_PATH=/cdui/backend",
        "-v",
        f"{workspace.resolve()}:/workspace",
        image,
    ]

    try:
        proc = subprocess.run(  # noqa: S603
            cmd,
            timeout=timeout_seconds + 30,
            capture_output=True,
            text=True,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {
            "status": "timeout",
            "score": 0.0,
            "log": f"Sandbox exceeded {timeout_seconds}s timeout",
            "runtime_ms": timeout_seconds * 1000,
        }

    result_file = workspace / "result.json"
    if result_file.exists():
        try:
            return json.loads(result_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            return {
                "status": "error",
                "score": 0.0,
                "log": f"Could not parse result.json: {e}\nstdout: {proc.stdout}\nstderr: {proc.stderr}",
                "runtime_ms": 0,
            }
    return {
        "status": "error",
        "score": 0.0,
        "log": f"Sandbox produced no result.json. exit={proc.returncode}\n"
               f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}",
        "runtime_ms": 0,
    }
