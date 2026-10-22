#!/usr/bin/env python3
"""本文の引用番号と文献リストの対応チェック（Python 標準ライブラリのみ）。

対応する本文中の引用形式:
  [1]  [1,3]  [2–5]   ^1^  ^1,2^   和文字の直後の 1)  3,4)  5–7)
文献リストは見出し「文献 / 引用文献 / 参考文献 / References」以降の、
行頭が「1)」「1.」「[1]」の行。最初の「## 」見出しより前（表題・著者・所属）は無視する。

あわせて図表番号を確認する：本文で「表1」「図2」「Table 3」「Fig. 1」と参照された番号と、
行頭の図表タイトル（例「表1　患者背景」「**図2** 経過」「Table 1.」）の対応、
初出順、欠番。補足資料（表S1 等）は対象外。

ERROR が1件でもあれば終了コード 1。
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _textio import read_manuscript  # noqa: E402

REF_HEAD = re.compile(r"^#{1,6}\s*(文献|引用文献|参考文献|References)\s*$", re.I)
ENTRY = re.compile(r"^\s*(?:\[(\d+)\]|(\d+)[).．.])\s+\S")
CITES = [
    re.compile(r"\[(\d+(?:\s*[,，–\-~〜]\s*\d+)*)\]"),
    re.compile(r"\^(\d+(?:\s*[,，–\-~〜]\s*\d+)*)\^"),
    re.compile(r"(?<=[぀-ヿ一-鿿）」。、])(\d+(?:\s*[,，–\-~〜]\s*\d+)*)\)"),
]


FIG_REF = re.compile(r"(表|図|Table|Fig\.?|Figure)\s*(\d+)", re.I)
FIG_CAP = re.compile(r"^\s*(?:\*\*|#{1,6}\s*)?(表|図|Table|Fig\.?|Figure)\s*(\d+)(?:\*\*)?(?:[\s　.:：]|$)", re.I)


def kind(word: str) -> str:
    return "表" if word.lower().startswith(("表", "table")) else "図"


def check_figures(lines: list[str]) -> int:
    errors = 0
    refs: dict[str, list[tuple[int, int]]] = {"表": [], "図": []}
    caps: dict[str, dict[int, int]] = {"表": {}, "図": {}}
    started = False
    for i, line in enumerate(lines, 1):
        if line.startswith("## "):
            started = True
        if not started or REF_HEAD.match(line):
            continue
        cm = FIG_CAP.match(line)
        if cm:
            caps[kind(cm.group(1))][int(cm.group(2))] = i
            rest = line[cm.end():]
        else:
            rest = line
        for m in FIG_REF.finditer(rest):
            refs[kind(m.group(1))].append((int(m.group(2)), i))
    for k in ("表", "図"):
        cited = {n for n, _ in refs[k]}
        if caps[k]:
            for n, ln in refs[k]:
                if n not in caps[k]:
                    print(f"ERROR L{ln}: 本文の{k}{n}に対応するタイトル行がない")
                    errors += 1
        for n, ln in sorted(caps[k].items()):
            if n not in cited:
                print(f"ERROR L{ln}: {k}{n}が本文で参照されていない")
                errors += 1
        mx = 0
        for n, ln in refs[k]:
            if n > mx:
                if n != mx + 1:
                    print(f"WARN  L{ln}: {k}{n}の初出が番号順でない（直前までの最大は {mx}）")
                mx = n
        allnums = cited | set(caps[k])
        if allnums:
            missing = [n for n in range(1, max(allnums) + 1) if n not in allnums]
            if missing:
                print(f"ERROR: {k}に欠番 {missing}")
                errors += 1
        if refs[k] and not caps[k]:
            print(f"INFO: {k}を参照しているがタイトル行が見つからない（別ファイルなら想定どおり）")
    return errors


def expand(spec: str) -> list[int]:
    nums: list[int] = []
    for part in re.split(r"\s*[,，]\s*", spec):
        m = re.match(r"(\d+)\s*[–\-~〜]\s*(\d+)$", part)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            nums.extend(range(a, b + 1) if a <= b else [a, b])
        elif part.isdigit():
            nums.append(int(part))
    return nums


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file")
    a = ap.parse_args()
    text = read_manuscript(a.file)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    lines = text.split("\n")

    started, in_refs = False, False
    order: list[tuple[int, int]] = []  # (番号, 行)
    styles: set[str] = set()
    entries: dict[int, int] = {}
    for i, line in enumerate(lines, 1):
        if line.startswith("## "):
            started = True
        if line.startswith("#"):
            in_refs = bool(REF_HEAD.match(line))
            continue
        if not started:
            continue
        if in_refs:
            m = ENTRY.match(line)
            if m:
                n = int(m.group(1) or m.group(2))
                if n in entries:
                    print(f"ERROR L{i}: 文献番号 {n} が重複（L{entries[n]}）")
                entries[n] = i
            continue
        found = sorted((m.start(), m.group(1)) for pat in CITES for m in pat.finditer(line))
        for idx, pat in enumerate(CITES):
            if pat.search(line):
                styles.add(("[n]", "^n^（上付き）", "n)")[idx])
        for _, spec in found:
            for n in expand(spec):
                order.append((n, i))

    errors = 0
    cited = {n for n, _ in order}
    if len(styles) > 1:
        print(f"WARN: 引用番号の書き方が混在している（{'、'.join(sorted(styles))}）。誌規定の形式に統一する")
    if not entries:
        if cited:
            print(f"ERROR: 本文に引用番号 {sorted(cited)} があるが文献リストが見つからない（見出し「文献」等と行頭番号を確認）")
            errors += 1
        else:
            print("INFO: 引用番号も文献リストもない（文献未作成の下書きなら想定どおり。【要文献】の件数は lint_ja.py で確認）")
    for n, ln in order:
        if entries and n not in entries:
            print(f"ERROR L{ln}: 本文の引用 {n} が文献リストにない")
            errors += 1
    for n, ln in sorted(entries.items()):
        if n not in cited:
            print(f"ERROR L{ln}: 文献 {n} が本文で引用されていない")
            errors += 1
    # 出現順チェック：新出番号は「これまでの最大+1」であるべき
    seen_max = 0
    for n, ln in order:
        if n > seen_max:
            if n != seen_max + 1:
                print(f"WARN  L{ln}: 引用 {n} の初出が番号順でない（直前までの最大は {seen_max}）")
            seen_max = n
    if entries:
        expect = list(range(1, max(entries) + 1))
        missing = [n for n in expect if n not in entries]
        if missing:
            print(f"ERROR: 文献リストに欠番 {missing}")
            errors += 1
    errors += check_figures(lines)
    print(f"\n本文の引用 {len(cited)} 種 / 文献リスト {len(entries)} 件 / ERROR {errors} 件（図表を含む）")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
