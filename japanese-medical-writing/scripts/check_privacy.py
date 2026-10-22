#!/usr/bin/env python3
"""原稿中の個人情報らしき記載の検出（Python 標準ライブラリのみ・ネットワーク不使用）。

検出するもの（すべて「候補」。誤検出も見逃しもある。最後は人が読む）:
  - 具体的な年月日（2025年4月3日、2025/4/3、令和7年4月3日、R7.4.3、年のない4月3日 など）
    「X年Y月」形式は対象外
  - 生年月日、90歳以上の年齢、年齢の月数まで（小児では臨床的に必要な場合あり）
  - カルテ番号・患者ID・保険者番号・MRN 等、12桁の番号（マイナンバー等）
  - 電話番号（ハイフンあり・なし、+81）・郵便番号・メールアドレス
  - 住所（都道府県＋市区町村、番地）、「〜在住」、病室番号
  - 施設名（〜病院・医院・クリニック・診療所・医療センター）
  - 人名（さん・氏・先生等の敬称つき、イニシャル、英字の氏名らしき並び）
    ※「様」は「すりガラス様」「腫瘤様」等の医学用語と区別できないため対象外。敬称なしの氏名も検出できない
  - 職業・勤務先の具体的記載、画像ファイル名・DICOM
  .docx ではヘッダ・フッタ・脚注・コメント・作成者情報（メタデータ）も確認する。
  見出し・HTMLコメント・【要確認】の中も確認する（ファイルとして他人に渡るため）。

使い方:
  python3 check_privacy.py manuscript.md
  python3 check_privacy.py --no-echo manuscript.md   # 該当文字列を表示しない

候補があれば終了コード 1。倫理承認番号・試験登録番号などは除外する。
"""
from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _textio import read_docx_extras, read_manuscript  # noqa: E402

ERA = r"(?:明治|大正|昭和|平成|令和)"
KANJI_NUM = r"[〇一二三四五六七八九十元]+"
NAME_CHARS = r"[一-鿿々゠-ヿ]"

CHECKS: list[tuple[str, re.Pattern[str], bool]] = [
    # (ラベル, パターン, 文献節でも確認するか)
    ("具体的な年月日", re.compile(
        r"(?:(?:19|20)\d{2}|" + ERA + r"\s*(?:\d{1,2}|元)|" + ERA + KANJI_NUM + r")\s*年\s*(?:\d{1,2}|" + KANJI_NUM + r")\s*月\s*(?:\d{1,2}|" + KANJI_NUM + r")\s*日"
        r"|(?:19|20)\d{2}[/.-]\d{1,2}[/.-]\d{1,2}"
        r"|(?<![A-Za-z])[MTSHR]\s?\d{1,2}[./]\d{1,2}[./]\d{1,2}"
        r"|(?<![年\d])\d{1,2}\s*月\s*\d{1,2}\s*日"), False),
    ("生年月日・高齢（90歳以上）", re.compile(r"生年月日|生年\s*[:：]|(?<!\d)(?:9\d|1[0-2]\d)\s*歳"), True),
    ("年齢の月数（小児では必要な場合あり。特定リスクと誌規定で判断）", re.compile(r"\d{1,3}\s*歳\s*\d{1,2}\s*(?:か|ヶ|カ|ケ|箇)?月"), True),
    ("カルテ番号・ID・保険証番号", re.compile(
        r"(?:カルテ|診察券|患者|受付|入院|外来|検体|病歴)\s*(?:番号|ID|No\.?)\s*[:：]?\s*[\w-]+"
        r"|保険者番号|被保険者|記号\s*\S{1,10}\s*番号|\bMRN\b|(?<![A-Za-z])ID\s*[:：]\s*\w+", re.I), True),
    ("12桁の番号（マイナンバー等）", re.compile(r"(?<!\d)\d{4}\s?\d{4}\s?\d{4}(?!\d)"), True),
    ("電話番号", re.compile(r"(?<!\d)0\d{1,4}[-‐ー]\d{1,4}[-‐ー]\d{3,4}(?!\d)|(?<![\d.])0\d{9,10}(?![\d.])|\+81[-\s]?\d"), True),
    # 〒なしの「123-4567」は、単位・範囲が続くもの（「500-1500 mL」等）を除く
    ("郵便番号", re.compile(r"〒\s*\d{3}[-‐ー]?\d{4}|(?<![\d.,\-–~〜])\d{3}-\d{4}(?![\d.,\-–~〜])(?!\s*(?:[A-Za-zμ%/×]|例|名|人|件|回|日|週|か月|ヶ月|年|歳|円|個|錠|本|台|床|倍))"), True),
    ("メールアドレス", re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), True),
    ("住所らしき記載", re.compile(
        r"(?:東京都|北海道|(?:京都|大阪)府|[一-鿿]{2,3}県)[一-鿿]{1,6}(?:市|区|町|村)[一-鿿]*(?:[\d]+(?:-[\d]+){0,2}|\d+\s*(?:丁目|番地|番|号))?"
        r"|[一-鿿]{1,5}(?:市|区|町|村)\s*在住"), True),
    ("病室番号", re.compile(r"\d{2,4}\s*号室"), True),
    ("施設名らしき記載", re.compile(r"[一-鿿゠-ヿA-Za-z]{2,12}(?:病院|医院|クリニック|診療所|医療センター)"), True),
    ("人名（敬称・肩書・イニシャル）", re.compile(
        NAME_CHARS + r"{1,6}(?:さん|ちゃん|くん|氏|先生|殿)"
        r"|(?<![A-Za-z])[A-Z]\.\s?[A-Z]\.(?![A-Za-z])"
        r"|(?<![A-Za-z])[A-Z]\s?氏"
        r"|(?:Dr|Mr|Ms|Mrs)\.?\s+[A-Z][a-z]+"), True),
    ("英字の氏名らしき並び", re.compile(r"(?<![A-Za-z])[A-Z][a-z]{1,15}\s[A-Z][a-z]{1,15}(?![A-Za-z])"), False),
    ("職業・勤務先の具体的記載", re.compile(
        r"[一-鿿゠-ヿ]{2,10}(?:株式会社|社|工場|高校|中学校|小学校|大学)(?:に)?(?:勤務|在籍|在学|の教諭|の社員)"), True),
    ("画像・DICOM", re.compile(r"\.(?:dcm|DCM)\b|DICOM|IMG_\d{3,}|DSC_?\d{3,}"), True),
]
# 誤検出を減らすため、照合前に取り除く「識別子ではない番号・語」
REMOVE_FIRST = re.compile(
    r"【二次情報[^】]*】"  # 出典名と報道日であり患者情報ではない
    r"|(?:承認|登録|課題|研究)番号\s*[:：]?\s*[\w\-–]+"
    r"|jRCT[sa]?\d+|UMIN\d+|ISSN\s*[\dX-]+|doi[:：]?\s*\S+|https?://\S+"
    r"|(?<![\u4e00-\u9fff\u30a0-\u30ffA-Za-z])(?:当院|本院|本学|自施設|他院|前医|近医|総合病院|大学病院|一般病院|市中病院|基幹病院|地域医療支援病院|特定機能病院|精神科病院|療養病院)"
    r"|(?:Phase|Grade|Stage|Type|Class|Group|Table|Figure|Fig)\s+[A-Z][a-z]+"
    # 指定・区分の一般名（施設名ではない）
    r"|(?:都道府県|地域)?がん診療連携拠点病院|地域がん診療病院|がんゲノム医療(?:中核)?拠点病院|小児がん拠点病院"
    r"|災害拠点病院|臨床研修病院|へき地医療拠点病院|(?:総合|地域)周産期母子医療センター|(?:高度)?救命救急センター"
    r"|地域医療支援病院|特定機能病院|がん専門病院|大学附属病院|大学付属病院"
    # 医学用語の「殿部」「殿筋」と「赤ちゃん」は敬称ではない
    r"|[左右両]?殿(?:部|筋|裂|溝)|赤ちゃん", re.I)
