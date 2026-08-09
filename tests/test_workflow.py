from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
import zipfile
from copy import deepcopy
from pathlib import Path

from languagelab.config import EXISTING_NOTE_FIELDS
from languagelab.generator import (
    ROOT,
    _cloze_text,
    _grammar_answer_html,
    _listening_extra_html,
    _make_model,
    _speaking_answer_html,
    _structured_note_html,
    _writing_answer_html,
    _writing_prompt_html,
    build_batch,
)
from languagelab.updates import UnsafeUpdateError, merge_existing_note
from languagelab.validation import BatchValidationError, ensure_exportable, validate_batch


class WorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.example_path = ROOT / "batches" / "example.json"
        self.example = json.loads(self.example_path.read_text(encoding="utf-8"))

    def test_example_is_valid(self) -> None:
        self.assertEqual([], validate_batch(self.example))

    def test_typing_hint_is_back_only_and_tts_is_available(self) -> None:
        front = (ROOT / "templates" / "typing_front.html").read_text(encoding="utf-8")
        back = (ROOT / "templates" / "typing_back.html").read_text(encoding="utf-8")
        self.assertNotIn("{{Context}}", front)
        self.assertIn("{{Context}}", back)
        self.assertNotIn("{{tts", front)
        self.assertIn("{{tts __TTS_LANG__:TTS}}", back)

    def test_writing_expression_uses_context_without_exact_typing(self) -> None:
        front = (ROOT / "templates" / "writing_front.html").read_text(encoding="utf-8")
        back = (ROOT / "templates" / "writing_back.html").read_text(encoding="utf-8")
        self.assertNotIn("{{type:Answer}}", front)
        self.assertIn("{{Prompt}}", front)
        self.assertIn("{{Answer}}", back)
        self.assertNotIn("{{tts", front)
        self.assertIn("{{tts __TTS_LANG__:TTS}}", back)
        self.assertIn("{{type:Answer}}", (ROOT / "templates" / "typing_front.html").read_text(encoding="utf-8"))

        card = {
            "translation_cue": "许多城市正在努力探索一条可持续发展的道路。",
            "translation_focus": "努力探索一条可持续发展的道路",
            "english_frame": "Many cities are [...].",
            "answer": "make efforts to explore a path of sustainable development",
            "model_sentence": "Many cities are making efforts to explore a path of sustainable development.",
            "accepted_answers": ["Many cities are working to explore a path towards sustainable development."],
        }
        prompt = _writing_prompt_html(card)
        answer = _writing_answer_html(card)
        self.assertIn('<mark class="ll-cue-focus">努力探索一条可持续发展的道路</mark>', prompt)
        self.assertIn("Many cities are [...].", prompt)
        self.assertIn("Many cities are making efforts", answer)
        self.assertIn("可接受变体", answer)

    def test_writing_expression_requires_context_frame_and_model(self) -> None:
        batch = deepcopy(self.example)
        card = next(card for card in batch["cards"] if card["card_type"] == "writing_expression")
        card["translation_cue"] = "许多城市正在努力探索一条可持续发展的道路。"
        card["translation_focus"] = "努力探索一条可持续发展的道路"
        card["english_frame"] = "Many cities are [...]."
        card["model_sentence"] = "Many cities are making efforts to explore a path of sustainable development."
        card["accepted_answers"] = []
        card["usage"] = "make efforts to do something"
        self.assertEqual([], validate_batch(batch))

        card["translation_focus"] = "不存在的片段"
        card["english_frame"] = "Many cities are making efforts."
        card.pop("model_sentence")
        errors = validate_batch(batch)
        for field in ("translation_focus", "english_frame", "model_sentence"):
            self.assertTrue(any(field in error for error in errors))

    def test_speaking_card_uses_oral_cue_model_sentence_and_variants(self) -> None:
        card = next(card for card in self.example["cards"] if card["card_type"] == "speaking_cloze")
        front_text = _cloze_text(card)
        answer = _speaking_answer_html(card)
        model = _make_model("speaking_cloze")
        self.assertIn("请口头表达", front_text)
        self.assertIn('<mark class="ll-cue-focus">到周五就没劲了</mark>', front_text)
        self.assertIn("自然替代表达", answer)
        self.assertIn("适用位置", answer)
        self.assertNotIn("{{type:", model.templates[0]["qfmt"])
        self.assertIn("{{tts en_US:TTS}}", model.templates[0]["afmt"])

    def test_japanese_grammar_back_separates_connection_function_and_contrast(self) -> None:
        card = next(card for card in self.example["cards"] if card["card_type"] == "japanese_grammar_cloze")
        answer = _grammar_answer_html(card)
        model = _make_model("japanese_grammar_cloze")
        for label in ("核心功能", "接续", "本句意思", "易混辨析"):
            self.assertIn(label, answer)
        self.assertIn("完整语境", model.templates[0]["qfmt"])
        self.assertIn("{{tts ja_JP:TTS}}", model.templates[0]["afmt"])

    def test_listening_cards_distinguish_comprehension_and_dictation(self) -> None:
        front = (ROOT / "templates" / "listening_front.html").read_text(encoding="utf-8")
        back = (ROOT / "templates" / "listening_back.html").read_text(encoding="utf-8")
        self.assertIn("听辨意思", front)
        self.assertIn("精确听写", front)
        self.assertIn("{{^Dictation}}", front)
        self.assertIn("{{type:Target}}", front)
        self.assertIn("{{tts __TTS_LANG__:Target}}", front)
        self.assertIn("辨听复盘", back)
        card = next(card for card in self.example["cards"] if card["card_type"] == "english_listening")
        extra = _listening_extra_html(card)
        for label in ("听音重点", "未听出原因", "声音线索", "听写理由"):
            self.assertIn(label, extra)

    def test_remaining_scenarios_require_learning_diagnostics(self) -> None:
        cases = [
            ("speaking_cloze", "speaking_function"),
            ("japanese_grammar_cloze", "grammar_connection"),
            ("english_listening", "miss_reason"),
        ]
        for card_type, field in cases:
            with self.subTest(card_type=card_type, field=field):
                batch = deepcopy(self.example)
                card = next(card for card in batch["cards"] if card["card_type"] == card_type)
                card.pop(field)
                errors = validate_batch(batch)
                self.assertTrue(any(field in error for error in errors))

    def test_reading_front_is_clean_and_tts_plays_on_back(self) -> None:
        front = (ROOT / "templates" / "basic_front.html").read_text(encoding="utf-8")
        back = (ROOT / "templates" / "basic_back.html").read_text(encoding="utf-8")
        self.assertNotIn("{{tts", front)
        self.assertNotIn("{{Prompt}}", front)
        self.assertNotIn("{{Reading}}", front)
        self.assertIn("{{tts __TTS_LANG__:TTS}}", back)
        self.assertIn("{{Reading}}", back)
        self.assertNotIn("{{Answer}}", front)
        self.assertNotIn("{{Context}}", front)
        self.assertIn("ll-basic-front", front)
        self.assertIn("text-align: center", (ROOT / "templates" / "common.css").read_text(encoding="utf-8"))
        self.assertIn("{{Answer}}", back)
        self.assertIn("结构化答案", back)

    def test_structured_word_note_contains_required_learning_sections(self) -> None:
        html = _structured_note_html({
            "note_format": "word",
            "answer": "通货膨胀",
            "part_of_speech": "n.",
            "common_meanings": ["通货膨胀", "膨胀"],
            "collocations": ["rising inflation"],
            "phrases": ["inflation rate"],
            "example_sentence": "Inflation remains high.",
            "example_translation": "通胀仍然很高。",
            "source_sentence": "The bank is watching inflation.",
            "source_translation": "央行正在关注通胀。",
        })
        for label in ("词性", "常见中文含义", "常用固定搭配", "词组", "例句", "本文原句与意思"):
            self.assertIn(label, html)

    def test_structured_phrase_and_sentence_notes_are_atomic_but_complete(self) -> None:
        phrase = _structured_note_html({
            "note_format": "phrase", "answer": "谨慎平衡", "usage": "between A and B",
            "example_sentence": "We must walk a fine line.", "example_translation": "我们必须谨慎权衡。",
        })
        self.assertIn("中文", phrase)
        self.assertIn("用法", phrase)
        self.assertIn("例句", phrase)
        sentence = _structured_note_html({
            "note_format": "sentence", "source_translation": "这是句意。",
            "unknown_words": [{
                "word": "fragile", "part_of_speech": "adj.", "common_meanings": ["脆弱的"],
                "collocations": ["fragile recovery"], "phrases": [],
                "example_sentence": "The recovery is fragile.", "example_translation": "复苏仍很脆弱。",
            }],
            "grammar_breakdown": ["主干：The recovery is fragile.", "fragile 作表语。"],
        })
        self.assertIn("可能不认识的词语", sentence)
        self.assertIn("fragile", sentence)
        self.assertIn("语法拆解", sentence)

    def test_english_cloze_shows_chinese_translation_task_above_sentence(self) -> None:
        html = _cloze_text({
            "translation_cue": "由于工资仍然停滞，许多家庭的生活水平几乎没有改善。",
            "translation_focus": "由于工资仍然停滞",
            "prompt": "But {{c1::with wages still relatively flat}}, many households have seen little improvement.",
        })
        self.assertIn("ll-translation-cue", html)
        self.assertIn("ll-cloze-sentence", html)
        self.assertLess(html.index("ll-translation-cue"), html.index("ll-cloze-sentence"))
        self.assertIn('<mark class="ll-cue-focus">由于工资仍然停滞</mark>', html)
        self.assertIn("{{c1::with wages still relatively flat}}", html)

    def test_english_cloze_requires_translation_cue(self) -> None:
        batch = deepcopy(self.example)
        cloze = next(card for card in batch["cards"] if card["card_type"] == "english_context_cloze")
        cloze.pop("translation_cue")
        errors = validate_batch(batch)
        self.assertTrue(any("translation_cue" in error for error in errors))

    def test_english_cloze_focus_must_be_part_of_chinese_cue(self) -> None:
        batch = deepcopy(self.example)
        cloze = next(card for card in batch["cards"] if card["card_type"] == "english_context_cloze")
        cloze["translation_focus"] = "不存在的中文片段"
        errors = validate_batch(batch)
        self.assertTrue(any("连续原文" in error for error in errors))

    def test_ocr_uncertainty_blocks_export(self) -> None:
        batch = deepcopy(self.example)
        batch["ocr"] = {
            "status": "needs_confirmation",
            "uncertain": [{"text": "rn", "reason": "可能是 m"}],
        }
        with self.assertRaises(BatchValidationError):
            ensure_exportable(batch)

    def test_duplicate_card_id_is_rejected(self) -> None:
        batch = deepcopy(self.example)
        batch["cards"][1]["id"] = batch["cards"][0]["id"]
        errors = validate_batch(batch)
        self.assertTrue(any("重复" in error for error in errors))

    def test_unsafe_html_is_rejected(self) -> None:
        batch = deepcopy(self.example)
        batch["cards"][0]["extra"] = '<img src="x" onerror="alert(1)">'
        errors = validate_batch(batch)
        self.assertTrue(any("不允许" in error for error in errors))

    def test_supplement_requires_related_note(self) -> None:
        batch = deepcopy(self.example)
        batch["cards"][0]["action"] = "supplement"
        errors = validate_batch(batch)
        self.assertTrue(any("related_note" in error for error in errors))

    def test_protected_note_types_cannot_be_updated(self) -> None:
        for note_type in ("eggrolls-JLPT10k-v3", "TOEFL 绿宝书"):
            with self.subTest(note_type=note_type):
                batch = deepcopy(self.example)
                card = batch["cards"][0]
                card["action"] = "update_existing"
                card["existing_note"] = {
                    "guid": "protected-guid",
                    "note_type": note_type,
                    "deck": "受保护词库",
                    "fields": {},
                    "additions": {"note": "不得写入"},
                }
                errors = validate_batch(batch)
                self.assertTrue(any("只读保护词库" in error for error in errors))

    def test_unknown_existing_field_update_is_rejected(self) -> None:
        fields = {name: "" for name in EXISTING_NOTE_FIELDS["英语单词模板(vocab配色)"]}
        with self.assertRaises(UnsafeUpdateError):
            merge_existing_note({
                "note_type": "英语单词模板(vocab配色)",
                "fields": fields,
                "additions": {"中文释义": "不允许覆盖释义"},
            })

    def test_build_writes_utf8_tsv_without_overwriting_existing_fields(self) -> None:
        fields = {name: "" for name in EXISTING_NOTE_FIELDS["英语单词模板(vocab配色)"]}
        fields.update({
            "英语单词": "sustain",
            "中文释义": "维持；支撑",
            "英语例句": "The bridge sustained heavy damage.",
            "中文例句": "这座桥遭受了严重损坏。",
        })
        batch = {
            "schema_version": "1.0",
            "batch_id": "test-existing-update",
            "language": "english",
            "scenario": "reading",
            "source": {"type": "pasted_text", "raw_text": "sustain", "clean_text": "sustain"},
            "ocr": {"status": "not_applicable", "uncertain": []},
            "cards": [{
                "id": "test-update-sustain",
                "card_type": "english_reading",
                "action": "update_existing",
                "deck": "LanguageLab::English::Reading",
                "target": "sustain",
                "prompt": "",
                "answer": "",
                "tags": ["ielts", "reading"],
                "existing_note": {
                    "guid": "stable-demo-guid",
                    "note_type": "英语单词模板(vocab配色)",
                    "deck": "大学六级英语单词",
                    "fields": fields,
                    "additions": {
                        "英语例句": "Policies must be sustained over time.",
                        "中文例句": "政策必须长期坚持。",
                        "vocabulary扩展": "搭配：sustain economic growth"
                    },
                    "tags": ["CET6"]
                }
            }]
        }
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            batch_path = root / "batch.json"
            batch_path.write_text(json.dumps(batch, ensure_ascii=False), encoding="utf-8")
            manifest = build_batch(batch_path, root / "output")
            tsv_name = next(name for name in manifest["files"] if name.endswith(".tsv"))
            tsv_path = root / "output" / batch["batch_id"] / tsv_name
            data = tsv_path.read_text(encoding="utf-8-sig")
            self.assertTrue(tsv_path.read_bytes().startswith(b"\xef\xbb\xbf"))
            self.assertIn("The bridge sustained heavy damage.<br>Policies must be sustained over time.", data)
            self.assertIn("维持；支撑", data)
            self.assertIn("sustain economic growth", data)
            self.assertEqual(1, manifest["existing_updates"])

    def test_build_creates_apkg_reports_and_stable_guids(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            first = build_batch(self.example_path, output)
            apkg = output / self.example["batch_id"] / f"LanguageLab-{self.example['batch_id']}.apkg"
            self.assertTrue(apkg.is_file())
            self.assertGreater(apkg.stat().st_size, 1000)
            self.assertEqual(9, first["new_cards"])
            first_guids = self._read_guids(apkg, output / "extract-1")
            self.assertEqual(9, self._read_card_count(apkg, output / "cards-1"))

            second = build_batch(self.example_path, output)
            second_guids = self._read_guids(apkg, output / "extract-2")
            self.assertEqual(first_guids, second_guids)
            self.assertEqual(9, len(first_guids))
            self.assertIn("summary.md", second["files"])
            self.assertIn("review.md", second["files"])
            notes = (output / self.example["batch_id"] / "study-notes.md").read_text(encoding="utf-8")
            self.assertIn("# 结构化学习笔记", notes)
            self.assertIn("## 单词", notes)
            self.assertIn("## 词组", notes)
            self.assertIn("## 口语表达训练", notes)
            self.assertIn("## 日语 N2 语法", notes)
            self.assertIn("## 听力辨听复盘", notes)

    def test_review_omits_tsv_instructions_when_there_are_no_updates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "output"
            manifest = build_batch(self.example_path, output)
            review = (output / manifest["batch_id"] / "review.md").read_text(encoding="utf-8")
            if manifest["existing_updates"] == 0:
                self.assertNotIn("导入旧卡 TSV", review)

    def test_expression_bank_fields_create_tags_and_manifest_count(self) -> None:
        batch = deepcopy(self.example)
        batch["batch_id"] = "test-expression-bank"
        batch["cards"] = [batch["cards"][0]]
        batch["cards"][0]["expression_group"] = "urban-development"
        batch["cards"][0]["memory_priority"] = "related"
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            batch_path = root / "batch.json"
            batch_path.write_text(json.dumps(batch, ensure_ascii=False), encoding="utf-8")
            manifest = build_batch(batch_path, root / "output")
            self.assertEqual(1, manifest["related_expression_cards"])
            apkg = root / "output" / batch["batch_id"] / f"LanguageLab-{batch['batch_id']}.apkg"
            tags = self._read_tags(apkg, root / "expression-tags")
            self.assertIn("expression-bank", tags)
            self.assertIn("expression::urban-development", tags)
            self.assertIn("priority::related", tags)

    @staticmethod
    def _read_guids(apkg: Path, extract_dir: Path) -> set[str]:
        extract_dir.mkdir()
        with zipfile.ZipFile(apkg) as archive:
            archive.extract("collection.anki2", extract_dir)
        connection = sqlite3.connect(extract_dir / "collection.anki2")
        try:
            return {row[0] for row in connection.execute("select guid from notes")}
        finally:
            connection.close()

    @staticmethod
    def _read_card_count(apkg: Path, extract_dir: Path) -> int:
        extract_dir.mkdir()
        with zipfile.ZipFile(apkg) as archive:
            archive.extract("collection.anki2", extract_dir)
        connection = sqlite3.connect(extract_dir / "collection.anki2")
        try:
            return connection.execute("select count(*) from cards").fetchone()[0]
        finally:
            connection.close()

    @staticmethod
    def _read_tags(apkg: Path, extract_dir: Path) -> set[str]:
        extract_dir.mkdir()
        with zipfile.ZipFile(apkg) as archive:
            archive.extract("collection.anki2", extract_dir)
        connection = sqlite3.connect(extract_dir / "collection.anki2")
        try:
            raw = connection.execute("select tags from notes").fetchone()[0]
            return set(raw.split())
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()
