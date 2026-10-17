#!/usr/bin/env python3
"""抄録（和文・英文）と本文の数値の突き合わせ（Python 標準ライブラリのみ）。

抄録に出てくる数値が本文（抄録・文献以外の全節。Markdown の表を含む）に
一度も出てこない場合を ERROR とする。抄録で数値を書き換えた・足した、
英文抄録だけに数値がある、といった不一致を見つけるためのもの。

使い方:
  python3 check_numbers.py manuscript.md
  python3 check_numbers.py --ignore 95,2024 manuscript.md   # 照合しない数値

数値が本文にあることは「正しい」ことを意味しない（同じ数が別の意味で出ている
可能性がある）。最終確認は人が台帳と照らして行う。ERROR があれば終了コード 1。
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ABSTRACT = re.compile(r"^#{1,6}\s*(要旨|抄録|和文抄録|英文抄録|Abstract|Summary)\b", re.I)
REFS = re.compile(r"^#{1,6}\s*(文献|引用文献|参考文献|References)\s*$", re.I)
NUM = re.compile(r"(?<![0-9A-Za-z_.])(\d+(?:[.,]\d+)*)(?![0-9A-Za-z_])")


def norm(n: str) -> str:
    n = n.replace(",", "")
    if "." in n:
        n = n.rstrip("0").rstrip(".") or "0"
    return n


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file")
    ap.add_argument("--ignore", default="", help="照合しない数値（カンマ区切り）")
    a = ap.parse_args()
    ignore = {norm(x.strip()) for x in a.ignore.split(",") if x.strip()}

    text = Path(a.file).read_text(encoding="utf-8")
    text = re.sub(r"<!--.*?-->", lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S)
    text = re.sub(r"【要(確認|文献)[^】]*】", "", text)

    mode, started = "body", False
    abstract_nums: list[tuple[str, int]] = []
    body: set[str] = set()
    for i, line in enumerate(text.split("\n"), 1):
        if line.startswith("#"):
            if line.startswith("## "):
                started = True
            mode = "abs" if ABSTRACT.match(line) else "refs" if REFS.match(line) else "body"
            continue
        if not started or mode == "refs":
            continue
        nums = [norm(m.group(1)) for m in NUM.finditer(line)]
        if mode == "abs":
            abstract_nums += [(n, i) for n in nums]
        else:
            body.update(nums)

    if not abstract_nums:
        print("INFO: 抄録の見出し（要旨/抄録/Abstract）が見つからないか、抄録に数値がない")
        sys.exit(0)
    errors, seen = 0, set()
    for n, ln in abstract_nums:
        if n in ignore or n in body or (n, ln) in seen:
            continue
        seen.add((n, ln))
        print(f"ERROR L{ln}: 抄録の数値 {n} が本文・表に見当たらない")
        errors += 1
    print(f"\n抄録の数値 {len(abstract_nums)} 個 / 本文に無いもの {errors} 個")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
