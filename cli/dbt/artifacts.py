"""Locate and load dbt artifacts (run_results.json + manifest.json)."""
from __future__ import annotations

import json
import os
from pathlib import Path


class DbtArtifactsError(Exception):
    """A user-facing error locating or loading dbt artifacts."""


def resolve_target_dir(target_dir: str | None = None, project_dir: str | None = None) -> Path:
    """Resolve the dbt target directory.

    Order: explicit --target-dir, then DBT_TARGET_PATH env, then <project_dir>/target,
    then ./target.
    """
    if target_dir:
        return Path(target_dir)
    env = os.environ.get("DBT_TARGET_PATH")
    if env:
        return Path(env)
    if project_dir:
        return Path(project_dir) / "target"
    return Path("target")


def load_artifacts(target_dir: Path) -> tuple[dict, dict]:
    """Load run_results.json and manifest.json from target_dir.

    Raises DbtArtifactsError with an actionable message if either is missing
    or unparseable.
    """
    run_results = _load_json(target_dir / "run_results.json", target_dir)
    manifest = _load_json(target_dir / "manifest.json", target_dir)
    return run_results, manifest


def _load_json(path: Path, target_dir: Path) -> dict:
    if not path.exists():
        raise DbtArtifactsError(
            f"Couldn't find dbt artifacts at {target_dir}. "
            "Run `dbt test` (or `dbt build`) first, or pass --target-dir."
        )
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as e:
        raise DbtArtifactsError(f"Could not read {path}: {e}") from e
