from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any

import genanki

from .config import DECK_IDS, EXISTING_NOTE_FIELDS, MODEL_SPECS, SYNC_REMINDER
from .updates import UnsafeUpdateError, merge_existing_note
from .validation import ensure_exportable


ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_ROOT = ROOT / "templates"


def _read_template(name: str) -> str:
    return (TEMPLATE_ROOT / name).read_text(encoding="utf-8")


def _model_fields(family: str) -> list[str]:
    return {
        "basic": ["Target", "Prompt", "Answer", "Context", "Reading", "Extra", "Sources", "TTS"],
        "cloze": ["Text", "Meaning", "Extra", "Sources", "TTS"],
        "typing": ["Prompt", "Context", "Answer", "Explanation", "Sources", "TTS"],
        "listening": ["Target", "Meaning", "Context", "Extra", "Dictation", "Sources"],
    }[family]


def _make_model(spec_key: str) -> genanki.Model:
    spec = MODEL_SPECS[spec_key]
    template_name = spec.template_name or spec.family
    front = _read_template(f"{template_name}_front.html")
    back = _read_template(f"{template_name}_back.html")
    for token, value in {
        "__THEME__": spec.theme,
        "__HEADER__": spec.header,
        "__TTS_LANG__": spec.tts_language,
    }.items():
        front = front.replace(token, value)
        back = back.replace(token, value)
    model_type = genanki.Model.CLOZE if spec.family == "cloze" else genanki.Model.FRONT_BACK
    return genanki.Model(
        spec.model_id,
        spec.name,
        fields=[{"name": field} for field in _model_fields(spec.family)],
        templates=[{"name": "Card 1", "qfmt": front, "afmt": back}],
        css=_read_template("common.css"),
        model_type=model_type,
    )


def _sources_html(card: dict[str, Any]) -> str:
    urls = card.get("source_urls", [])
    if not urls:
        return ""
    links = []
    for url in urls:
        safe_url = str(url).replace('"', "%22")
        links.append(f'<a href="{safe_url}">{safe_url}</a>')
    date = str(card.get("source_date", "")).strip()
    suffix = f"<br>检索日期：{date}" if date else ""
    return "<br>".join(links) + suffix


def _html_text(value: Any) -> str:
    return escape(str(value or "")).replace("\n", "<br>")


def _joined_html(value: Any, empty: str = "无高价值内容") -> str:
    if isinstance(value, list):
        items = [_html_text(item) for item in value if str(item).strip()]
        return "；".join(items) if items else empty
    return _html_text(value) if str(value or "").strip() else empty


def _note_row(label: str, value: str, css_class: str = "") -> str:
    class_name = f"ll-note-row {css_class}".strip()
    return (
        f'<section class="{class_name}">'
        f'<div class="ll-note-label">{label}</div>'
        f'<div class="ll-note-value">{value}</div>'
        "</section>"
    )


def _bilingual_example(english: Any, chinese: Any) -> str:
    lines = []
    if str(english or "").strip():
        lines.append(f'<div class="ll-example-en">{_html_text(english)}</div>')
    if str(chinese or "").strip():
        lines.append(f'<div class="ll-example-cn">{_html_text(chinese)}</div>')
    return "".join(lines) or "无"


def _word_entry_html(word: dict[str, Any]) -> str:
    rows = [f'<div class="ll-word-entry"><div class="ll-word-title">{_html_text(word.get("word"))}</div>']
    rows.append(_note_row("词性", _html_text(word.get("part_of_speech")) or "未标注"))
    rows.append(_note_row("常见中文含义", _joined_html(word.get("common_meanings"), "未补充")))
    rows.append(_note_row("常用固定搭配", _joined_html(word.get("collocations"))))
    rows.append(_note_row("词组", _joined_html(word.get("phrases"))))
    rows.append(_note_row("例句", _bilingual_example(word.get("example_sentence"), word.get("example_translation"))))
    rows.append("</div>")
    return "".join(rows)


