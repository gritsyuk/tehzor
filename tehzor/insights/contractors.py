"""Организация исполнителя по его должности — только для группировки в сводках.

fact (2026-11-05): должность имеет вид «Должность, Организация», «Генподряд, ООО "…"» или «ООО "…"»;
кавычки бывают ” “ « » ", встречаются неразрывные пробелы и варианты с правовой формой и без неё
(«МС Строй» и «ООО «МС Строй»»). Должность без организации («Инженер гарантийного отдела») → None.
"""

from __future__ import annotations

import re

LEGAL_FORMS = r"(?:ООО|ОАО|ЗАО|ПАО|НАО|АО|ИП|ГУП|МУП|ФГУП|ГКУ|ГБУ)"
_LEGAL = re.compile(rf"(?<![\w]){LEGAL_FORMS}(?![\w])")
_QUOTES = str.maketrans({"”": '"', "“": '"', "„": '"', "«": '"', "»": '"', "'": '"', " ": " "})


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text.translate(_QUOTES)).strip(" ,;")


def contractor_from_position(position: str | None) -> tuple[str, str] | None:
    """(название для показа, ключ для группировки) или None, если организации в должности нет."""
    if not position:
        return None
    text = _clean(position)
    parts = [p.strip() for p in text.split(",") if p.strip()]
    if not parts:
        return None
    candidate = next((p for p in reversed(parts) if _LEGAL.search(p)), None)
    if candidate is None:
        if len(parts) < 2:
            return None
        candidate = parts[-1]
    key = _LEGAL.sub(" ", candidate).replace('"', " ")
    key = re.sub(r"\s+", " ", key).strip().casefold()
    if not key:
        return None
    return candidate, key
