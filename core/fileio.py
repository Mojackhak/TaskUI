from __future__ import annotations

import pickle
from datetime import datetime
from pathlib import Path
from typing import Union


PathLike = Union[str, Path]


def ensure_directory(path: PathLike) -> Path:
    folder = Path(path or ".").expanduser()
    try:
        folder.mkdir(parents=True, exist_ok=True)
    except Exception:
        folder = Path(".")
        folder.mkdir(parents=True, exist_ok=True)
    return folder


def timestamp_string(dt: datetime | None = None, fmt: str = "%Y%m%d_%H%M%S") -> str:
    dt = dt or datetime.now()
    return dt.strftime(fmt)


def build_timestamped_path(folder: PathLike, prefix: str, dt: datetime | None = None, suffix: str = "pkl") -> Path:
    folder_path = ensure_directory(folder)
    suffix = suffix.lstrip(".")
    ts = timestamp_string(dt)
    return folder_path / f"{prefix}_{ts}.{suffix}"


def save_pickle(data: object, path: PathLike) -> None:
    with open(Path(path), "wb") as f:
        pickle.dump(data, f)