def _structured_note_html(card: dict[str, Any]) -> str:
    note_format = card.get("note_format")
    if note_format not in {"word", "phrase", "sentence"}:
        return ""

    rows = ['<div class="ll-note-sheet">']
    if note_format == "word":
        rows.append(_note_row("词性", _html_text(card.get("part_of_speech")) or "未标注"))
        rows.append(_note_row("常见中文含义", _joined_html(card.get("common_meanings"), _html_text(card.get("answer")))))
        rows.append(_note_row("常用固定搭配", _joined_html(card.get("collocations"))))
        rows.append(_note_row("词组", _joined_html(card.get("phrases"))))
        rows.append(_note_row("例句", _bilingual_example(card.get("example_sentence"), card.get("example_translation"))))
        rows.append(_note_row("本文原句与意思", _bilingual_example(card.get("source_sentence") or card.get("context"), card.get("source_translation") or card.get("answer")), "ll-source-row"))
    elif note_format == "phrase":
        rows.append(_note_row("中文", _html_text(card.get("answer"))))
        rows.append(_note_row("用法", _html_text(card.get("usage") or card.get("explanation")) or "未补充"))
        rows.append(_note_row("例句", _bilingual_example(card.get("example_sentence"), card.get("example_translation"))))
        if str(card.get("source_sentence") or card.get("context") or "").strip():
            rows.append(_note_row("本文原句与意思", _bilingual_example(card.get("source_sentence") or card.get("context"), card.get("source_translation") or card.get("answer")), "ll-source-row"))
    else:
        rows.append(_note_row("句意", _html_text(card.get("source_translation") or card.get("answer"))))
        unknown_words = card.get("unknown_words", [])
        word_html = "".join(_word_entry_html(word) for word in unknown_words if isinstance(word, dict))
        rows.append(_note_row("可能不认识的词语", word_html or "无"))
        grammar = card.get("grammar_breakdown", [])
        if isinstance(grammar, list):
            grammar_html = "".join(
                f'<div class="ll-grammar-step"><span>{index}</span>{_html_text(item)}</div>'
                for index, item in enumerate(grammar, start=1) if str(item).strip()
            )
        else:
            grammar_html = _html_text(grammar)
        rows.append(_note_row("语法拆解", grammar_html or "无"))

    extensions = []
    for label, key in [("辨析", "explanation"), ("同义表达", "synonyms"), ("反义表达", "antonyms"), ("同根词", "word_family")]:
        value = card.get(key)
        if isinstance(value, list):
            value = "；".join(str(item) for item in value if str(item).strip())
        if str(value or "").strip() and not (note_format == "phrase" and key == "explanation"):
            extensions.append(f"<b>{label}</b>：{_html_text(value)}")
    if extensions:
        rows.append(f'<details><summary>辨析与扩展</summary><div class="ll-details">{"<br>".join(extensions)}</div></details>')
    rows.append("</div>")
    return "".join(rows)


def _translation_cue_html(card: dict[str, Any], label: str = "请翻译") -> str:
    cue = str(card.get("translation_cue", "")).strip()
    if not cue:
        return ""
    focus = str(card.get("translation_focus", "")).strip()
    cue_html = _html_text(cue)
    if focus and focus in cue:
        before, highlighted, after = cue.partition(focus)
        cue_html = (
            f'{_html_text(before)}<mark class="ll-cue-focus">{_html_text(highlighted)}</mark>'
            f'{_html_text(after)}'
        )
    return (
        '<div class="ll-translation-cue">'
        f'<div class="ll-cue-label">{label}</div>'
        f'<div class="ll-cue-cn">{cue_html}</div>'
        '</div>'
    )


def _cloze_text(card: dict[str, Any]) -> str:
    text = str(card.get("prompt", ""))
    label = "请口头表达" if card.get("card_type") == "speaking_cloze" else "请翻译"
    cue_html = _translation_cue_html(card, label)
    return f'{cue_html}<div class="ll-cloze-sentence">{text}</div>' if cue_html else text


