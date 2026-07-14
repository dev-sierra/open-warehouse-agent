"""Append-only audit log of every run_query call.

Independent of anything the warehouse itself logs — this is the
project's own record of what the model asked for, so "what did the
agent query last Tuesday" is always answerable without needing
warehouse-side query history access.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class AuditRecord:
    timestamp: float
    sql: str
    row_limit: int
    success: bool
    row_count: int | None = None
    error: str | None = None
    duration_ms: float | None = None


class AuditLog:
    def __init__(self, path: str | Path):
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, entry: AuditRecord) -> None:
        with self._path.open("a") as f:
            f.write(json.dumps(asdict(entry)) + "\n")
