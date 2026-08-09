from __future__ import annotations

import re
from typing import Any

from .config import CARD_TYPE_TO_DECKS, EXISTING_NOTE_FIELDS, MODEL_SPECS, PROTECTED_NOTE_TYPES


BATCH_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,63}$")
DANGEROUS_HTML_RE = re.compile(
    r"<(?:script|iframe|object|embed|link|style)\b|\bon[a-z]+\s*=|javascript\s*:",
    re.IGNORECASE,
)
STRUCTURED_READING_TYPES = {
    "english_reading", "english_context_cloze", "japanese_reading", "japanese_grammar_cloze",
}


class BatchValidationError(ValueError):
    pass


def _walk_strings(value: Any, path: str = ""):
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, dict):
        for key, child in value.items():
            yield from _walk_strings(child, f"{path}.{key}" if path else str(key))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk_strings(child, f"{path}[{index}]")


def validate_batch(batch: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(batch, dict):
        return ["批次根节点必须是 JSON 对象。"]

    if batch.get("schema_version") != "1.0":
        errors.append("schema_version 必须是 1.0。")
    if batch.get("language") not in {"english", "japanese", "mixed"}:
        errors.append("language 必须是 english、japanese 或 mixed。")
    if batch.get("scenario") not in {"reading", "writing", "speaking", "listening", "mixed"}:
        errors.append("scenario 无效。")

    batch_id = batch.get("batch_id")
    if not isinstance(batch_id, str) or not BATCH_ID_RE.fullmatch(batch_id):
        errors.append("batch_id 必须为 3-64 位字母、数字、点、下划线或连字符。")

    source = batch.get("source")
    if not isinstance(source, dict) or not str(source.get("raw_text", "")).strip():
        errors.append("source.raw_text 不能为空；截图材料也必须保留原始识别文本。")

    ocr = batch.get("ocr", {"status": "not_applicable", "uncertain": []})
    if not isinstance(ocr, dict):
        errors.append("ocr 必须是对象。")
    else:
        status = ocr.get("status", "not_applicable")
        if status not in {"not_applicable", "confirmed", "needs_confirmation"}:
            errors.append("ocr.status 必须是 not_applicable、confirmed 或 needs_confirmation。")
        if not isinstance(ocr.get("uncertain", []), list):
            errors.append("ocr.uncertain 必须是数组。")

    cards = batch.get("cards")
    if not isinstance(cards, list) or not cards:
        errors.append("cards 必须是非空数组。")
        return errors

    seen_ids: set[str] = set()
    seen_existing_guids: set[str] = set()
    for index, card in enumerate(cards, start=1):
        prefix = f"cards[{index}]"
        if not isinstance(card, dict):
            errors.append(f"{prefix} 必须是对象。")
            continue
        card_id = str(card.get("id", "")).strip()
        if not card_id:
            errors.append(f"{prefix}.id 不能为空。")
        elif card_id in seen_ids:
            errors.append(f"{prefix}.id 与批次中其他卡片重复：{card_id}")
        seen_ids.add(card_id)

        action = card.get("action", "create")
        if action not in {"create", "supplement", "update_existing"}:
            errors.append(f"{prefix}.action 无效。")

        card_type = card.get("card_type")
        if card_type not in MODEL_SPECS:
            errors.append(f"{prefix}.card_type 无效：{card_type}")
        else:
            allowed_decks = CARD_TYPE_TO_DECKS[card_type]
            if action != "update_existing" and card.get("deck") not in allowed_decks:
                errors.append(f"{prefix}.deck 与卡片类型不匹配，应为：{', '.join(sorted(allowed_decks))}")
            expected_tts = MODEL_SPECS[card_type].tts_language
            if action != "update_existing" and card.get("tts_language", expected_tts) != expected_tts:
                errors.append(f"{prefix}.tts_language 应为 {expected_tts}。")

        if action in {"create", "supplement"}:
            if not str(card.get("prompt", "")).strip():
                errors.append(f"{prefix}.prompt 不能为空。")
            if not str(card.get("answer", "")).strip():
                errors.append(f"{prefix}.answer 不能为空。")
            if card_type and "cloze" in card_type and "{{c" not in str(card.get("prompt", "")):
                errors.append(f"{prefix}.prompt 必须包含 Anki cloze 标记，例如 {{{{c1::表达}}}}。")
            if card_type == "english_context_cloze" and not str(card.get("translation_cue", "")).strip():
                errors.append(f"{prefix}.translation_cue 必须提供完整中文意图，让正面任务明确为中译英。")
            if card_type == "english_context_cloze":
                cue = str(card.get("translation_cue", ""))
                focus = str(card.get("translation_focus", "")).strip()
                if not focus:
                    errors.append(f"{prefix}.translation_focus 必须标出中文中与英文挖空对应的部分。")
                elif focus not in cue:
                    errors.append(f"{prefix}.translation_focus 必须是 translation_cue 中的连续原文。")
            if card_type == "writing_expression":
                cue = str(card.get("translation_cue", ""))
                focus = str(card.get("translation_focus", "")).strip()
                frame = str(card.get("english_frame", "")).strip()
                if not cue.strip():
                    errors.append(f"{prefix}.translation_cue 必须提供完整中文语境。")
                if not focus:
                    errors.append(f"{prefix}.translation_focus 必须标出本卡训练的连续中文片段。")
                elif focus not in cue:
                    errors.append(f"{prefix}.translation_focus 必须是 translation_cue 中的连续原文。")
                if not frame:
                    errors.append(f"{prefix}.english_frame 必须提供限制答案范围的英文句框。")
                elif "[...]" not in frame:
                    errors.append(f"{prefix}.english_frame 必须使用 [...] 标出需要产出的部分。")
                if not str(card.get("model_sentence", "")).strip():
                    errors.append(f"{prefix}.model_sentence 必须提供完整、自然的参考句。")
                if not isinstance(card.get("accepted_answers"), list):
                    errors.append(f"{prefix}.accepted_answers 必须是数组；没有变体时使用空数组。")
                if not str(card.get("usage", "")).strip():
                    errors.append(f"{prefix}.usage 必须说明目标表达的用法或迁移条件。")
            if card_type == "speaking_cloze":
                cue = str(card.get("translation_cue", ""))
                focus = str(card.get("translation_focus", "")).strip()
                if not cue.strip():
                    errors.append(f"{prefix}.translation_cue 必须提供完整、自然的中文口语意图。")
                if not focus:
                    errors.append(f"{prefix}.translation_focus 必须标出口头表达的训练重点。")
                elif focus not in cue:
                    errors.append(f"{prefix}.translation_focus 必须是 translation_cue 中的连续原文。")
                if not str(card.get("model_sentence", "")).strip():
                    errors.append(f"{prefix}.model_sentence 必须提供完整、自然的示范句。")
                if not isinstance(card.get("accepted_answers"), list):
                    errors.append(f"{prefix}.accepted_answers 必须是数组；没有替代表达时使用空数组。")
                if not str(card.get("usage", "")).strip():
                    errors.append(f"{prefix}.usage 必须说明表达的口语用法或语气。")
                if card.get("speaking_part") not in {"part1", "part2", "part3", "general"}:
                    errors.append(f"{prefix}.speaking_part 必须是 part1、part2、part3 或 general。")
                if not str(card.get("speaking_function", "")).strip():
                    errors.append(f"{prefix}.speaking_function 必须说明表达功能，例如观点、原因、例子或叙事细节。")
                if not str(card.get("tts_text", "")).strip():
                    errors.append(f"{prefix}.tts_text 必须提供完整示范句，供背面朗读。")
            if card_type == "japanese_grammar_cloze":
                if not str(card.get("grammar_connection", "")).strip():
                    errors.append(f"{prefix}.grammar_connection 必须提供语法接续。")
                if not str(card.get("grammar_function", "")).strip():
                    errors.append(f"{prefix}.grammar_function 必须提供核心功能和语气。")
                if not isinstance(card.get("confusable_with"), list):
                    errors.append(f"{prefix}.confusable_with 必须是数组；没有必要辨析时使用空数组。")
                if not str(card.get("tts_text", "")).strip():
                    errors.append(f"{prefix}.tts_text 必须提供揭晓后的完整日语例句。")
            if card_type in {"english_listening", "japanese_listening"}:
                if not str(card.get("meaning", "")).strip():
                    errors.append(f"{prefix}.meaning 必须提供听力文本的准确中文意思。")
                if not str(card.get("listening_focus", "")).strip():
                    errors.append(f"{prefix}.listening_focus 必须说明本卡需要听出的关键词、意群或声音线索。")
                if not str(card.get("miss_reason", "")).strip():
                    errors.append(f"{prefix}.miss_reason 必须记录未听出的主要原因。")
                if not isinstance(card.get("sound_features"), list):
                    errors.append(f"{prefix}.sound_features 必须是数组；没有明显语音现象时使用空数组。")
                if not isinstance(card.get("dictation"), bool):
                    errors.append(f"{prefix}.dictation 必须明确为 true 或 false。")
                elif card.get("dictation") and not str(card.get("dictation_reason", "")).strip():
                    errors.append(f"{prefix}.dictation_reason 必须解释为什么这条内容值得精确听写。")
            if action == "supplement":
                related = card.get("related_note")
                if not isinstance(related, dict) or not all(str(related.get(key, "")).strip() for key in ("guid", "note_type", "deck")):
                    errors.append(f"{prefix}.related_note 必须记录补充卡关联的旧笔记 GUID、笔记类型和牌组。")

            if card_type in STRUCTURED_READING_TYPES:
                note_format = card.get("note_format")
                if note_format not in {"word", "phrase", "sentence"}:
                    errors.append(f"{prefix}.note_format 必须是 word、phrase 或 sentence。")
                elif note_format == "word":
                    for field in ("part_of_speech", "example_sentence", "example_translation", "source_sentence", "source_translation"):
                        if not str(card.get(field, "")).strip():
                            errors.append(f"{prefix}.{field} 是单词笔记的必填字段。")
                    if not isinstance(card.get("common_meanings"), list) or not card.get("common_meanings"):
                        errors.append(f"{prefix}.common_meanings 必须包含至少一个常见中文含义。")
                    for field in ("collocations", "phrases"):
                        if not isinstance(card.get(field), list):
                            errors.append(f"{prefix}.{field} 必须是数组；没有高价值内容时使用空数组。")
                elif note_format == "phrase":
                    for field in ("usage", "example_sentence", "example_translation"):
                        if not str(card.get(field, "")).strip():
                            errors.append(f"{prefix}.{field} 是词组笔记的必填字段。")
                else:
                    if not str(card.get("source_translation", "")).strip():
                        errors.append(f"{prefix}.source_translation 是句子笔记的必填字段。")
                    if not isinstance(card.get("unknown_words"), list):
                        errors.append(f"{prefix}.unknown_words 必须是数组。")
                    if not isinstance(card.get("grammar_breakdown"), list) or not card.get("grammar_breakdown"):
                        errors.append(f"{prefix}.grammar_breakdown 必须包含句子主干和必要语法拆解。")

        for value_path, value in _walk_strings(card):
            if DANGEROUS_HTML_RE.search(value):
                errors.append(f"{prefix}.{value_path} 含有不允许的脚本、事件属性或外部页面元素。")

        if action == "update_existing":
            existing = card.get("existing_note")
            if not isinstance(existing, dict):
                errors.append(f"{prefix}.existing_note 是更新旧卡时的必填对象。")
                continue
            note_type = existing.get("note_type")
            if note_type in PROTECTED_NOTE_TYPES:
                errors.append(f"{prefix}.existing_note.note_type 属于只读保护词库，必须改为 LanguageLab 补充卡。")
                continue
            if note_type not in EXISTING_NOTE_FIELDS:
                errors.append(f"{prefix}.existing_note.note_type 不是受支持的旧笔记类型。")
                continue
            if not str(existing.get("guid", "")).strip():
                errors.append(f"{prefix}.existing_note.guid 不能为空。")
            elif existing["guid"] in seen_existing_guids:
                errors.append(f"{prefix}.existing_note.guid 在同一批次中重复，可能产生冲突更新。")
            else:
                seen_existing_guids.add(existing["guid"])
            fields = existing.get("fields")
            if not isinstance(fields, dict):
                errors.append(f"{prefix}.existing_note.fields 必须包含完整字段快照。")
            else:
                missing = [name for name in EXISTING_NOTE_FIELDS[note_type] if name not in fields]
                if missing:
                    errors.append(f"{prefix}.existing_note.fields 缺少字段：{', '.join(missing)}")
            if not isinstance(existing.get("additions"), dict) or not existing.get("additions"):
                errors.append(f"{prefix}.existing_note.additions 不能为空。")

    return errors


def ensure_exportable(batch: dict[str, Any]) -> None:
    errors = validate_batch(batch)
    if errors:
        raise BatchValidationError("\n".join(f"- {error}" for error in errors))
    ocr = batch.get("ocr", {})
    if ocr.get("status") == "needs_confirmation" or ocr.get("uncertain"):
        raise BatchValidationError("OCR 仍有未确认内容。请清空 ocr.uncertain 并将 ocr.status 改为 confirmed 后再导出。")
