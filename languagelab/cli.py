from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import genanki

from . import __version__
from .config import DECK_IDS, MODEL_SPECS, SYNC_REMINDER
from .generator import ROOT, build_batch
from .validation import BatchValidationError, validate_batch


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="languagelab", description="本地 Anki 制卡与旧卡更新文件生成器")
    parser.add_argument("--version", action="version", version=f"LanguageLab {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate", help="检查批次 JSON，但不生成文件")
    validate.add_argument("batch", type=Path)

    build = sub.add_parser("build", help="生成 APKG、TSV 和报告")
    build.add_argument("batch", type=Path)
    build.add_argument("--output", type=Path, default=ROOT / "output")

    sub.add_parser("self-check", help="检查依赖、固定 ID 与模板文件")
    return parser


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _self_check() -> int:
    required_templates = {
        "common.css",
        "basic_front.html", "basic_back.html", "cloze_front.html", "cloze_back.html",
        "typing_front.html", "typing_back.html", "listening_front.html", "listening_back.html",
        "writing_front.html", "writing_back.html",
        "speaking_front.html", "speaking_back.html", "grammar_front.html", "grammar_back.html",
    }
    missing = sorted(name for name in required_templates if not (ROOT / "templates" / name).is_file())
    ids = list(DECK_IDS.values()) + [spec.model_id for spec in MODEL_SPECS.values()]
    if missing:
        print("缺少模板：" + ", ".join(missing), file=sys.stderr)
        return 1
    if len(ids) != len(set(ids)):
        print("固定 deck/model ID 存在重复。", file=sys.stderr)
        return 1
    print(f"LanguageLab {__version__}")
    print(f"genanki: {getattr(genanki, '__version__', '已安装')}")
    print(f"牌组：{len(DECK_IDS)}；笔记类型：{len(MODEL_SPECS)}；模板：{len(required_templates)}")
    print("检查通过。")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "self-check":
            return _self_check()
        if args.command == "validate":
            errors = validate_batch(_load(args.batch))
            if errors:
                print("批次检查失败：", file=sys.stderr)
                for error in errors:
                    print(f"- {error}", file=sys.stderr)
                return 1
            print(f"检查通过：{args.batch}")
            return 0
        manifest = build_batch(args.batch.resolve(), args.output.resolve())
        print(f"已生成批次：{manifest['batch_id']}")
        print(f"新卡/补充卡：{manifest['new_cards']}；旧卡更新：{manifest['existing_updates']}")
        for filename in manifest["files"]:
            print(f"- {filename}")
        if manifest["blocked_items"]:
            print(f"有 {len(manifest['blocked_items'])} 项被阻止，请查看 review.md。")
        print(SYNC_REMINDER)
        return 0
    except FileNotFoundError as exc:
        print(f"文件不存在：{exc.filename}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as exc:
        print(f"JSON 格式错误：第 {exc.lineno} 行，第 {exc.colno} 列：{exc.msg}", file=sys.stderr)
        return 1
    except BatchValidationError as exc:
        print(f"批次无法导出：\n{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
