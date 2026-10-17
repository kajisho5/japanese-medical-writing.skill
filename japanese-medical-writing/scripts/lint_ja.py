#!/usr/bin/env python3
"""和文医学論文の表記・文体 lint（Python 標準ライブラリのみ）。

使い方:
  python3 lint_ja.py manuscript.md            # チェック
  python3 lint_ja.py --count abstract.md      # 字数カウント（節ごと）
  python3 lint_ja.py --count --section 要旨 --limit 600 ms.md   # 要旨の字数と上限との差
  python3 lint_ja.py --allow-desu reply.md    # です・ます調を許可（査読回答など）
  python3 lint_ja.py --draft manuscript.md    # 下書き段階：未解決マーカーは件数集計のみ（ERROR扱いしない）
  python3 lint_ja.py --known WORD,WORD ms.md  # 定義不要略語を追加
  python3 lint_ja.py --no-echo ms.md          # 原稿の文面を出力に含めない（機密原稿用）

ERROR が1件でもあれば終了コード 1。
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _textio import read_manuscript  # noqa: E402

KNOWN_ABBR = {
    # 一般に定義不要とされることが多いもの（誌規定で要確認）
    "DNA", "RNA", "CT", "MRI", "PET", "HIV", "PCR", "ECG", "ICU", "BMI",
    "SD", "IQR", "CI", "OR", "HR", "RR", "SE", "ID", "AI", "WHO", "SI",
    "URL", "DOI", "PMID", "ISBN", "ISSN", "USA", "UK", "JP", "MD", "PhD",
    # 報告ガイドライン・機関名
    "ICMJE", "CONSORT", "STROBE", "PRISMA", "CARE", "STARD", "TRIPOD",
    "SPIRIT", "COREQ", "SRQR", "SQUIRE", "CHEERS", "ARRIVE", "TIDIER",
    "EQUATOR", "UMIN", "CTR", "JRCT", "GCP", "COI", "MESH", "NLM",
    "PUBMED", "MEDLINE", "EMBASE", "CINAHL", "CRED", "CREDIT", "ORCID", "PROSPERO",
    # 単位など
    "IU", "MG", "KG", "ML", "MMHG", "DL",
}

UNITS = r"(?:mg|kg|μg|ug|ng|g|mL|ml|dL|L|mmol|μmol|mEq|mmHg|cmH2O|cm|mm|μm|nm|IU|U|kcal|Gy|Sv|Hz|kPa)"
SECTION_SKIP = re.compile(r"^#{1,6}\s*(文献|引用文献|参考文献|References|Abstract|英文抄録)", re.I)
MARKER = re.compile(r"【(?:要(確認|文献)|(二次情報))[^】]*】")
ZEN_ALNUM = re.compile(r"[Ａ-Ｚａ-ｚ０-９]")
HAN_KANA = re.compile(r"[ｦ-ﾟ]")
DESU = re.compile(r"(です|ます|でした|ました|ません|でしょう)[。．]")
DEARU = re.compile(r"(である|であった|だった|した|された|いる|ある|ない|れる|れた|った|きた|た)[。．]")
P_ZERO = re.compile(r"[pP]\s*[=＝]\s*0\.0+(?!\d*[1-9])")
NUM_UNIT = re.compile(r"(?<![A-Za-z0-9.])(\d+(?:\.\d+)?)(" + UNITS + r")(?![A-Za-z0-9])")
YUUI = re.compile(r"有意(?!水準)")
STAT_EVIDENCE = re.compile(r"[pP]\s*[<>=≦≧≤≥＜＞＝]|信頼区間|\bCI\b|95\s*%")
PRIORITY = re.compile(r"本邦初|世界初|国内初|初めての報告|初の報告|最初の報告|報告(?:は|が)(?:ない|なかった|みられない|見当たらない|存在しない)|報告例(?:は|が)(?:ない|なかった)")
SEARCH_BASIS = re.compile(r"検索(?:した|し得た)?限り|医中誌|PubMed|MEDLINE|J-STAGE|Embase")
OVERCLAIM = re.compile(r"証明(?:した|された|する)|立証|原因である|臨床応用可能|有用性が確立|確立された治療")
PLACEHOLDER = re.compile(r"(?<![A-Za-z])(?:TBD|TODO|FIXME|x{3,}|XX)(?![A-Za-z])|20XX|○○|△△|（\s*）|\(\s*\)")
COMPARE = re.compile(r"優れ(?:て|た|る)|劣(?:って|った|る)|上回(?:った|る)|下回(?:った|る)")
ABBR = re.compile(r"(?<![A-Za-z0-9])([A-Z][A-Za-z0-9]*[A-Z][A-Za-z0-9]*)(?![A-Za-z0-9])")
DEFINE = re.compile(r"[：:，,（(]\s*([A-Z][A-Za-z0-9]*[A-Z][A-Za-z0-9]*)\s*[）)]")


def strip_noise(text: str) -> list[str]:
    """HTMLコメントとコードブロックを空行に置換して行番号を保つ。"""
    text = re.sub(r"<!--.*?-->", lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S)
    out, in_code = [], False
    for line in text.split("\n"):
        if line.strip().startswith("```"):
            in_code = not in_code
            out.append("")
            continue
        out.append("" if in_code else line)
    return out


def mostly_ascii(line: str) -> bool:
    s = line.strip()
    if not s:
        return True
    ascii_n = sum(1 for c in s if ord(c) < 128)
    return ascii_n / len(s) > 0.8


def count_chars(lines: list[str], section: str = "", limit: int = 0) -> None:
    sections: list[tuple[str, int]] = []
    current, n, total = "(冒頭)", 0, 0
    for line in lines:
        if line.startswith("#"):
            sections.append((current, n))
            current, n = line.lstrip("#").strip(), 0
            continue
        body = re.sub(r"[\s*_`>|]", "", line)
        n += len(body)
        total += len(body)
    sections.append((current, n))
    print("字数カウント（空白・Markdown記号・見出し・HTMLコメントを除く）")
    targets = [(n, c) for n, c in sections if c and (not section or section.lower() in n.lower())]
    if section and not targets:
        print(f"  見出しに「{section}」を含む節が見つからない")
    for name, c in targets:
        extra = ""
        if limit:
            extra = f"（上限 {limit} 字まで残り {limit - c} 字）" if c <= limit else f"（上限 {limit} 字を {c - limit} 字超過）"
        print(f"  {name}: {c} 字{extra}")
    if not section:
        print(f"  合計: {total} 字" + ((f"（上限 {limit} 字まで残り {limit - total} 字）" if total <= limit else f"（上限 {limit} 字を {total - limit} 字超過）") if limit else ""))
    print("※ 全角換算・表題/著者名の算入有無は投稿規定で確認すること")


def lint(lines: list[str], allow_desu: bool, known: set[str], draft: bool = False, echo: bool = True) -> int:
    errors = warns = 0
    defined: set[str] = set()
    reported_abbr: set[str] = set()
    desu_lines, dearu_n = [], 0
    puncts = {"、": [], "，": [], "。": [], "．": []}
    ranges = {"–": [], "〜": []}
    skip = False
    prev_sentence = ""
    markers = {"確認": 0, "文献": 0, "二次情報": 0, "仮置き": 0}
    abbr_count: dict[str, int] = {}

    def report(level: str, ln: int, msg: str, frag: str = "") -> None:
        nonlocal errors, warns
        if level == "ERROR":
            errors += 1
        else:
            warns += 1
        tail = f"  …{frag[:40]}…" if (frag and echo) else ""
        where = f"L{ln}" if ln else "全体"
        print(f"{level:5} {where}: {msg}{tail}")

    for i, raw in enumerate(lines, 1):
        line = raw.rstrip()
        if line.startswith("#"):
            skip = bool(SECTION_SKIP.match(line))
            continue
        if not line.strip():
            continue
        # マーカーは全節で検査
        for m in MARKER.finditer(line):
            markers[m.group(1) or m.group(2)] += 1
            if not draft:
                report("ERROR", i, "未解決マーカーが残っている", m.group(0))
        for m in PLACEHOLDER.finditer(MARKER.sub("", line)):
            markers["仮置き"] += 1
            if not draft:
                report("ERROR", i, f"仮置きの文字列「{m.group(0)}」が残っている（【要確認】に置き換えるか埋める）")
        if skip or mostly_ascii(line):
            continue
        line = PLACEHOLDER.sub("", MARKER.sub("", line))  # マーカー・仮置きは表記チェックの対象外

        for m in ZEN_ALNUM.finditer(line):
            report("ERROR", i, f"全角英数字「{m.group(0)}」→ 半角に")
            break
        if HAN_KANA.search(line):
            report("ERROR", i, "半角カタカナがある")
        if P_ZERO.search(line):
            report("ERROR", i, "p = 0.000 表記 → p < 0.001 等に", P_ZERO.search(line).group(0))
        for m in NUM_UNIT.finditer(line):
            report("WARN", i, f"数値と単位が詰まっている「{m.group(0)}」→「{m.group(1)} {m.group(2)}」（誌規定確認）")

        for ch in puncts:
            if ch in line:
                puncts[ch].append(i)
        for ch in ranges:
            if re.search(r"\d\s*" + ch + r"\s*\d", line):
                ranges[ch].append(i)

        if DESU.search(line):
            desu_lines.append(i)
        dearu_n += len(DEARU.findall(line))

        # 文単位のチェック
        for sent in re.split(r"(?<=[。．])", line):
            s = sent.strip()
            if not s:
                continue
            if len(s) > 120:
                report("WARN", i, f"1文が{len(s)}字（120字超）→ 分割を検討", s)
            if PRIORITY.search(s) and not SEARCH_BASIS.search(s):
                report("WARN", i, "「初の報告」「報告はない」系の主張に検索根拠がない（例：「医中誌Webおよび PubMed で○年○月に検索した限り」）", s)
            if OVERCLAIM.search(s):
                report("WARN", i, "「証明」は臨床研究では強すぎることが多い（「示された」「関連していた」等を検討）", s)
            if COMPARE.search(s) and not STAT_EVIDENCE.search(s) and not STAT_EVIDENCE.search(prev_sentence):
                report("WARN", i, "比較の表現（優れた・上回った等）の近くに効果量/信頼区間がない", s)
            if YUUI.search(s) and not STAT_EVIDENCE.search(s) and not STAT_EVIDENCE.search(prev_sentence):
                report("WARN", i, "「有意」の近くに p値/信頼区間がない", s)
            prev_sentence = s

        # 略語
        for m in DEFINE.finditer(line):
            defined.add(m.group(1))
        for m in ABBR.finditer(line):
            ab = m.group(1)
            abbr_count[ab] = abbr_count.get(ab, 0) + 1
            if ab in defined or ab.upper() in known or ab in reported_abbr:
                continue
            # 同じ行の後方で定義されているなら初出定義とみなす
            after = line[m.end():m.end() + 3]
            if re.match(r"\s*[）)]", after):
                defined.add(ab)
                continue
            reported_abbr.add(ab)
            report("WARN", i, f"略語「{ab}」が定義前に使われている（初出で「正式名（英語：{ab}）」と定義）")

    rare = sorted(ab for ab in defined if abbr_count.get(ab, 0) <= 2 and ab.upper() not in known)
    if rare:
        report("WARN", 0, f"定義したが本文で2回以下しか使わない略語：{', '.join(rare)}（略さず書くことを検討）")
    if desu_lines and not allow_desu:
        if dearu_n:
            report("ERROR", desu_lines[0], f"です・ます調が混在（該当行: {', '.join('L'+str(x) for x in desu_lines[:10])}）")
        else:
            report("WARN", desu_lines[0], "全体がです・ます調。論文本文はである調が既定（投稿規定確認）")
    if puncts["、"] and puncts["，"]:
        report("ERROR", puncts["，"][0], "読点「、」と「，」が混在")
    if puncts["。"] and puncts["．"]:
        report("ERROR", puncts["．"][0], "句点「。」と「．」が混在")
    if ranges["–"] and ranges["〜"]:
        report("WARN", ranges["〜"][0], "数値範囲の記号「–」と「〜」が混在")

    if any(markers.values()):
        print(f"INFO  未解決マーカー: 【要確認】{markers['確認']} 件 / 【要文献】{markers['文献']} 件 / 【二次情報】{markers['二次情報']} 件 / 仮置き {markers['仮置き']} 件"
              + ("（--draft のため ERROR に数えていない。投稿前は --draft なしで 0 件にする）" if draft else ""))
    print(f"\n結果: ERROR {errors} 件 / WARN {warns} 件")
    return errors


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file")
    ap.add_argument("--count", action="store_true", help="字数カウントのみ")
    ap.add_argument("--section", default="", help="--count で数える節（見出しの一部。例：要旨）")
    ap.add_argument("--limit", type=int, default=0, help="--count で比べる字数の上限")
    ap.add_argument("--allow-desu", action="store_true", help="です・ます調を許可")
    ap.add_argument("--draft", action="store_true", help="未解決マーカーを件数集計のみにする")
    ap.add_argument("--no-echo", action="store_true", help="該当箇所の文面を表示しない")
    ap.add_argument("--known", default="", help="定義不要略語をカンマ区切りで追加")
    a = ap.parse_args()

    text = read_manuscript(a.file)
    lines = strip_noise(text)
    if a.count:
        count_chars(lines, a.section, a.limit)
        return
    known = KNOWN_ABBR | {w.strip().upper() for w in a.known.split(",") if w.strip()}
    sys.exit(1 if lint(lines, a.allow_desu, known, a.draft, not a.no_echo) else 0)


if __name__ == "__main__":
    main()
