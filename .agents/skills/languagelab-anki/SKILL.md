---
name: languagelab-anki
description: Create local Anki APKG packages and structured study notes from English IELTS or Japanese JLPT N2 reading, writing, speaking, listening, translation, correction, pasted text, screenshots, or iPad ChatGPT handoff JSON. Use when Codex needs to analyze language-learning material, design atomic LanguageLab cards, validate a card batch, build Anki packages, or revise this repository's prompts and templates.
---

# LanguageLab Anki

Use this repository's validated workflow to turn understood language-learning material into importable Anki packages. Keep the process local and preserve source context.

## Workflow

1. Remind the user to sync Anki before starting a new batch.
2. Identify the language and scenario. For screenshots, preserve raw OCR separately from cleaned text and stop on unresolved text.
3. Read `prompts/batch-output-contract.md` and the matching scenario prompt:
   - `prompts/english-reading.md`
   - `prompts/ielts-writing.md`
   - `prompts/ielts-speaking.md`
   - `prompts/listening.md`
   - `prompts/japanese-n2.md`
4. Read `schemas/card-batch.schema.json` before writing `batches/<batch-id>.json`.
5. Keep cards atomic. Test one recall target per card and place structured explanation on the back.
6. Run `./run.ps1 validate ./batches/<batch-id>.json` on Windows or `./run.sh validate ./batches/<batch-id>.json` on macOS/Linux.
7. Resolve validation failures, then run the matching `build` command.
8. Inspect `summary.md`, `review.md`, `study-notes.md`, and the generated APKG before delivery.
9. End every delivery with: `待完成：请导入 APKG/TSV，并在 Anki 中点击同步。`

## Card Decisions

- Prefer recognition cards for reading. Add production cards only for expressions with real active-use value.
- Use contextual production for writing: complete Chinese intent, highlighted focus, constrained English frame, model sentence, and accepted variants.
- Use speaking cloze cards for one reusable spoken chunk. Preserve natural alternatives and the sentence function.
- Use listening comprehension by default. Enable dictation only when exact sound-to-spelling recall has a stated reason.
- Use Japanese grammar cloze only in a complete Japanese sentence. Record connection, function, and one useful contrast.
- Do not manufacture synonyms, antonyms, roots, sound features, or source links merely to fill fields.

## Safety

- Do not use AnkiConnect, AnkiWeb credentials, browser automation, or direct writes to Anki databases.
- Never overwrite or clear existing note fields.
- Treat `eggrolls-JLPT10k-v3` and `TOEFL 绿宝书` as read-only. Create LanguageLab supplement cards when needed.
- Block export while OCR uncertainties remain.
- Use deterministic card IDs so repeated builds update rather than duplicate LanguageLab notes.
- Do not include personal batches, notes, outputs, Anki binaries, or local environments in repository releases.
