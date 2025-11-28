from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Mapping

import pickle

from PyQt5 import QtGui, QtWidgets


def translate(translations: Mapping[str, Mapping[str, str]], language: str, key: str, fallback_language: str = "en") -> str:
    """Return a localized string from either lang-first or key-first translation maps."""
    lang_map = translations.get(language)
    if isinstance(lang_map, Mapping):
        return lang_map.get(key, key)

    entry = translations.get(key)
    if isinstance(entry, Mapping):
        if language in entry:
            return entry[language]
        if fallback_language in entry:
            return entry[fallback_language]
        return next(iter(entry.values()), key)

    if fallback_language in translations and isinstance(translations[fallback_language], Mapping):
        return translations[fallback_language].get(key, key)
    return key


def get_app_icon(icon_path: Path) -> QtGui.QIcon:
    if icon_path.exists():
        return QtGui.QIcon(str(icon_path))
    return QtGui.QIcon()


def set_groupbox_title_font(groupbox: QtWidgets.QGroupBox, point_size: int = 12) -> None:
    font = groupbox.font()
    font.setPointSize(point_size)
    font.setBold(True)
    groupbox.setFont(font)


def load_pickle(path: str | Path) -> Any:
    """Load and return the object stored in a pickle file at the given path."""
    with open(Path(path), "rb") as f:
        return pickle.load(f)
