#!/usr/bin/env python3
"""Standalone judge script — runs INSIDE the sandbox (Docker container in prod,
host subprocess in dev). Imports cdui's execute_graph by path and runs the
student's graph after patching in hidden test data.

Environment:
    OJ_WORKSPACE   path to workspace dir containing
                     - submission.json
                     - judge_spec.json
                     - test_data/   (hidden inputs)
    OJ_CDUI_PATH   path to cdui's backend directory (where `app/` lives)

Writes: <workspace>/result.json with shape:
    {status, score, log, runtime_ms, extracted_keys: [...]}
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import traceback
from pathlib import Path


def _write_result(workspace: Path, *, status: str, score: float, log: str, runtime_ms: int = 0,
                  extracted_keys: list[str] | None = None) -> None:
    result = {
        "status": status,
        "score": float(score),
        "log": log,
        "runtime_ms": int(runtime_ms),
        "extracted_keys": extracted_keys or [],
    }
    (workspace / "result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def main() -> int:
    workspace = Path(os.environ.get("OJ_WORKSPACE", ".")).resolve()
    cdui_path = Path(os.environ.get("OJ_CDUI_PATH", "")).resolve()

    if not workspace.is_dir():
        print(f"workspace not a dir: {workspace}", file=sys.stderr)
        return 2

    here = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(here))
    from sandbox.patcher import (
        ValidationFailure,
        apply_patches,
        extract_outputs,
        validate_required_nodes,
    )
    from sandbox.scoring import ScoringFailure, compute_score

    submission_path = workspace / "submission.json"
    spec_path = workspace / "judge_spec.json"
    if not submission_path.exists():
        _write_result(workspace, status="error", score=0,
                      log=f"submission.json missing at {submission_path}")
        return 0
    if not spec_path.exists():
        _write_result(workspace, status="error", score=0,
                      log=f"judge_spec.json missing at {spec_path}")
        return 0

    submission = json.loads(submission_path.read_text(encoding="utf-8"))
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    test_data_dir = workspace / "test_data"

    try:
        validate_required_nodes(submission, spec.get("required_node_ids", []))
    except ValidationFailure as e:
        _write_result(workspace, status="invalid", score=0, log=str(e))
        return 0

    try:
        patched = apply_patches(submission, spec, str(test_data_dir))
    except Exception as e:  # noqa: BLE001
        _write_result(workspace, status="error", score=0,
                      log=f"patch failed: {e}\n{traceback.format_exc()}")
        return 0
    (workspace / "patched.json").write_text(
        json.dumps(patched, ensure_ascii=False), encoding="utf-8"
    )

    if not cdui_path.exists():
        _write_result(workspace, status="error", score=0,
                      log=f"OJ_CDUI_PATH does not exist: {cdui_path}")
        return 0

    sys.path.insert(0, str(cdui_path))
    try:
        from app.config import settings as cdui_settings
        from app.core.graph_engine import execute_graph, validate_graph
        from app.core.logging_config import setup_logging
        from app.core.node_registry import registry
        from app.core.preset_registry import preset_registry
    except Exception as e:  # noqa: BLE001
        _write_result(workspace, status="error", score=0,
                      log=f"could not import cdui: {e}\n{traceback.format_exc()}")
        return 0

    setup_logging(level="WARNING")
    try:
        registry.discover(cdui_settings.NODES_DIR, "app.nodes")
        preset_registry.discover(cdui_settings.PRESETS_DIR, registry)
    except Exception as e:  # noqa: BLE001
        _write_result(workspace, status="error", score=0,
                      log=f"cdui registry discover failed: {e}")
        return 0

    nodes = patched.get("nodes", [])
    edges = patched.get("edges", [])

    errs = validate_graph(nodes, edges)
    if errs:
        _write_result(workspace, status="invalid", score=0,
                      log="cdui validation failed:\n" + "\n".join(errs))
        return 0

    t0 = time.time()
    try:
        execution_outputs = asyncio.run(execute_graph(nodes, edges))
    except Exception as e:  # noqa: BLE001
        runtime_ms = int((time.time() - t0) * 1000)
        _write_result(workspace, status="runtime_error", score=0,
                      log=f"execution failed: {e}\n{traceback.format_exc()}",
                      runtime_ms=runtime_ms)
        return 0
    runtime_ms = int((time.time() - t0) * 1000)

    try:
        extracted = extract_outputs(execution_outputs, spec.get("output_reads", []))
    except ValidationFailure as e:
        _write_result(workspace, status="invalid", score=0, log=str(e),
                      runtime_ms=runtime_ms)
        return 0

    try:
        score, score_log = compute_score(extracted, spec["scoring"], str(test_data_dir))
    except (ScoringFailure, KeyError) as e:
        _write_result(workspace, status="error", score=0,
                      log=f"scoring failed: {e}", runtime_ms=runtime_ms)
        return 0

    _write_result(workspace, status="judged", score=score, log=score_log,
                  runtime_ms=runtime_ms, extracted_keys=list(extracted.keys()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
