from __future__ import annotations

from dataclasses import dataclass


SYNC_REMINDER = "待完成：请导入 APKG/TSV，并在 Anki 中点击同步。"


DECK_IDS = {
    "LanguageLab::English::Reading": 1802408101,
    "LanguageLab::English::Writing": 1802408102,
    "LanguageLab::English::Speaking": 1802408103,
    "LanguageLab::English::Listening": 1802408104,
    "LanguageLab::Japanese::N2::Reading": 1802408105,
    "LanguageLab::Japanese::N2::Grammar": 1802408106,
    "LanguageLab::Japanese::N2::Listening": 1802408107,
}


@dataclass(frozen=True)
class ModelSpec:
    model_id: int
    name: str
    family: str
    header: str
    theme: str
    tts_language: str = ""
    template_name: str = ""


MODEL_SPECS = {
    "english_reading": ModelSpec(
        1802408201, "LanguageLab v1 - English Reading", "basic", "IELTS Reading", "green", "en_US"
    ),
    "english_context_cloze": ModelSpec(
        1802408202, "LanguageLab v1 - English Context Cloze", "cloze", "IELTS Reading", "green", "en_US"
    ),
    "japanese_reading": ModelSpec(
        1802408203, "LanguageLab v1 - Japanese N2 Reading", "basic", "JLPT N2 Reading", "indigo", "ja_JP"
    ),
    "japanese_grammar_cloze": ModelSpec(
        1802408204, "LanguageLab v1 - Japanese N2 Grammar", "cloze", "JLPT N2 Grammar", "indigo", "ja_JP", "grammar"
    ),
    "writing_expression": ModelSpec(
        1802408205, "LanguageLab v1 - IELTS Writing", "typing", "IELTS Writing", "blue", "en_US", "writing"
    ),
    "correction_typing": ModelSpec(
        1802408206, "LanguageLab v1 - Error Correction", "typing", "Error Correction", "gray", "en_US"
    ),
    "speaking_cloze": ModelSpec(
        1802408207, "LanguageLab v1 - IELTS Speaking", "cloze", "IELTS Speaking", "red", "en_US", "speaking"
    ),
    "english_listening": ModelSpec(
        1802408208, "LanguageLab v1 - English Listening", "listening", "IELTS Listening", "red", "en_US"
    ),
    "japanese_listening": ModelSpec(
        1802408209, "LanguageLab v1 - Japanese N2 Listening", "listening", "JLPT N2 Listening", "indigo", "ja_JP"
    ),
}


CARD_TYPE_TO_DECKS = {
    "english_reading": {"LanguageLab::English::Reading"},
    "english_context_cloze": {"LanguageLab::English::Reading"},
    "japanese_reading": {"LanguageLab::Japanese::N2::Reading"},
    "japanese_grammar_cloze": {"LanguageLab::Japanese::N2::Grammar"},
    "writing_expression": {"LanguageLab::English::Writing"},
    "correction_typing": {"LanguageLab::English::Writing"},
    "speaking_cloze": {"LanguageLab::English::Speaking"},
    "english_listening": {"LanguageLab::English::Listening"},
    "japanese_listening": {"LanguageLab::Japanese::N2::Listening"},
}


PROTECTED_NOTE_TYPES = frozenset({"eggrolls-JLPT10k-v3", "TOEFL 绿宝书"})


EXISTING_NOTE_FIELDS = {
    "英语单词模板(vocab配色)": [
        "英语单词", "英美音标", "中文释义", "英语例句", "中文例句", "vocabulary简明",
        "vocabulary扩展", "柯林斯星级", "柯林斯解释", "英语发音",
    ],
}
