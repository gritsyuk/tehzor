"""JSONL-журнал изменяющих операций MCP: превью, подтверждение, отказ, результат.

Персональные данные (ФИО, телефоны, email) маскируются; api-key в журнал не попадает никогда.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger("tehzor.mcp")

MASK_KEYS = frozenset(
    {
        "name",
        "email",
        "additionalEmail",
        "phone",
        "additionalPhone",
        "ownerName",
        "ownerEmail",
        "ownerPhone",
        "claimerName",
        "fullName",
        "displayName",
    }
)


def mask(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: ("***" if k in MASK_KEYS and v else mask(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [mask(v) for v in value]
    return value


class AuditLog:
    def __init__(self, path: Path) -> None:
        self.path = path

    def write(self, event: str, **data: Any) -> None:
        record = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "event": event, **mask(data)}
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        except OSError as exc:  # журнал не должен ронять сервер, но об отказе нужно знать
            logger.error("tehzor-mcp: не удалось записать журнал аудита %s: %s", self.path, exc)
