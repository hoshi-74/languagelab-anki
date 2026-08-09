from __future__ import annotations

from copy import deepcopy
from typing import Any

from .config import EXISTING_NOTE_FIELDS


class UnsafeUpdateError(ValueError):
    pass


def _as_items(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def _normalized(value: str) -> str:
    return " ".join(value.casefold().replace("<br>", " ").split())


def _append_unique(existing: str, additions: Any, separator: str = "<br>") -> str:
    result = str(existing or "").strip()
    normalized = _normalized(result)
    for addition in _as_items(additions):
        if _normalized(addition) in normalized:
            continue
        result = f"{result}{separator if result else ''}{addition}"
        normalized = _normalized(result)
    return result


def _merge_allowlist(fields: dict[str, str], additions: dict[str, Any], allowed: set[str]) -> dict[str, str]:
    unknown = sorted(set(additions) - allowed)
    if unknown:
        raise UnsafeUpdateError(f"存在不允许更新的字段：{', '.join(unknown)}")
    for field_name, value in additions.items():
        fields[field_name] = _append_unique(fields[field_name], value)
    return fields


def merge_existing_note(existing_note: dict[str, Any]) -> tuple[list[str], list[str]]:
    note_type = existing_note["note_type"]
    if note_type not in EXISTING_NOTE_FIELDS:
        raise UnsafeUpdateError(f"不支持的旧笔记类型：{note_type}")
    order = EXISTING_NOTE_FIELDS[note_type]
    original = existing_note["fields"]
    if set(order) - set(original):
        raise UnsafeUpdateError("旧笔记字段快照不完整，已拒绝更新。")

    fields = {name: str(value or "") for name, value in deepcopy(original).items()}
    additions = existing_note["additions"]
    if note_type == "英语单词模板(vocab配色)":
        fields = _merge_allowlist(fields, additions, {"英语例句", "中文例句", "vocabulary扩展"})

    changed = [name for name in order if fields[name] != str(original[name] or "")]
    if not changed:
        raise UnsafeUpdateError("新增内容与旧卡完全重复，没有可导出的更新。")
    return [fields[name] for name in order], changed
