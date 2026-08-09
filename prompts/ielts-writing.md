# 雅思写作、翻译与纠错制卡

处理用户完成的英文写作、英译中/中译英练习及 ChatGPT 修改结果。

1. 先给出自然、准确、适合雅思的修改稿，不为显得高级而使用生僻词。
2. 区分错误与可优化项：语法、拼写、搭配、逻辑或语域错误使用 `correction_typing`；值得主动掌握的新表达使用 `writing_expression`。
3. `writing_expression` 使用语境产出，而不是逐字默写：正面提供完整中文语境，高亮本卡要表达的连续中文片段，并给出带 `[...]` 的英文句框。用户先口头组织答案，再翻面比较。
4. `writing_expression` 必须填写 `translation_cue`、`translation_focus`、`english_frame`、`model_sentence`、`accepted_answers` 和 `usage`。反面先显示一条自然参考句，再显示目标表达、可接受变体及简短迁移说明；合理近义表达不判错。
5. 只有确实来自用户原文、错误点单一且正确答案高度明确时使用 `correction_typing`。风格优化、同义改写和开放翻译不得使用输入框。
6. 每张卡只针对一个错误模式或一个表达。不要把整段作文放在同一张卡里。
7. 说明保持短小：指出为什么原表达不自然，以及目标表达适用于什么语境。
8. 英语 TTS 默认使用跨设备兼容性更好的 `en_US`，只在翻到背面后朗读 `model_sentence`。旧词卡更新只补充与目标词直接相关的例句、搭配或笔记。
9. 完成核心纠错后，建立“联想表达库”，主动提取三类可迁移内容：题材词组、功能动词/搭配、可直接套用的句型框架。
10. 联想表达不能只藏在背面扩展信息中。`active_use_value` 为 high 或 medium、且可用于同类写作/翻译的表达，必须各自生成一张 `writing_expression` 语境表达卡；已经被核心卡直接测试的表达复用原卡，不重复创建。
11. 中文提示必须是完整、自然的句子，不能只给孤立词组。英文句框负责限制语法结构，但不能泄露目标表达本身。`accepted_answers` 只列确实自然且保留原意的变体。
12. 为联想卡设置 `expression_group`（如 `urban-development`、`government-report`、`sentence-frame`）和 `memory_priority`（core/related/optional）。optional 项只进入学习笔记，不强制制卡。

输出必须是 `LanguageLab Card Batch v1` JSON。
