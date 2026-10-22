#!/usr/bin/env python3
"""原稿内の記載の食い違い（前後矛盾）の候補を拾う（Python 標準ライブラリのみ・通信なし）。

同じ部位・同じ検査について、原稿の別の場所で反対の記載があるものを候補として示す。
  1. 左右：同じ部位に「左」と「右」の両方が出る（例：左股関節 … 右股関節）
  2. 運動の方向：同じ部位について、制限・痛みなど異常を述べた方向が別の箇所で反対になっている
     （内旋/外旋、内転/外転、屈曲/伸展、背屈/底屈、回内/回外、内反/外反。部位を省いた文は直前の部位とみなす）
  3. 検査・徴候の結果：同じ検査名に「陽性」と「陰性」の両方が出る（例：Patrickテスト陽性 … 陰性）
  4. 病理・組織型：異なる組織型・分化度・良悪性の記載が複数ある
  5. 同じ運動の角度（可動域）が複数の値で書かれている

否定・正常の記載（「左肺に異常はなかった」「扁平上皮癌の成分は認めなかった」）の中の左右・組織型は数えない。
英文抄録の left/right ＋部位（hip, knee, lung など）と主な組織型（adenocarcinoma 等）も照合する。
部位の表記ゆれ（膝/膝関節、頚/頸）はそろえて比べる。

これらは「矛盾の候補」で、治療前後の変化や両側の比較など正しい記載のこともある。
候補ごとに、時点・対象が違うのか、書き間違いかを人が確認する。
AI は、このツールに加えて原稿全体を読み、時系列・用量・診断の流れの矛盾も確認する（SKILL.md）。

使い方:
  python3 check_consistency.py manuscript.md
  python3 check_consistency.py --no-echo manuscript.md   # 原稿から取った語（検査名）を表示しない

出力に出るのは、部位・運動方向・組織型など辞書にある医学用語と行番号だけ（--no-echo では検査名も伏せる）。

候補があれば終了コード 1。
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _textio import read_manuscript  # noqa: E402

PARTS = [
    "股関節", "膝関節", "足関節", "肩関節", "肘関節", "手関節", "顎関節", "仙腸関節",
    "大腿骨頭", "大腿骨頸部", "大腿骨", "脛骨", "腓骨", "上腕骨", "橈骨", "尺骨", "鎖骨", "肩甲骨", "膝蓋骨", "踵骨", "舟状骨",
    "大腿", "下腿", "上腕", "前腕", "下肢", "上肢", "膝", "肩", "肘", "手指", "足趾", "母趾", "母指", "足部", "手部",
    "肺", "腎", "副腎", "尿管", "卵巣", "卵管", "精巣", "乳房", "乳腺", "眼", "耳", "鼠径部", "腋窩", "胸腔", "横隔膜",
    "前頭葉", "側頭葉", "頭頂葉", "後頭葉", "大脳半球", "小脳半球", "内頸動脈", "中大脳動脈", "椎骨動脈", "総頸動脈", "片麻痺",
    "腰部", "殿部", "臀部", "坐骨神経", "腓骨神経", "正中神経", "尺骨神経",
]
PARTS.sort(key=len, reverse=True)
PART_RE = "|".join(map(re.escape, PARTS))
SIDE = re.compile(r"(左|右)(?:側)?\s*(" + PART_RE + ")")
DIRECTIONS = [("内旋", "外旋"), ("内転", "外転"), ("屈曲", "伸展"), ("背屈", "底屈"), ("回内", "回外"), ("内反", "外反"),
              ("掌屈", "背屈"), ("挙上", "下制")]
TEST = re.compile(r"([A-Za-z゠-ヿ一-鿿'’\-]{2,20}?(?:テスト|徴候|サイン|試験|検査|反射|sign|test))\s*(?:は|が|で|:|：)?\s*(陽性|陰性|\(\+\)|\(-\)|（\+）|（-）)", re.I)
HISTO = ["腺癌", "扁平上皮癌", "小細胞癌", "大細胞癌", "腺扁平上皮癌", "尿路上皮癌", "肝細胞癌", "腎細胞癌", "肉腫", "悪性リンパ腫",
         "高分化", "中分化", "低分化", "未分化", "良性", "悪性", "境界悪性"]
# 長いものから当てる（腺扁平上皮癌の中の「腺癌」「扁平上皮癌」、境界悪性・悪性リンパ腫の中の「悪性」を別に数えない）。
# 良性・悪性は「良性発作性頭位めまい症」などを拾わないよう、病変・腫瘍・判定の文脈に限る。
HISTO_RE = re.compile("|".join(sorted((re.escape(h) for h in HISTO if h not in ("良性", "悪性", "境界悪性")), key=len, reverse=True))
                      + r"|(?:境界悪性|良性|悪性)(?=腫瘍|病変|所見|と診断|と判断|であ|の|。|、|$)")
ANGLE = re.compile(r"(内旋|外旋|内転|外転|屈曲|伸展|背屈|底屈|回内|回外)\s*(?:角|可動域)?\s*(?:は|が|:|：)?\s*(\d{1,3})\s*(?:°|度)")
NOT_DIRECTION = re.compile(r"下肢伸展挙上(?:テスト|試験)?|大腿神経伸展(?:テスト|試験)?|伸展型|屈曲型|伸展位骨折|屈曲位骨折"
                           r"|外反母趾|内反小趾|内反足|外反扁平足|外反膝|内反膝|内反肘|外反肘")
TIME_PREFIX = re.compile(r"^(?:初診時|再診時|来院時|入院時|退院時|術前|術後|治療前|治療後|受傷時|今回|前回|経過中|最終観察時|同日|翌日|右|左|両側)+")
# 方向は「制限・痛み・拘縮など異常を述べている」ものだけ数える（屈曲 120°、伸展 0° のような可動域の列挙は数えない）
ABNORMAL = re.compile(r"制限|痛|拘縮|障害|不能|困難|不安定|誘発|増悪|低下|減少")
# 否定・正常の記載（「左肺に異常はなかった」「扁平上皮癌の成分は認めなかった」）は数えない
NEGATED = re.compile(r"認めな|認めず|みられな|見られな|否定|除外|ではな|なかった|なし|正常|異常はな|保たれ|健側|左右差は?な")
# 部位の表記ゆれ・省略をそろえる（左膝 と 右膝関節 を同じ部位として比べる）
PART_NORM = {"膝": "膝関節", "肩": "肩関節", "肘": "肘関節", "臀部": "殿部"}
EN_PART = {"hip": "股関節", "knee": "膝関節", "shoulder": "肩関節", "elbow": "肘関節", "ankle": "足関節", "wrist": "手関節",
           "lung": "肺", "kidney": "腎", "eye": "眼", "ovary": "卵巣", "breast": "乳房", "femur": "大腿骨", "femoral neck": "大腿骨頸部"}
EN_SIDE = re.compile(r"\b(left|right)\s+(" + "|".join(sorted(EN_PART, key=len, reverse=True)) + r")s?\b", re.I)
EN_HISTO = [(re.compile(r"\badenosquamous carcinoma", re.I), "腺扁平上皮癌"),
            (re.compile(r"\badenocarcinoma", re.I), "腺癌"),
            (re.compile(r"\bsquamous cell carcinoma", re.I), "扁平上皮癌"),
            (re.compile(r"(?<!non-)(?<!non )\bsmall cell carcinoma", re.I), "小細胞癌"),
            (re.compile(r"\bwell[- ]differentiated", re.I), "高分化"),
            (re.compile(r"\bmoderately[- ]differentiated", re.I), "中分化"),
            (re.compile(r"\bpoorly[- ]differentiated", re.I), "低分化")]
REF_HEAD = re.compile(r"^#{1,6}\s*(文献|引用文献|参考文献|References)\s*$", re.I)


def norm_result(r: str) -> str:
    return "陽性" if r in ("陽性", "(+)", "（+）") else "陰性"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file")
    ap.add_argument("--no-echo", action="store_true")
    a = ap.parse_args()
    text = read_manuscript(a.file)
    text = re.sub(r"<!--.*?-->", lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S)

    text = text.replace("頚", "頸")
    sentences: list[tuple[int, str, int]] = []  # (行番号, 文, 節の番号)
    in_refs, section = False, 0
    for i, line in enumerate(text.split("\n"), 1):
        if re.match(r"^#{1,6}\s", line):
            in_refs = bool(REF_HEAD.match(line))
            section += 1
            continue
        if in_refs:
            continue
        for s in re.split(r"(?<=[。．])|(?<=\.)\s+", line):
            if s.strip():
                sentences.append((i, s, section))

    sides: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    dirs: dict[tuple[str, str, str], dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))  # 文の番号
    line_of: dict[int, int] = {}
    tests: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    histo: dict[str, list[int]] = defaultdict(list)
    angles: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    bilateral = set()

    def norm(p: str) -> str:
        return PART_NORM.get(p, p)

    # 直前に出た部位（「術後、内旋制限は残存」のように部位を省いた文に使う）。同じ節を優先し、なければ原稿全体で直前のもの
    last_part: dict[int, str] = {}
    last_any = ""
    for si, (ln, s, sec) in enumerate(sentences):
        line_of[si] = ln
        clauses = re.split(r"[、，,]", s)
        for c in clauses:
            if NEGATED.search(c):
                continue  # 否定・正常の記載の中の左右・組織型は数えない
            for m in SIDE.finditer(c):
                sides[norm(m.group(2))][m.group(1)].append(ln)
            for m in EN_SIDE.finditer(c):
                sides[EN_PART[m.group(2).lower()]]["左" if m.group(1).lower() == "left" else "右"].append(ln)
            for m in HISTO_RE.finditer(c):
                histo[m.group(0)].append(ln)
            for pat, ja in EN_HISTO:
                if pat.search(c):
                    histo[ja].append(ln)
        for p in re.findall(r"両側\s*(?:の)?\s*(" + PART_RE + ")", s) + re.findall(r"左右\s*(?:の)?\s*(" + PART_RE + ")", s):
            bilateral.add(norm(p))
        parts_here = {norm(p) for p in re.findall(PART_RE, s)}
        if len(parts_here) == 1:
            last_part[sec] = last_any = next(iter(parts_here))
        fallback = last_part.get(sec) or last_any
        targets = parts_here or ({fallback} if fallback else set())
        for c in clauses:
            c_dir = NOT_DIRECTION.sub("", c)  # 病名・検査名に含まれる「外反」「伸展」は方向として数えない
            if NEGATED.search(c_dir) or not ABNORMAL.search(c_dir):
                continue
            for d1, d2 in DIRECTIONS:
                for d in (d1, d2):
                    if d in c_dir:
                        for p in targets:
                            dirs[(p, d1, d2)][d].append(si)
        for m in TEST.finditer(s):
            tests[TIME_PREFIX.sub("", m.group(1)) or m.group(1)][norm_result(m.group(2))].append(ln)
        for m in ANGLE.finditer(s):
            angles[m.group(1)][m.group(2)].append(ln)

    hits = 0

    def say(msg: str) -> None:
        nonlocal hits
        hits += 1
        print(msg)

    def where(lines: list[int]) -> str:
        return "、".join(f"L{n}" for n in sorted(set(lines))[:6])

    for part, d in sides.items():
        if "左" in d and "右" in d and part not in bilateral:
            say(f"CHECK 左右：「{part}」に左（{where(d['左'])}）と右（{where(d['右'])}）の両方がある → 左右の取り違えでないか（両側なら「両側」と明記）")
    for (part, d1, d2), d in dirs.items():
        if d1 in d and d2 in d:
            if set(d[d1]) == set(d[d2]):
                continue  # どの文でも両方を並べている（例：屈曲 120°、伸展 0° の可動域の記載）
            l1 = [line_of[i] for i in d[d1]]
            l2 = [line_of[i] for i in d[d2]]
            say(f"CHECK 方向：「{part}」に{d1}（{where(l1)}）と{d2}（{where(l2)}）がある → 制限・痛みの方向が前後で入れ替わっていないか")
    for name, d in tests.items():
        if "陽性" in d and "陰性" in d:
            shown = "検査・徴候" if a.no_echo else f"「{name}」"
            say(f"CHECK 所見：{shown}が陽性（{where(d['陽性'])}）と陰性（{where(d['陰性'])}）の両方 → 時点の違いか、取り違えか")
    types = [h for h in histo if h not in ("高分化", "中分化", "低分化", "未分化", "良性", "悪性", "境界悪性")]
    grades = [h for h in histo if h in ("高分化", "中分化", "低分化", "未分化")]
    malign = [h for h in histo if h in ("良性", "悪性", "境界悪性")]
    for label, group in (("組織型", types), ("分化度", grades), ("良性/悪性", malign)):
        if len(group) > 1:
            say(f"CHECK 病理：{label}が複数ある（{'、'.join(f'{h}（{where(histo[h])}）' for h in group)}）→ 同じ病変について記載が食い違っていないか")
    for motion, vals in angles.items():
        if len(vals) > 1:
            say(f"INFO  角度：{motion}の角度が複数（{'、'.join(f'{v}°（{where(l)}）' for v, l in vals.items())}）→ 時点（初診時・術後など）が書き分けられているか")
            hits -= 1  # 情報のみ（終了コードに数えない）

    print(f"\n前後の食い違いの候補 {hits} 件（候補であり、正しい記載のこともある。時系列・用量・診断の流れは人と AI が全文を読んで確認すること）")
    sys.exit(1 if hits else 0)


if __name__ == "__main__":
    main()