def _writing_prompt_html(card: dict[str, Any]) -> str:
    cue_html = _translation_cue_html(card, "根据语境表达")
    frame = _html_text(card.get("english_frame"))
    return f'{cue_html}<div class="ll-writing-frame">{frame}</div>'


def _writing_answer_html(card: dict[str, Any]) -> str:
    rows = [
        '<div class="ll-writing-answer">',
        f'<div class="ll-model-sentence">{_html_text(card.get("model_sentence") or card.get("answer"))}</div>',
        _note_row("目标表达", _html_text(card.get("answer"))),
    ]
    accepted = card.get("accepted_answers", [])
    if accepted:
        rows.append(_note_row("可接受变体", _joined_html(accepted)))
    rows.append("</div>")
    return "".join(rows)


def _writing_explanation_html(card: dict[str, Any]) -> str:
    rows = []
    for label, value in [
        ("用法", card.get("usage")),
        ("为什么这样表达", card.get("explanation")),
        ("易错点", card.get("context")),
        ("迁移例句", card.get("variant")),
    ]:
        if str(value or "").strip():
            rows.append(_note_row(label, _html_text(value)))
    return f'<div class="ll-writing-notes">{"".join(rows)}</div>' if rows else ""


def _speaking_answer_html(card: dict[str, Any]) -> str:
    part_labels = {"part1": "Part 1", "part2": "Part 2", "part3": "Part 3", "general": "通用"}
    rows = ['<div class="ll-speaking-answer">']
    rows.append(_note_row("中文意思", _html_text(card.get("meaning") or card.get("answer"))))
    rows.append(_note_row("目标表达", _html_text(card.get("target"))))
    accepted = card.get("accepted_answers", [])
    if accepted:
        rows.append(_note_row("自然替代表达", _joined_html(accepted)))
    rows.append(_note_row("口语用法", _html_text(card.get("usage"))))
    meta = " · ".join(filter(None, [
        part_labels.get(str(card.get("speaking_part", "")), ""),
        str(card.get("speaking_function", "")).strip(),
    ]))
    if meta:
        rows.append(_note_row("适用位置", _html_text(meta)))
    rows.append("</div>")
    return "".join(rows)


def _speaking_extra_html(card: dict[str, Any]) -> str:
    rows = []
    for label, value in [
        ("为什么自然", card.get("explanation")),
        ("替换语境", card.get("variant")),
        ("个人语境", card.get("context")),
    ]:
        if str(value or "").strip():
            rows.append(_note_row(label, _html_text(value)))
    return f'<div class="ll-speaking-notes">{"".join(rows)}</div>' if rows else ""


def _grammar_answer_html(card: dict[str, Any]) -> str:
    rows = ['<div class="ll-grammar-answer">']
    rows.append(_note_row("核心功能", _html_text(card.get("grammar_function"))))
    rows.append(_note_row("接续", _html_text(card.get("grammar_connection"))))
    rows.append(_note_row("本句意思", _html_text(card.get("meaning") or card.get("answer"))))
    confusable = card.get("confusable_with", [])
    if confusable:
        rows.append(_note_row("易混辨析", _joined_html(confusable)))
    if str(card.get("example_sentence", "")).strip():
        rows.append(_note_row("迁移例句", _bilingual_example(card.get("example_sentence"), card.get("example_translation"))))
    rows.append("</div>")
    return "".join(rows)


def _grammar_extra_html(card: dict[str, Any]) -> str:
    rows = []
    for label, value in [
        ("语气与限制", card.get("usage")),
        ("补充说明", card.get("explanation") or card.get("extra")),
    ]:
        if str(value or "").strip():
            rows.append(_note_row(label, _html_text(value)))
    return f'<div class="ll-grammar-notes">{"".join(rows)}</div>' if rows else ""


