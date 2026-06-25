from __future__ import annotations

import sys
from pathlib import Path


def ensure_project_paths() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    ml_python_root = Path(__file__).resolve().parents[1]
    for path in (repo_root, ml_python_root):
        path_text = str(path)
        if path_text not in sys.path:
            sys.path.insert(0, path_text)


def ensure_repo_root_on_path() -> None:
    ensure_project_paths()
