# LanguageLab Card Batch v1 输出约定

生成批次前必须读取 `schemas/card-batch.schema.json` 和目标场景提示词。

- `batch_id` 使用稳定、可读且唯一的英文标识，例如 `2026-08-09-ielts-reading-01`。
- `source.raw_text` 原样保存用户输入或第一阶段 OCR；`source.clean_text` 保存清理结果。
- 截图无疑点时使用 `ocr.status: confirmed`；有疑点时使用 `needs_confirmation` 并列出每个疑点。此状态下不要执行构建。
- 卡片 `id` 基于“语言 + 场景 + 核心目标 + 语境”稳定命名。同一学习项目再次出现时沿用 ID。
- 新卡使用 `create`；`eggrolls-JLPT10k-v3` 与 `TOEFL 绿宝书` 命中时必须使用 `supplement`；只有 `英语单词模板(vocab配色)` 可在确认 GUID 和完整字段快照后使用 `update_existing`。
- 卡片正文允许简单 HTML，但不得加入脚本、远程字体、追踪代码或依赖桌面端插件的元素。
- 阅读卡必须填写 `note_format`。`word` 使用词性、常见义、固定搭配、词组、独立例句和本文原句字段；`phrase` 使用中文、用法、独立例句和本文语境字段；`sentence` 使用难词清单与 `grammar_breakdown`。独立例句不得照抄本文原句。
- 正面只测试当前语境中的一个核心含义；结构化笔记全部放在背面。不要要求用户一次回忆背面的整组资料。
- `english_context_cloze` 必须填写 `translation_cue` 和 `translation_focus`：正面上方显示完整中文意图，并高亮、划线与英文挖空对应的连续中文片段；下方显示英文挖空句，答案和用法只在反面出现。
- `writing_expression` 是开放但受限的语境产出卡，不使用输入框。必须填写完整中文 `translation_cue`、连续高亮片段 `translation_focus`、含 `[...]` 的 `english_frame`、完整 `model_sentence`、数组 `accepted_answers` 和 `usage`。反面展示参考表达与合理变体，不能把唯一译文当作唯一正确答案。
- `correction_typing` 只用于用户原文中真实、单一且答案明确的错误；风格优化、近义改写和开放翻译改用 `writing_expression`。
- `speaking_cloze` 必须提供完整中文意图与高亮重点、完整示范句、自然替代表达、口语用法、雅思 Part 和表达功能。正面只挖空一个可复用表达，背面朗读完整示范句；自然替代说法不判错。
- `japanese_grammar_cloze` 必须填写接续、核心功能和易混辨析数组。正面在完整日语句中最小挖空，背面展示完整句、接续、功能与必要辨析。
- 听力卡必须填写听音重点、未听出原因、声音线索数组和布尔值 `dictation`。听写为 true 时必须说明具体理由；普通听辨不输入文字。
- 来源应优先选择词典、考试机构、教材或权威语法资料；保存 URL 与检索日期，不复制长段原文。
- 写作/翻译批次必须检查联想表达：值得主动使用的题材词组、功能动词和句型框架各自成为原子化语境表达卡，并填写 `expression_group` 与 `memory_priority`；已被核心卡直接测试的表达不得重复。
- 每批可以包含全部适合当天学习的新卡，不设置数量上限；仍需避免重复、无意义扩展和非原子卡。
