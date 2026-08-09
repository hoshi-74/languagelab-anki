# LanguageLab：Codex + Anki 英语与日语工作流

这是一个仅在本机运行的 Anki 制卡项目，面向雅思英语和日语 N2。你把阅读摘录、写作/翻译、中文口语思路或听力材料交给 Codex，Codex 按 `schemas/card-batch.schema.json` 整理成批次 JSON；本项目再生成可导入 Anki 的 APKG、旧卡更新 TSV、批次摘要和人工检查报告。

项目不会使用 AnkiConnect、不会登录 AnkiWeb，也不会直接写入 Anki 数据库。

> 本项目是非官方学习工具，不隶属于 Anki 或 OpenAI。公开仓库不包含 Anki 程序、个人牌组、个人学习材料或生成结果；使用者需要自行安装 Anki 和 Python 3.10+。

## 获取项目

```bash
git clone https://github.com/hoshi-74/languagelab-anki.git
cd languagelab-anki
```

项目内置 `$languagelab-anki` Codex Skill。使用 Codex 打开仓库后，可以直接说“把这份雅思阅读做成 Anki 卡”或明确调用 `$languagelab-anki`。Skill 会读取场景提示词、生成批次、执行验证并交付 APKG。

## 每次使用

1. **开始前先打开 Anki 并同步。** 等待同步完成；如果出现“单向上传/下载”，先停下并确认方向。
2. 在当前 Codex 对话中提交文字或截图，并说明场景，例如：
   - “把这段雅思阅读中高亮的词和句子做卡。”
   - “修改这篇翻译，把真实错误做成纠错卡，把更好的表达做成语境表达卡。”
   - “把这些中文想法整理成雅思口语，再做成短语块和少量整句卡。”
   - “把这段 N2 阅读的词汇和语法做卡。”
   - “把这组听力表达做成听辨卡，其中两张需要听写。”
3. Codex 将材料整理为 `batches/<批次ID>.json`。截图中存在无法可靠判断的文字时，会先请求确认，不会导出。
4. 运行：

   ```powershell
   .\run.ps1 build .\batches\<批次ID>.json
   ```

5. 从 `output/<批次ID>/` 导入：
   - `LanguageLab-<批次ID>.apkg`：新卡和补充卡。
   - `update-*.tsv`：已有旧卡的更新；按报告中的字段顺序导入。
   - `summary.md`：卡片数量、预计首轮时间和导入清单。
   - `review.md`：需要人工确认的内容和风险提示。
6. **导入后再次点击 Anki 同步并等待完成。** 其他设备学习前也要先同步。

待完成：请导入 APKG/TSV，并在 Anki 中点击同步。

## iPad 上收集材料

当学习发生在 iPad、无法直接使用 Codex 时，在 ChatGPT 中使用 [iPad 交接提示词](prompts/ipad-chatgpt-handoff.md)。ChatGPT 负责识图、查资料、修改表达并返回“学习笔记 + Codex 交接包”；回到电脑后，将完整结果发给 Codex，由本项目检查本地重复项并生成 APKG。

iPad 端不判断 Anki GUID，也不生成更新 TSV。`eggrolls-JLPT10k-v3` 和 `TOEFL 绿宝书` 始终只读。

### 联想表达库

写作、翻译和高价值阅读材料会同时生成一组可迁移表达卡：题材词组、政府报告/议论文常用动词，以及可以替换内容反复使用的句型框架。正面显示完整中文语境，高亮当前需要表达的中文，并提供带空位的英文句框；翻面后比较参考句和可接受变体，不要求逐字复现唯一译文。它们带有 `expression-bank`、表达分组和记忆优先级标签。已经在核心纠错卡中直接测试的表达不会重复制卡；低价值联想只保留在学习笔记中。

阅读学习笔记与卡片背面使用同一套结构化字段：单词显示词性、常见义、固定搭配、词组、独立例句和本文语境；词组显示中文、用法、独立例句和本文语境；完整句子显示可能的生词及语法拆解。阅读识别卡正面只显示目标词或词组，词性、读音、TTS 和完整资料全部放在背面。主动表达填空卡先显示完整中文意图，高亮并划线需要翻译的中文片段，再显示英文挖空句，并在揭晓答案后触发 TTS。

口语卡正面显示完整中文意图并高亮当前训练重点，再在完整英文示范句中挖空一个可复用表达；翻面后朗读完整示范句，并显示自然替代表达、适用 Part 和表达功能。合理替代说法不算错误。

听力卡默认只要求听懂并复述大意，正面不会显示原文；只有确有拼写、语音边界或考试关键词价值时才出现输入框。背面记录听音重点、此前没听出的原因和具体声音线索，帮助下一次真正听出来。

日语 N2 语法卡在完整日语句中最小挖空一个语法形式，背面展示完整例句、接续、核心功能、本句意思和一条必要辨析。它不要求脱离语境从中文硬译语法形式。

## 首次安装

