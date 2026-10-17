#!/usr/bin/env python3
"""原稿中の個人情報らしき記載の検出（Python 標準ライブラリのみ・ネットワーク不使用）。

検出するもの（すべて「候補」。誤検出も見逃しもある。最後は人が読む）:
  - 具体的な年月日（2025年4月3日、2025/4/3、令和7年4月3日 など）。「X年Y月」形式は対象外
  - 生年月日・年齢の端数まで（「67歳3か月」）
  - カルテ番号・患者ID・登録番号らしき記載
  - 電話番号・郵便番号・メールアドレス
  - 都道府県＋市区町村の住所らしき記載
  - 人名の敬称・イニシャル（「○○さん」「〜様」「A.B.」「T氏」）
  - 職業・勤務先の具体的記載（「〜社勤務」「〜高校の教諭」）
  - 画像ファイル名・DICOM を示唆する記載

使い方:
  python3 check_privacy.py manuscript.md
  python3 check_privacy.py --no-echo manuscript.md   # 該当文字列を表示しない

検出件数があれば終了コード 1（倫理承認番号・試験登録番号は除外）。
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ERA = r"(?:明治|大正|昭和|平成|令和)"
CHECKS: list[tuple[str, re.Pattern[str]]] = [
    ("具体的な年月日", re.compile(r"(?:(?:19|20)\d{2}|" + ERA + r"\s*\d{1,2})\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日|(?:19|20)\d{2}[/.-]\d{1,2}[/.-]\d{1,2}")),
    ("生年月日・詳細な年齢", re.compile(r"生年月日|\d{1,3}\s*歳\s*\d{1,2}\s*(?:か|ヶ|カ|ケ)?月")),
    ("カルテ番号・ID", re.compile(r"(?:カルテ|診察券|患者|受付|入院|検体)\s*(?:番号|ID|No\.?)\s*[:：]?\s*\w+", re.I)),
    ("電話番号", re.compile(r"(?<!\d)0\d{1,4}[-‐ー]\d{1,4}[-‐ー]\d{3,4}(?!\d)")),
    ("郵便番号", re.compile(r"〒\s*\d{3}[-‐ー]?\d{4}|(?<![\d.])\d{3}-\d{4}(?![\d-])")),
    ("メールアドレス", re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")),
    ("住所らしき記載", re.compile(r"(?:東京都|北海道|(?:京都|大阪)府|[一-鿿]{2,3}県)[一-鿿]{1,6}(?:市|区|町|村)[一-鿿\d０-９]*(?:丁目|番地|番|号)?")),
    ("人名の敬称・イニシャル", re.compile(r"[一-鿿゠-ヿ]{1,4}(?:さん|様|ちゃん|くん)|(?<![A-Za-z])[A-Z]\.\s?[A-Z]\.(?![A-Za-z])|(?<![A-Za-z])[A-Z]\s?氏")),
    ("職業・勤務先の具体的記載", re.compile(r"[一-鿿゠-ヿ]{2,10}(?:株式会社|社|工場|高校|中学校|小学校|大学)(?:に)?(?:勤務|在籍|在学|の教諭|の社員)")),
    ("画像・DICOM", re.compile(r"\.(?:dcm|DCM)\b|DICOM|IMG_\d{3,}|DSC_?\d{3,}")),
]
EXCLUDE = re.compile(r"承認番号|登録番号|jRCT|UMIN|課題番号|ISSN|DOI|doi", re.I)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file")
    ap.add_argument("--no-echo", action="store_true")
    a = ap.parse_args()
    text = Path(a.file).read_text(encoding="utf-8")
    text = re.sub(r"<!--.*?-->", lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S)
    hits = 0
    in_refs = False
    for i, line in enumerate(text.split("\n"), 1):
        if line.startswith("#"):
            in_refs = bool(re.match(r"^#{1,6}\s*(文献|引用文献|参考文献|References)\s*$", line, re.I))
            continue
        if in_refs or not line.strip():
            continue
        target = re.sub(r"【要(確認|文献)[^】]*】", "", line)
        for label, pat in CHECKS:
            for m in pat.finditer(target):
                ctx = target[max(0, m.start() - 8):m.end() + 8]
                if EXCLUDE.search(ctx):
                    continue
                hits += 1
                shown = "" if a.no_echo else f"  「{m.group(0)}」"
                print(f"CHECK L{i}: {label}{shown}")
    print(f"\n個人情報の候補 {hits} 件（候補であり、見逃しもある。画像・図表・表のセルも人が確認すること）")
    sys.exit(1 if hits else 0)


if __name__ == "__main__":
    main()