def _listening_extra_html(card: dict[str, Any]) -> str:
    rows = [
        _note_row("听音重点", _html_text(card.get("listening_focus"))),
        _note_row("未听出原因", _html_text(card.get("miss_reason"))),
    ]
    sound_features = card.get("sound_features", [])
    if sound_features:
        rows.append(_note_row("声音线索", _joined_html(sound_features)))
    if card.get("dictation"):
        rows.append(_note_row("听写理由", _html_text(card.get("dictation_reason"))))
    if str(card.get("explanation", "")).strip():
        rows.append(_note_row("辨听提示", _html_text(card.get("explanation"))))
    return f'<div class="ll-listening-notes">{"".join(rows)}</div>'


def _extra_html(card: dict[str, Any]) -> str:
    structured = _structured_note_html(card)
    if structured:
        return structured
    parts = []
    for label, key in [
        ("补充", "extra"), ("变式", "variant"), ("搭配", "collocations"),
        ("同义词", "synonyms"), ("反义词", "antonyms"), ("同根词", "word_family"),
    ]:
        value = card.get(key)
        if isinstance(value, list):
            value = "；".join(str(item) for item in value if str(item).strip())
        if str(value or "").strip():
            parts.append(f"<b>{label}</b>：{value}")
    return "<br>".join(parts)


def _note_fields(card: dict[str, Any], family: str) -> list[str]:
    sources = _sources_html(card)
    tts = str(card.get("model_sentence") or card.get("tts_text") or card.get("answer") or card.get("target") or "")
    structured = _structured_note_html(card)
    if family == "basic":
        note_format = card.get("note_format")
        prompt = {
            "word": "回忆本文义",
            "phrase": "回忆中文含义和用法",
            "sentence": "理解句意并回忆句子结构",
        }.get(note_format, str(card.get("prompt", "")))
        context = "" if note_format == "sentence" else str(card.get("source_sentence") or card.get("context", ""))
        return [
            str(card.get("target", "")), prompt, structured or str(card.get("answer", "")),
            context, str(card.get("reading") or (card.get("part_of_speech") if note_format == "word" else "") or ""),
            "" if structured else _extra_html(card), sources, tts,
        ]
    if family == "cloze":
        if card.get("card_type") == "speaking_cloze":
            return [
                _cloze_text(card), _speaking_answer_html(card),
                _speaking_extra_html(card), sources, tts,
            ]
        if card.get("card_type") == "japanese_grammar_cloze":
            return [
                str(card.get("prompt", "")), _grammar_answer_html(card),
                _grammar_extra_html(card), sources, tts,
            ]
        return [
            _cloze_text(card), structured or str(card.get("answer", "")),
            "" if structured else _extra_html(card), sources, tts,
        ]
    if family == "typing":
        if card.get("card_type") == "writing_expression":
            return [
                _writing_prompt_html(card), "", _writing_answer_html(card),
                _writing_explanation_html(card), sources, tts,
            ]
        return [
            str(card.get("prompt", "")), str(card.get("context", "")), str(card.get("answer", "")),
            str(card.get("explanation") or card.get("extra") or ""), sources, tts,
        ]
    return [
        str(card.get("target", "")), str(card.get("meaning", "")),
        str(card.get("context", "")), _listening_extra_html(card),
        str(card.get("target", "")) if card.get("dictation") else "", sources,
    ]


def _clean_cell(value: Any) -> str:
    return str(value or "").replace("\t", " ").replace("\r\n", "<br>").replace("\n", "<br>").replace("\r", "<br>")


def _markdown_items(value: Any, empty: str = "无高价值内容") -> str:
    if isinstance(value, list):
        items = [str(item).strip() for item in value if str(item).strip()]
        return "；".join(items) if items else empty
    return str(value).strip() if str(value or "").strip() else empty


