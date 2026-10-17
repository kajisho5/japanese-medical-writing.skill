#!/usr/bin/env python3
"""医学用語の点検（Python 標準ライブラリのみ・通信なし）。

assets/term-changes.json の一覧をもとに、次を検出する。
  - 改称・変更された旧用語（例：痴呆 → 認知症）。出典と年を表示する
  - 診断基準の版によって名称が異なる用語（例：DSM-5 と DSM-5-TR）。使った基準に合わせるよう促す
  - 同じ原稿の中での表記ゆれ（例：頸部と頚部）

辞書に載っていない用語の正しさは判定できない。最終的には `references/terminology.md` の典拠
（日本医学会 医学用語辞典、各学会の用語集、ICD、JAN 等）で確認すること。

使い方:
  python3 check_terms.py manuscript.md
  python3 check_terms.py --no-echo manuscript.md

旧用語（level=error）があれば終了コード 1。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _textio import read_manuscript  # noqa: E402

DATA = Path(__file__).resolve().parent.parent / "assets" / "term-changes.json"
REF_HEAD = re.compile(r"^#{1,6}\s*(文献|引用文献|参考文献|References)\s*$", re.I)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file")
    ap.add_argument("--no-echo", action="store_true")
    a = ap.parse_args()
    data = json.loads(DATA.read_text(encoding="utf-8"))
    text = read_manuscript(a.file)
    text = re.sub(r"<!--.*?-->", lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S)

    lines, in_refs = [], False
    for i, line in enumerate(text.split("\n"), 1):
        if re.match(r"^#{1,6}\s", line):
            in_refs = bool(REF_HEAD.match(line))
            continue
        if not in_refs:  # 文献の題名にある旧用語は原典どおりなので対象外
            lines.append((i, line))

    errors = warns = 0
    for t in data["changes"]:
        pat = re.compile(t["pattern"])
        allow = re.compile(t["allow"]) if t.get("allow") else None
        for i, line in lines:
            for m in pat.finditer(line):
                ctx = line[max(0, m.start() - 12):m.end() + 12]
                if allow and allow.search(ctx):
                    continue
                level = t.get("level", "warn")
                if level == "error":
                    errors += 1
                else:
                    warns += 1
                shown = "" if a.no_echo else f"「{m.group(0)}」"
                print(f"{'ERROR' if level == 'error' else 'WARN '} L{i}: {shown}→ {t['recommended']}（{t['note']}。出典：{t['source']}）")
                break

    for group in data.get("variants", []):
        used = {}
        for i, line in lines:
            for form in group["forms"]:
                if form in line:
                    used.setdefault(form, i)
        if len(used) > 1:
            warns += 1
            forms = "、".join(f"{f}（L{n}）" for f, n in used.items())
            print(f"WARN : 表記ゆれ {forms} → どれかに統一（{group['note']}）")

    print(f"\n用語：旧用語など {errors} 件 / 確認を勧めるもの {warns} 件")
    print("※ 辞書にない用語は判定できない。`references/terminology.md` の典拠で確認すること")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
