"""Deterministic comparison for immutable purchase-order snapshots."""

from __future__ import annotations

from typing import Any

from ..models import OrderVersion
from ..schemas import VersionChange, VersionDiffResponse
from .orders import version_response


def _path(prefix: str, segment: str) -> str:
    return f"{prefix}.{segment}" if prefix else segment


def _diff_values(before: Any, after: Any, path: str, changes: list[VersionChange]) -> None:
    if isinstance(before, dict) and isinstance(after, dict):
        for key in sorted(set(before) | set(after)):
            _diff_values(before.get(key), after.get(key), _path(path, str(key)), changes)
        return
    if isinstance(before, list) and isinstance(after, list):
        if all(isinstance(item, dict) and "line_number" in item for item in [*before, *after]):
            before_by_line = {item["line_number"]: item for item in before}
            after_by_line = {item["line_number"]: item for item in after}
            for line_number in sorted(set(before_by_line) | set(after_by_line)):
                _diff_values(
                    before_by_line.get(line_number),
                    after_by_line.get(line_number),
                    f"{path}[line_number={line_number}]",
                    changes,
                )
            return
    if before != after:
        changes.append(VersionChange(path=path, before=before, after=after))


def version_diff(base: OrderVersion, target: OrderVersion) -> VersionDiffResponse:
    before = version_response(base).model_dump(mode="json", exclude={"id", "version_number", "source_type", "created_by_type", "created_at"})
    after = version_response(target).model_dump(mode="json", exclude={"id", "version_number", "source_type", "created_by_type", "created_at"})
    changes: list[VersionChange] = []
    _diff_values(before, after, "", changes)
    return VersionDiffResponse(base_version_id=base.id, version_id=target.id, changes=changes)