def _structured_study_notes(batch: dict[str, Any]) -> str:
    reading_cards = [
        card for card in batch.get("cards", [])
        if card.get("action") != "update_existing"
        and card.get("card_type") in {"english_reading", "english_context_cloze", "japanese_reading"}
        and card.get("note_format") in {"word", "phrase", "sentence"}
    ]
    writing_cards = [
        card for card in batch.get("cards", [])
        if card.get("action") != "update_existing" and card.get("card_type") == "writing_expression"
    ]
    correction_cards = [
        card for card in batch.get("cards", [])
        if card.get("action") != "update_existing" and card.get("card_type") == "correction_typing"
    ]
    speaking_cards = [
        card for card in batch.get("cards", [])
        if card.get("action") != "update_existing" and card.get("card_type") == "speaking_cloze"
    ]
    grammar_cards = [
        card for card in batch.get("cards", [])
        if card.get("action") != "update_existing" and card.get("card_type") == "japanese_grammar_cloze"
    ]
    listening_cards = [
        card for card in batch.get("cards", [])
        if card.get("action") != "update_existing"
        and card.get("card_type") in {"english_listening", "japanese_listening"}
    ]
    if not any((reading_cards, writing_cards, correction_cards, speaking_cards, grammar_cards, listening_cards)):
        return ""

    lines = ["# 结构化学习笔记", "", "正面只测试一个核心内容；以下栏目用于理解、复习和查漏，不要求一次全部默写。", ""]
    words = [card for card in reading_cards if card.get("note_format") == "word"]
    phrases = [
        card for card in reading_cards
        if card.get("note_format") == "phrase" and "cloze" not in str(card.get("card_type", ""))
    ]
    expression_cards = [
        card for card in reading_cards
        if card.get("note_format") == "phrase" and "cloze" in str(card.get("card_type", ""))
    ]
    sentences = [card for card in reading_cards if card.get("note_format") == "sentence"]

    if words:
        lines.extend(["## 单词", ""])
        for card in words:
            lines.extend([
                f"### {card['target']}", "",
                f"- 词性：{card.get('part_of_speech', '')}",
                f"- 常见中文含义：{_markdown_items(card.get('common_meanings'), card.get('answer', ''))}",
                f"- 常用固定搭配：{_markdown_items(card.get('collocations'))}",
                f"- 词组：{_markdown_items(card.get('phrases'))}",
                f"- 例句：{card.get('example_sentence', '')}",
                f"- 例句中文：{card.get('example_translation', '')}",
                f"- 本文原句：{card.get('source_sentence') or card.get('context', '')}",
                f"- 本文原句中文：{card.get('source_translation') or card.get('answer', '')}", "",
            ])

    if phrases:
        lines.extend(["## 词组", ""])
        for card in phrases:
            lines.extend([
                f"### {card['target']}", "",
                f"- 中文：{card.get('answer', '')}",
                f"- 用法：{card.get('usage') or card.get('explanation', '')}",
                f"- 例句：{card.get('example_sentence', '')}",
                f"- 例句中文：{card.get('example_translation', '')}",
                f"- 本文原句：{card.get('source_sentence') or card.get('context', '')}",
                f"- 本文原句中文：{card.get('source_translation') or card.get('answer', '')}", "",
            ])

    if expression_cards:
        lines.extend(["## 联想表达", ""])
        for card in expression_cards:
            lines.extend([
                f"### {card['target']}", "",
                f"- 中文：{card.get('answer', '')}",
                f"- 用法：{card.get('usage') or card.get('explanation', '')}",
                f"- 例句：{card.get('example_sentence', '')}",
                f"- 例句中文：{card.get('example_translation', '')}", "",
            ])

    if sentences:
        lines.extend(["## 句子", ""])
        for card in sentences:
            lines.extend([
                f"### {card['target']}", "",
                f"- 句意：{card.get('source_translation') or card.get('answer', '')}", "",
                "#### 可能不认识的词语", "",
            ])
            unknown_words = card.get("unknown_words", [])
            if not unknown_words:
                lines.extend(["无", ""])
            for word in unknown_words:
                lines.extend([
                    f"##### {word.get('word', '')}", "",
                    f"- 词性：{word.get('part_of_speech', '')}",
                    f"- 常见中文含义：{_markdown_items(word.get('common_meanings'), '未补充')}",
                    f"- 常用固定搭配：{_markdown_items(word.get('collocations'))}",
                    f"- 词组：{_markdown_items(word.get('phrases'))}",
                    f"- 例句：{word.get('example_sentence', '')}",
                    f"- 例句中文：{word.get('example_translation', '')}", "",
                ])
            lines.extend(["#### 语法拆解", ""])
            lines.extend(f"{index}. {item}" for index, item in enumerate(card.get("grammar_breakdown", []), start=1))
            lines.append("")

    if writing_cards:
        lines.extend(["## 写作语境表达", "", "复习时先看完整中文语境和英文句框，口头组织答案，再查看参考表达。近义变体不算错误。", ""])
        for card in writing_cards:
            lines.extend([
                f"### {card['target']}", "",
                f"- 中文语境：{card.get('translation_cue', '')}",
                f"- 本卡重点：{card.get('translation_focus', '')}",
                f"- 英文句框：{card.get('english_frame', '')}",
                f"- 参考表达：{card.get('model_sentence') or card.get('answer', '')}",
                f"- 可接受变体：{_markdown_items(card.get('accepted_answers'))}",
                f"- 用法与迁移：{card.get('usage') or card.get('explanation', '')}", "",
            ])

    if correction_cards:
        lines.extend(["## 个人错误纠正", "", "只有答案明确、确实来自个人错误的卡保留输入核对。", ""])
        for card in correction_cards:
            lines.extend([
                f"### {card['target']}", "",
                f"- 纠错任务：{card.get('prompt', '')}",
                f"- 正确表达：{card.get('answer', '')}",
                f"- 错误原因：{card.get('explanation') or card.get('context', '')}", "",
            ])

    if speaking_cards:
        lines.extend(["## 口语表达训练", "", "先按中文意图自然说出一句话，再与示范句和替代表达比较；不要求逐字一致。", ""])
        for card in speaking_cards:
            lines.extend([
                f"### {card['target']}", "",
                f"- 中文语境：{card.get('translation_cue', '')}",
                f"- 本卡重点：{card.get('translation_focus', '')}",
                f"- 示范句：{card.get('model_sentence') or card.get('tts_text', '')}",
                f"- 自然替代表达：{_markdown_items(card.get('accepted_answers'))}",
                f"- 口语用法：{card.get('usage', '')}",
                f"- 适用位置：{card.get('speaking_part', '')} · {card.get('speaking_function', '')}", "",
            ])

    if grammar_cards:
        lines.extend(["## 日语 N2 语法", "", "先根据完整语境回忆一个语法形式，再核对接续、功能和必要辨析。", ""])
        for card in grammar_cards:
            lines.extend([
                f"### {card['target']}", "",
                f"- 完整例句：{card.get('tts_text', '')}",
                f"- 本句意思：{card.get('meaning') or card.get('answer', '')}",
                f"- 接续：{card.get('grammar_connection', '')}",
                f"- 核心功能：{card.get('grammar_function', '')}",
                f"- 易混辨析：{_markdown_items(card.get('confusable_with'))}",
                f"- 语气与限制：{card.get('usage', '')}", "",
            ])

    if listening_cards:
        lines.extend(["## 听力辨听复盘", "", "普通卡只需听懂并复述大意；只有确有必要的项目才做精确听写。", ""])
        for card in listening_cards:
            mode = "精确听写" if card.get("dictation") else "听辨意思"
            lines.extend([
                f"### {card['target']}", "",
                f"- 训练方式：{mode}",
                f"- 中文意思：{card.get('meaning', '')}",
                f"- 听音重点：{card.get('listening_focus', '')}",
                f"- 未听出原因：{card.get('miss_reason', '')}",
                f"- 声音线索：{_markdown_items(card.get('sound_features'))}",
                f"- 听写理由：{card.get('dictation_reason') or '不做听写'}", "",
            ])

    return "\n".join(lines).rstrip() + "\n"


