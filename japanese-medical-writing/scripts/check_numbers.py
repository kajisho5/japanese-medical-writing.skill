#!/usr/bin/env python3
"""数値の整合チェック（Python 標準ライブラリのみ）。

1. 抄録（和文・英文）に出てくる数値が本文（抄録・文献以外の全節。Markdown の表を
   含む）に一度も出てこない場合を ERROR とする。抄録で数値を書き換えた・足した、
   英文抄録だけに数値がある、符号（−）が落ちた、といった不一致を見つける。
2. 「12/48例（25.0%）」「12例/48例（25%）」「48例中12例（25.0%）」「12 of 48 (25%)」形式の割合を再計算し、記載の小数桁で
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
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _textio import body_start, heading_level, read_manuscript  # noqa: E402

ABSTRACT = re.compile(r"^#{1,6}\s+(要旨|抄録|和文抄録|英文抄録|Abstract|Summary)\b", re.I)
REFS = re.compile(r"^#{1,6}\s+(文献|引用文献|参考文献|References)\s*$", re.I)
UNIT = r"(?:例|名|人|件|眼|肢|歯|病変|patients|cases)"
FRAC = re.compile(r"(\d+)\s*" + UNIT + r"?\s*(?:/|of)\s*(\d+)\s*" + UNIT + r"?\s*[（(]\s*(\d+(?:\.\d+)?)\s*%")
FRAC_JA = re.compile(r"(\d+)\s*" + UNIT + r"?\s*中\s*(\d+)\s*" + UNIT + r"?\s*[（(]\s*(\d+(?:\.\d+)?)\s*%")
# 符号付きの数値も区別する（−0.5 と 0.5 を同一視しない）。範囲の「–」「〜」は符号として扱わない。
# 「−」は数字の直後でなければ符号（「は−1.5」も負の数）。半角「-」は英数字の直後でなければ符号
# （「1.2-3.4」は範囲、「COVID-19」は名称）。
# 「,」は直後がちょうど3桁のときだけ桁区切り（「1,234」）。「0.45,0.89」は 0.45 と 0.89 の2つ
NUM = re.compile(r"((?<![0-9.])−|(?<![0-9A-Za-z_.])-)?(?<![0-9A-Za-z_.])(\d{1,3}(?:,\d{3})+(?:\.\d+)?(?![\d,])|\d+(?:\.\d+)?)(?![0-9A-Za-z_])")


def norm(n: str) -> str:
    n = n.replace(",", "").replace("−", "-")
    if "." in n:
        n = n.rstrip("0").rstrip(".") or "0"
    return n


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file")
    ap.add_argument("--ignore", default="", help="照合しない数値（カンマ区切り）")
    a = ap.parse_args()
    ignore = {norm(x.strip()) for x in a.ignore.split(",") if x.strip()}

    # 全角数字・全角記号を半角にそろえて比べる（「４２例」と「42例」は同じ）
    text = unicodedata.normalize("NFKC", read_manuscript(a.file))
    text = re.sub(r"<!--.*?-->", lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S)
    text = re.sub(r"【(?:要(?:確認|文献)|二次情報)[^】]*】", "", text)
    # 「95% 信頼区間」の 95 などは結果の数値ではないので照合しない
    text = re.sub(r"(?<![0-9A-Za-z_.])(?:90|95|99)\s*%\s*(?=CI|信頼区間|信用区間|confidence)", " ", text)

    errors = 0
    for i, line in enumerate(text.split("\n"), 1):
        found = [(int(m.group(1)), int(m.group(2)), m.group(3), m.group(0)) for m in FRAC.finditer(line)]
        found += [(int(m.group(2)), int(m.group(1)), m.group(3), m.group(0)) for m in FRAC_JA.finditer(line)]
        for num, den, pct, whole in found:
            if den == 0:
                print(f"ERROR L{i}: 分母が0「{whole}」")
                errors += 1
                continue
            digits = len(pct.split(".")[1]) if "." in pct else 0
            calc = round(num / den * 100 + 1e-9, digits)
            if abs(calc - float(pct)) > 10 ** (-digits) / 2 + 1e-9:
                print(f"ERROR L{i}: 割合が合わない {num}/{den} = {calc:.{digits}f}% だが {pct}% と記載")
                errors += 1

    mode, abs_level = "body", 0
    abstract_nums: list[tuple[str, int]] = []
    body: set[str] = set()
    lines = text.split("\n")
    start, flat = body_start(lines, re.compile(ABSTRACT.pattern + "|" + REFS.pattern[1:], re.I))
    if flat and start < len(lines):
        print("INFO: 「## 」の見出しがないため、最初の「# 」見出しを表題、以降の「# 」見出しを節として扱った")
    for i, line in enumerate(lines, 1):
        lvl = heading_level(line)
        if lvl:
            if mode == "abs" and lvl > abs_level:
                continue  # 構造化抄録の小見出し（### 目的 / ### 結果）は抄録のうち
            mode = "abs" if ABSTRACT.match(line) else "refs" if REFS.match(line) else "body"
            abs_level = lvl
            continue
        if i - 1 < start or mode == "refs":
            continue
        nums = [norm((m.group(1) or "") + m.group(2)) for m in NUM.finditer(line)]
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