项目依赖只安装到当前目录的 `.venv`，不会全局安装：

```powershell
.\setup.ps1
.\run.ps1 self-check
```

`setup.ps1` 会依次查找 `CODEX_PYTHON`、系统 Python 和 Codex 桌面版附带的 Python，然后安装 `requirements.txt` 中锁定的依赖。

macOS 或 Linux：

```bash
chmod +x setup.sh run.sh
./setup.sh
./run.sh self-check
```

## 常用命令

```powershell
# 只检查批次，不生成文件
.\run.ps1 validate .\batches\example.json

# 生成 APKG、TSV 和报告
.\run.ps1 build .\batches\example.json

# 指定输出目录
.\run.ps1 build .\batches\example.json --output .\my-output

# 检查运行环境、固定 ID 和模板
.\run.ps1 self-check
```

## 批次约定

- `ocr.uncertain` 非空或 `ocr.status` 为 `needs_confirmation` 时，生成器拒绝导出。
- `action: create` 创建 LanguageLab 新卡。
- `action: supplement` 在无法安全修改旧卡时创建关联补充卡。
- `action: update_existing` 只用于允许更新的旧笔记，并生成 TSV；必须提供 GUID、笔记类型、完整字段快照和新增内容。
- 同一 `card.id` 会产生固定 GUID；重复生成同一批次不会制造重复卡。
- 所有内容按 UTF-8 保存。HTML 字段可以使用 `<b>`、`<br>` 和 `<details>`，但不允许远程脚本或外部字体。

完整字段定义见 [card-batch.schema.json](schemas/card-batch.schema.json)，可编辑示例见 [example.json](batches/example.json)。

## 牌组与主题

| 场景 | 牌组 | 主题 |
| --- | --- | --- |
| 英语阅读 | `LanguageLab::English::Reading` | 绿色 |
| 雅思写作 | `LanguageLab::English::Writing` | 蓝色 |
| 雅思口语 | `LanguageLab::English::Speaking` | 红色 |
| 英语听力 | `LanguageLab::English::Listening` | 红色 |
| 日语 N2 阅读 | `LanguageLab::Japanese::N2::Reading` | 靛蓝 |
| 日语 N2 语法 | `LanguageLab::Japanese::N2::Grammar` | 靛蓝 |
| 日语 N2 听力 | `LanguageLab::Japanese::N2::Listening` | 靛蓝 |

英语 TTS 默认使用跨设备兼容性更好的 `en_US`，日语 TTS 使用 `ja_JP`。卡片只使用 Anki 原生模板能力，优先兼容 AnkiMobile，同时保持桌面端和 Android 的基本兼容性。

### iPad 自动播放音频

- 写作表达卡不会在正面播放英文答案；翻到背面后，参考句使用 AnkiMobile 原生 TTS 自动朗读，并显示重播按钮。只有真实且答案明确的个人错误纠正卡保留输入核对。
- 口语卡和日语语法卡也只在翻面后朗读完整示范句；听力卡则在正面自动播放，翻面后可重播并核对原文。
- 在 AnkiMobile 牌组列表右上角打开齿轮，进入 `Preferences > Review`，开启 `Always Duck + Ignore Mute`；同时不要隐藏 `Audio Buttons`。
- 在 iPad 的 `设置 > 辅助功能 > 旁白 > 语音 > 声音` 中下载一个英语（美国）声音。不要选择 Siri 专用声音；安装声音后重启 AnkiMobile。
- 若不启用 `Always Duck + Ignore Mute`，iPad 静音开关处于静音时，TTS 不会自动播放。

## 旧卡更新安全规则

- `eggrolls-JLPT10k-v3` 和 `TOEFL 绿宝书` 是只读保护词库，生成器禁止为它们输出更新 TSV。命中其中已有词条时创建关联的 LanguageLab 补充卡。
- `英语单词模板(vocab配色)`：补充英语例句、中文例句或 `vocabulary扩展`。
- 生成器以 `existing_note.fields` 的完整快照为基准合并，绝不会用空值覆盖已有字段。无法识别的笔记类型或不安全的字段映射会中止该条更新，并写入 `review.md`。
- 更新前建议用 Anki 导出一份备份。TSV 只负责准备允许更新的六级词卡数据，导入映射和最终确认仍由用户在 Anki 中完成。

## 项目目录

```text
batches/       结构化输入批次
languagelab/   本地生成器
prompts/       各学习场景提示词
schemas/       JSON Schema
templates/     Anki HTML/CSS 模板
tests/         自动化测试
output/        生成结果（不提交）
```

公开仓库只包含匿名示例 `batches/example.json`。个人批次、学习笔记、输出文件、便携版 Anki、本地虚拟环境以及早期原始 TXT 均由 `.gitignore` 排除。

## 开源许可

项目代码与项目自有模板使用 [MIT License](LICENSE)。Anki、词典内容和用户自行导入的牌组仍受各自许可证约束。