def _write_update_tsv(path: Path, note_type: str, rows: list[dict[str, Any]]) -> None:
    fields = EXISTING_NOTE_FIELDS[note_type]
    columns = ["GUID", "Notetype", "Deck", *fields, "Tags"]
    lines = [
        "#separator:Tab",
        "#html:true",
        "#guid column:1",
        "#notetype column:2",
        "#deck column:3",
        f"#tags column:{len(columns)}",
        "#columns:" + ",".join(columns),
    ]
    for row in rows:
        values = [row["guid"], note_type, row["deck"], *row["fields"], " ".join(row["tags"])]
        lines.append("\t".join(_clean_cell(value) for value in values))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8-sig")


def _safe_filename(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-") or "updates"


def build_batch(batch_path: Path, output_root: Path) -> dict[str, Any]:
    batch = json.loads(batch_path.read_text(encoding="utf-8-sig"))
    ensure_exportable(batch)
    batch_id = batch["batch_id"]
    output_dir = output_root / batch_id
    output_dir.mkdir(parents=True, exist_ok=True)

    models: dict[str, genanki.Model] = {}
    decks: dict[str, genanki.Deck] = {}
    update_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    review_items: list[str] = []
    supplement_links: list[str] = []
    changed_fields: dict[str, list[str]] = {}
    card_counts: Counter[str] = Counter()
    related_expression_count = 0

    for card in batch["cards"]:
        action = card.get("action", "create")
        if action == "update_existing":
            existing = card["existing_note"]
            try:
                merged_fields, changed = merge_existing_note(existing)
            except UnsafeUpdateError as exc:
                review_items.append(f"`{card['id']}` 未导出旧卡更新：{exc}")
                continue
            note_type = existing["note_type"]
            update_rows[note_type].append({
                "guid": existing["guid"],
                "deck": existing["deck"],
                "fields": merged_fields,
                "tags": sorted(set(existing.get("tags", [])) | set(card.get("tags", [])) | {"LanguageLab-update"}),
            })
            changed_fields[card["id"]] = changed
            card_counts["update_existing"] += 1
            continue

        spec_key = card["card_type"]
        spec = MODEL_SPECS[spec_key]
        if spec_key not in models:
            models[spec_key] = _make_model(spec_key)
        model = models[spec_key]
        deck_name = card["deck"]
        deck = decks.setdefault(deck_name, genanki.Deck(DECK_IDS[deck_name], deck_name))
        stable_guid = genanki.guid_for("LanguageLab-v1", card["id"])
        tags = sorted(set(card.get("tags", [])) | {"LanguageLab", f"batch::{batch_id}"})
        if card.get("expression_group") and spec_key != "correction_typing":
            group = _safe_filename(str(card["expression_group"]).casefold())
            tags = sorted(set(tags) | {"expression-bank", f"expression::{group}"})
            related_expression_count += 1
        if card.get("memory_priority"):
            tags = sorted(set(tags) | {f"priority::{card['memory_priority']}"})
        if action == "supplement":
            related = card["related_note"]
            tags = sorted(set(tags) | {"LanguageLab-supplement"})
            supplement_links.append(
                f"`{card['id']}` → `{related['note_type']}` / `{related['deck']}` / GUID `{related['guid']}`"
            )
        note = genanki.Note(
            model=model,
            fields=_note_fields(card, spec.family),
            tags=tags,
            guid=stable_guid,
        )
        deck.add_note(note)
        card_counts[spec_key] += 1

    generated_files: list[str] = []
    if decks:
        apkg_path = output_dir / f"LanguageLab-{batch_id}.apkg"
        genanki.Package(list(decks.values())).write_to_file(str(apkg_path))
        generated_files.append(apkg_path.name)

    for note_type, rows in update_rows.items():
        filename = f"update-{_safe_filename(note_type)}.tsv"
        _write_update_tsv(output_dir / filename, note_type, rows)
        generated_files.append(filename)

    new_count = sum(count for kind, count in card_counts.items() if kind != "update_existing")
    update_count = card_counts["update_existing"]
    supplement_count = len(supplement_links)
    estimated_minutes = max(1, round(new_count * 0.7 + update_count * 0.25))
    built_at = datetime.now().astimezone().isoformat(timespec="seconds")

    summary_lines = [
        f"# 批次摘要：{batch_id}", "", f"- 生成时间：{built_at}",
        f"- 新卡/补充卡：{new_count}", f"- 旧卡更新：{update_count}",
        f"- 其中关联补充卡：{supplement_count}",
        f"- 联想表达卡：{related_expression_count}",
        f"- 预计首次学习与检查：约 {estimated_minutes} 分钟", "", "## 卡片清单", "",
    ]
    for kind, count in sorted(card_counts.items()):
        summary_lines.append(f"- `{kind}`：{count}")
    summary_lines.extend(["", "## 导入文件", ""])
    summary_lines.extend(f"- `{name}`" for name in generated_files)
    if not generated_files:
        summary_lines.append("- 无；所有项目均需人工检查。")
    if changed_fields:
        summary_lines.extend(["", "## 旧卡变更字段", ""])
        summary_lines.extend(f"- `{card_id}`：{', '.join(fields)}" for card_id, fields in changed_fields.items())
    if supplement_links:
        summary_lines.extend(["", "## 补充卡关联", "", *[f"- {item}" for item in supplement_links]])
    summary_lines.extend(["", "## 下一步", "", SYNC_REMINDER, ""])
    (output_dir / "summary.md").write_text("\n".join(summary_lines), encoding="utf-8")

    review_lines = [f"# 人工检查：{batch_id}", "", "## 导入前检查", "",
        "- 确认本轮开始前已经在主设备完成同步。",
        "- 快速浏览新卡正反面，确认语义、假名、例句和挖空范围。",
    ]
    if update_count:
        review_lines.append(
            "- 导入旧卡 TSV 时核对笔记类型、GUID、字段映射和牌组；不要把空列映射到其他字段。"
        )
    review_lines.append("- 导入前建议从 Anki 导出备份。")
    if review_items:
        review_lines.extend(["", "## 已阻止的项目", "", *[f"- {item}" for item in review_items]])
    else:
        review_lines.extend(["", "## 自动检查", "", "- 未发现阻止导出的项目。"])
    review_lines.extend(["", "## 同步", "", SYNC_REMINDER,
        "如果 Anki 出现单向上传或下载提示，请停止并确认方向。", ""])
    (output_dir / "review.md").write_text("\n".join(review_lines), encoding="utf-8")
    generated_files.extend(["summary.md", "review.md"])

    study_note_path = ROOT / "notes" / f"{batch_id}.md"
    manual_notes = study_note_path.read_text(encoding="utf-8").strip() if study_note_path.is_file() else ""
    structured_notes = _structured_study_notes(batch).strip()
    if manual_notes or structured_notes:
        note_sections = [section for section in (manual_notes, structured_notes) if section]
        (output_dir / "study-notes.md").write_text("\n\n".join(note_sections) + "\n", encoding="utf-8")
        generated_files.append("study-notes.md")

    manifest = {
        "batch_id": batch_id,
        "built_at": built_at,
        "new_cards": new_count,
        "existing_updates": update_count,
        "supplement_cards": supplement_count,
        "related_expression_cards": related_expression_count,
        "estimated_minutes": estimated_minutes,
        "files": generated_files,
        "blocked_items": review_items,
        "sync_reminder": SYNC_REMINDER,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest
