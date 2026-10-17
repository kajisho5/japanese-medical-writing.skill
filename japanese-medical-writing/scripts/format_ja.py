#!/usr/bin/env python3
"""表記の機械的な統一（Python 標準ライブラリのみ・通信なし）。

内容（言葉・数値・意味）は変えず、表記だけを統一した**別ファイル**を作る。元のファイルは変更しない。
【要確認】【要文献】、HTMLコメント、コードブロックの中は変更しない。

できること（指定したものだけ行う）:
  --punct ten      句読点を「、。」に統一（「，．」→「、。」）
  --punct comma    句読点を「，．」に統一（「、。」→「，．」）
  --zenkaku        全角英数字を半角に（例：２０２４ → 2024、ＣＴ → CT）
  --unit-space     数値と単位の間に半角スペース（5mg → 5 mg。% と ° は対象外）
  --range dash     数値範囲の記号を「–」に統一（1〜3 → 1–3）
  --range tilde    数値範囲の記号を「〜」に統一（1–3 → 1〜3）
  --all-default    --zenkaku --unit-space をまとめて行う（句読点・範囲は誌規定で決めるので含めない）

使い方:
  python3 format_ja.py --punct comma 原稿.md            → 原稿.formatted.md を作る
  python3 format_ja.py --zenkaku --unit-space 原稿.docx → 原稿.formatted.md を作る（Word は本文をテキスト化）
  python3 format_ja.py --punct ten -o 出力.md 原稿.md

小数点の「．」や英文中の「,」「.」は変えない（和文の句読点だけを対象にする）。
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _textio import read_manuscript  # noqa: E402

UNITS = r"(?:mg|kg|μg|ug|ng|g|mL|ml|dL|L|mmol|μmol|mEq|mmHg|cmH2O|cm|mm|μm|nm|IU|kcal|Gy|Sv|Hz|kPa)"
PROTECT = re.compile(r"【(?:要(?:確認|文献)|二次情報)[^】]*】|<!--.*?-->|`[^`\n]*`", re.S)
JA = r"[぀-ヿ一-鿿々〆ー）」』】]"


def protect(text: str) -> tuple[str, list[str]]:
    saved: list[str] = []

    def keep(m: re.Match[str]) -> str:
        saved.append(m.group(0))
        return f"{len(saved) - 1}"

    # コードブロック全体も保護
    text = re.sub(r"```.*?```", keep, text, flags=re.S)
    return PROTECT.sub(keep, text), saved


def restore(text: str, saved: list[str]) -> str:
    return re.sub("(\\d+)", lambda m: saved[int(m.group(1))], text)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file")
    ap.add_argument("-o", "--output")
    ap.add_argument("--punct", choices=["ten", "comma"])
    ap.add_argument("--zenkaku", action="store_true")
    ap.add_argument("--unit-space", action="store_true")
    ap.add_argument("--range", choices=["dash", "tilde"])
    ap.add_argument("--all-default", action="store_true")
    a = ap.parse_args()
    if a.all_default:
        a.zenkaku = a.unit_space = True
    if not (a.punct or a.zenkaku or a.unit_space or a.range):
        sys.exit("何を統一するか指定してください（--punct ten/comma、--zenkaku、--unit-space、--range dash/tilde）")

    src = Path(a.file)
    out = Path(a.output) if a.output else src.with_name(src.stem + ".formatted.md")
    if out.resolve() == src.resolve():
        sys.exit("元のファイルは上書きしません。別の出力名を指定してください")

    text, saved = protect(read_manuscript(a.file))
    counts: dict[str, int] = {}

    def sub(label: str, pattern: str, repl, s: str, flags: int = 0) -> str:
        new, n = re.subn(pattern, repl, s, flags=flags)
        if n:
            counts[label] = counts.get(label, 0) + n
        return new

    if a.zenkaku:
        text = sub("全角英数字→半角（文字数）", r"[Ａ-Ｚａ-ｚ０-９]", lambda m: chr(ord(m.group(0)) - 0xFEE0), text)
    if a.punct == "comma":
        text = sub("「、」→「，」", "、", "，", text)
        text = sub("「。」→「．」", "。", "．", text)
    elif a.punct == "ten":
        text = sub("「，」→「、」", "，", "、", text)
        # 全角ピリオドは和文の後ろにあるときだけ句点とみなす（小数点・略語は変えない）
        text = sub("「．」→「。」", r"(?<=" + JA + r")．|．(?=" + JA + r"|\s|\n|$)", "。", text, flags=re.M)
    if a.unit_space:
        text = sub("数値と単位の間に空白", r"(?<![A-Za-z0-9.])(\d+(?:\.\d+)?)(" + UNITS + r")(?![A-Za-z0-9])", r"\1 \2", text)
    if a.range == "dash":
        text = sub("範囲記号→「–」", r"(?<=\d)\s*[〜～~]\s*(?=\d)", "–", text)
    elif a.range == "tilde":
        text = sub("範囲記号→「〜」", r"(?<=\d)\s*[–—]\s*(?=\d)", "〜", text)

    out.write_text(restore(text, saved), encoding="utf-8")
    print(f"出力：{out}（元のファイルは変更していません）")
    if counts:
        for k, v in counts.items():
            print(f"  {k}：{v} か所")
    else:
        print("  変更はありませんでした")
    print("※ 表記だけを機械的に統一した。内容は変えていないが、念のため差分を確認すること")


if __name__ == "__main__":
    main()
