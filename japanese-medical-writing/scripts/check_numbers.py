#!/usr/bin/env python3
"""数値の整合チェック（Python 標準ライブラリのみ）。

1. 抄録（和文・英文）に出てくる数値が本文（抄録・文献以外の全節。Markdown の表を
   含む）に一度も出てこない場合を ERROR とする。抄録で数値を書き換えた・足した、
   英文抄録だけに数値がある、といった不一致を見つける。
2. 「12/48例（25.0%）」「12 of 48 (25%)」形式の割合を再計算し、記載の小数桁で
   丸めた値と一致しなければ ERROR とする（全節が対象）。

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
FRAC = re.compile(r"(\d+)\s*(?:/|of)\s*(\d+)\s*(?:例|名|人|件|眼|肢|patients|cases)?\s*[（(]\s*(\d+(?:\.\d+)?)\s*%")
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

    errors = 0
    for i, line in enumerate(text.split("\n"), 1):
        for m in FRAC.finditer(line):
            num, den, pct = int(m.group(1)), int(m.group(2)), m.group(3)
            if den == 0:
                print(f"ERROR L{i}: 分母が0「{m.group(0)}」")
                errors += 1
                continue
            digits = len(pct.split(".")[1]) if "." in pct else 0
            calc = round(num / den * 100 + 1e-9, digits)
            if abs(calc - float(pct)) > 10 ** (-digits) / 2 + 1e-9:
                print(f"ERROR L{i}: 割合が合わない {num}/{den} = {calc:.{digits}f}% だが {pct}% と記載")
                errors += 1

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
        print(f"\nERROR {errors} 件")
        sys.exit(1 if errors else 0)
    seen = set()
    for n, ln in abstract_nums:
        if n in ignore or n in body or (n, ln) in seen:
            continue
        seen.add((n, ln))
        print(f"ERROR L{ln}: 抄録の数値 {n} が本文・表に見当たらない")
        errors += 1
    print(f"\n抄録の数値 {len(abstract_nums)} 個 / ERROR {errors} 件（割合の不一致を含む）")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