# 英語の尺度・検定名など（大文字始まりの2語でも人名ではない）。大文字小文字を区別する
REMOVE_EN = re.compile(
    r"(?<![A-Za-z])(?:Glasgow Coma|Coma Scale|Barthel Index|Kaplan[- ]Meier|Mann[- ]Whitney|Fisher(?:'s)? Exact"
    r"|Wilcoxon(?: Signed[- ]Rank| Rank[- ]Sum)?|Kruskal[- ]Wallis|Bland[- ]Altman|Shapiro[- ]Wilk|Kolmogorov[- ]Smirnov"
    r"|Hosmer[- ]Lemeshow|Child[- ]Pugh|Hoehn(?: and)? Yahr|Modified Rankin|Mini[- ]Mental|New York Heart Association"
    r"|Performance Status|Visual Analog(?:ue)?|Numerical Rating|Cox Proportional|Chi[- ]Square|Student(?:'s)? T)(?![a-z])"
    r"|(?<![A-Za-z])[A-Z][a-z]+(?:[\s-][A-Z][a-z]+)+\s(?:Scale|Index|Test|Score|Classification|Criteria|Grade|Staging|Questionnaire|Inventory|Syndrome|Disease)(?![A-Za-z])")
REF_HEAD = re.compile(r"^#{1,6}\s*(文献|引用文献|参考文献|References)\s*$", re.I)
AUTHOR_HEAD = re.compile(r"^#{1,6}\s*(著者|著者名|所属|謝辞|Authors?|Affiliations?|Acknowledg)", re.I)


def scan(text: str, origin: str, echo: bool) -> int:
    hits = 0
    in_refs = in_authors = False
    for i, raw in enumerate(text.split("\n"), 1):
        line = unicodedata.normalize("NFKC", raw)
        if re.match(r"^#{1,6}\s", line):
            in_refs = bool(REF_HEAD.match(line))
            in_authors = bool(AUTHOR_HEAD.match(line))
        if not line.strip():
            continue
        target = REMOVE_EN.sub(" ", REMOVE_FIRST.sub(" ", line))
        for label, pat, in_refs_too in CHECKS:
            if in_refs and not in_refs_too:
                continue
            if (in_refs or in_authors) and label.startswith(("英字の氏名", "施設名")):
                continue  # 著者・所属・謝辞・文献の人名や施設名は患者識別子ではない
            for m in pat.finditer(target):
                hits += 1
                shown = "" if not echo else f"  「{m.group(0)}」"
                print(f"CHECK {origin}L{i}: {label}{shown}")
    return hits


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file")
    ap.add_argument("--no-echo", action="store_true")
    a = ap.parse_args()
    echo = not a.no_echo
    hits = scan(read_manuscript(a.file), "", echo)
    if a.file.lower().endswith(".docx"):
        for part, text in read_docx_extras(a.file):
            if part == "作成者情報":
                for line in text.split("\n"):
                    if line.strip():
                        hits += 1
                        print(f"CHECK [作成者情報]: ファイルのメタデータに {line if echo else '作成者・最終更新者等'} が残っている（共有前に削除）")
            else:
                hits += scan(text, f"[{part}] ", echo)
    print(f"\n個人情報の候補 {hits} 件（候補であり、見逃しもある。画像・図表の中の文字は検出できないので人が確認すること）")
    sys.exit(1 if hits else 0)


if __name__ == "__main__":
    main()
