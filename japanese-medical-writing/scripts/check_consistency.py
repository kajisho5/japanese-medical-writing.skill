#!/usr/bin/env python3
"""原稿内の記載の食い違い（前後矛盾）の候補を拾う（Python 標準ライブラリのみ・通信なし）。

同じ部位・同じ検査について、原稿の別の場所で反対の記載があるものを候補として示す。
  1. 左右：同じ部位に「左」と「右」の両方が出る（例：左股関節 … 右股関節）
  2. 運動の方向：同じ部位について、制限・痛みなど異常を述べた方向が別の箇所で反対になっている
     （内旋/外旋、内転/外転、屈曲/伸展、背屈/底屈、回内/回外、内反/外反。部位を省いた文は直前の部位とみなす）
  3. 検査・徴候の結果：同じ検査名に「陽性」と「陰性」の両方が出る（例：Patrickテスト陽性 … 陰性）
  4. 病理・組織型：異なる組織型・分化度・良悪性の記載が複数ある
  5. 同じ運動の角度（可動域）が複数の値で書かれている（INFO）
  6. 病変側と麻痺側：大脳（大脳半球・各脳葉・内包・放線冠・被殻・視床・中大脳動脈など）の病変と片麻痺が同じ側
     （錐体路は延髄で交叉するため、通常は対側。脳幹病変では交叉性の症状があり得る）
  7. 数値と向き：「CRP は 15.2 mg/dL から 3.1 mg/dL に上昇」のように、前後の数値の大小と上昇/低下が逆
     （基準値は使わない。同じ文の中の2つの数値の大小だけで判定する）
  8. 単位の混在：同じ検査項目に別の単位（CRP の mg/dL と mg/L など）。換算漏れ・転記ミスの候補
  9. 薬剤：同じ薬剤名に mg と μg のように桁の違う単位（CHECK）。用量・投与経路が複数ある（INFO：漸増・切替なら正しい）
 10. 時系列：症例・経過の節の中で「第N病日」「術後N日目」などが前の記載より小さくなる

否定・正常の記載（「左肺に異常はなかった」「扁平上皮癌の成分は認めなかった」）の中の左右・組織型は数えない。
英文抄録の left/right ＋部位（hip, knee, lung など）と主な組織型（adenocarcinoma 等）も照合する。
部位の表記ゆれ（膝/膝関節、頚/頸）はそろえて比べる。

これらは「矛盾の候補」で、治療前後の変化や両側の比較など正しい記載のこともある。
候補ごとに、時点・対象が違うのか、書き間違いかを人が確認する。
AI は、このツールに加えて原稿全体を読み、時系列・用量・診断の流れの矛盾も確認する（SKILL.md）。

使い方:
  python3 check_consistency.py manuscript.md
  python3 check_consistency.py --no-echo manuscript.md   # 原稿から取った語（検査名）を表示しない

出力に出るのは、行番号・数値と、部位・運動方向・組織型・検査項目など辞書にある医学用語。
原稿から取った語（徴候・テスト名、薬剤名）は --no-echo で伏せる。

候補があれば終了コード 1。
"""
from __future__ import annotations

import argparse
import re
import sys
import unicodedata
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

# 6. 病変側と麻痺側（出典：MSD マニュアル プロフェッショナル版「脳卒中の概要」【二次情報】。出典台帳を参照）
CEREBRAL = ["大脳半球", "前頭葉", "頭頂葉", "側頭葉", "後頭葉", "内包", "放線冠", "被殻", "視床", "尾状核", "基底核",
            "中大脳動脈", "前大脳動脈", "内頸動脈", "大脳"]
LESION = re.compile(r"(左|右)(?:側)?\s*(?:の)?\s*(" + "|".join(sorted(CEREBRAL, key=len, reverse=True)) + ")")
PARESIS = re.compile(r"(左|右)(?:側)?\s*(?:不全)?(?:片麻痺|半身(?:の)?(?:不全)?麻痺|上下肢(?:の)?(?:不全)?麻痺)|\b(left|right)[- ]sided? hemipar|\b(left|right) hemipar", re.I)
BRAINSTEM = re.compile(r"脳幹|中脳|橋(?:梗塞|出血|病変)|延髄|脊髄|頸髄|Weber|Wallenberg|brainstem|medulla|pons", re.I)

# 7・8. 検査項目（数値と単位を比べる対象。表記は一般的な略称と和名）
LABS = ["CRP", "WBC", "白血球数", "白血球", "Hb", "ヘモグロビン", "Plt", "血小板数", "血小板", "AST", "ALT", "LDH", "LD", "ALP", "γ-GTP",
        "CK", "BUN", "Cr", "クレアチニン", "eGFR", "Na", "K", "Cl", "Ca", "Alb", "アルブミン", "TP", "T-Bil", "総ビリルビン", "HbA1c",
        "BNP", "NT-proBNP", "PCT", "プロカルシトニン", "D-dimer", "Dダイマー", "フィブリノゲン", "PT-INR", "APTT", "血糖", "乳酸",
        "PaO2", "PaCO2", "SpO2", "pH", "フェリチン", "トロポニンT", "トロポニンI", "IgG", "IgE", "KL-6", "CEA", "CA19-9", "PSA", "AFP",
        "TSH", "FT4", "FT3", "尿蛋白", "体温", "収縮期血圧", "拡張期血圧", "血圧", "心拍数", "脈拍"]
LAB_RE = "|".join(re.escape(x) for x in sorted(LABS, key=len, reverse=True))
UNIT = r"(?:mg/dL|mg/L|g/dL|g/L|μg/dL|μg/mL|ng/mL|ng/dL|pg/mL|mIU/L|μIU/mL|U/L|IU/L|U/mL|mmol/L|mEq/L|mL/min/1\.73\s*m2|/μL|×10\^?\d+/μL|万/μL|%|mmHg|kPa|℃|°C|bpm|回/分|/分)"
NUM = r"(\d+(?:\.\d+)?)"
LAB_UNIT = re.compile(r"(?<![A-Za-z])(" + LAB_RE + r")(?![A-Za-z0-9])\s*(?:値)?\s*(?:は|が|:|：|=)?\s*(?:最高|最大|最低)?\s*" + NUM + r"\s*(" + UNIT + ")")
LAB_CHANGE = re.compile(r"(?<![A-Za-z])(" + LAB_RE + r")(?![A-Za-z0-9])[^。]{0,12}?" + NUM + r"\s*(" + UNIT + r")?\s*(?:から|より|→|⇒|->)\s*" + NUM
                        + r"\s*(" + UNIT + r")?\s*(?:に|へ|まで|と)?[^。、]{0,8}?(上昇|増加|増悪|高値化|低下|減少|低値化)")
UP, DOWN = {"上昇", "増加", "増悪", "高値化"}, {"低下", "減少", "低値化"}

# 9. 薬剤（片仮名の薬剤名＋投与量の単位。検査項目の和名は除く）
DRUG = re.compile(r"([ァ-ヴ][ァ-ヴー・]{2,24})\s*(?:\([^)]{1,20}\))?\s*(?:を|は)?\s*(?:1日|1回)?\s*" + NUM
                  + r"\s*(mg|μg|mcg|ng|g|mL|単位|IU|mEq)(?!\s*/\s*(?:dL|L|mL|μL))")
NOT_DRUG = set(LABS) | {"ヘモグロビン", "アルブミン", "クレアチニン", "ビリルビン", "フェリチン", "トロポニン", "グルコース", "カテーテル", "ドレーン"}
ROUTE = re.compile(r"点滴静注|静注|静脈内投与|経口投与|内服|筋注|筋肉内投与|皮下注|皮下投与|吸入|外用|坐剤|経鼻投与|髄注|動注")
MASS = {"ng": 1e-9, "μg": 1e-6, "mcg": 1e-6, "mg": 1e-3, "g": 1.0}

# 10. 時系列（経過の節の中で数え方ごとに比べる）
COURSE_HEAD = re.compile(r"症例|経過|現病歴|入院後|治療|Case|Course", re.I)
COUNTERS = [("術後", re.compile(r"術後\s*(?:第\s*)?(\d+)\s*(?:病日|日目|日|POD)")),
            ("入院", re.compile(r"入院\s*(?:第\s*)?(\d+)\s*(?:病日|日目)")),
            ("発症", re.compile(r"発症\s*(?:第\s*)?(\d+)\s*(?:病日|日目)")),
            ("病日", re.compile(r"(?<!術後)(?<!入院)(?<!発症)第\s*(\d+)\s*病日"))]


def extra_checks(sentences: list[tuple[int, str, int]], sec_names: dict[int, str], no_echo: bool) -> list[tuple[str, str]]:
    """6〜10 の照合。(種類 "CHECK"/"INFO", 文) のリストを返す。"""
    out: list[tuple[str, str]] = []
    full = "\n".join(s for _, s, _ in sentences)

    # 6. 病変側と麻痺側
    lesion_sides: dict[str, list[int]] = defaultdict(list)
    paresis_sides: dict[str, list[int]] = defaultdict(list)
    for ln, s, _ in sentences:
        for c in re.split(r"[、,]", s):
            if NEGATED.search(c):
                continue
            for m in LESION.finditer(c):
                lesion_sides[m.group(1)].append(ln)
            for m in PARESIS.finditer(c):
                side = m.group(1) or ("左" if (m.group(2) or m.group(3) or "").lower() == "left" else "右")
                paresis_sides[side].append(ln)
    if len(lesion_sides) == 1 and paresis_sides:
        side = next(iter(lesion_sides))
        if side in paresis_sides:
            note = "脳幹病変の記載あり：交叉性の症状なら説明があるか確認" if BRAINSTEM.search(full) else "大脳の病変なら通常は対側に麻痺が出る"
            out.append(("CHECK", f"病変側と麻痺側：{side}の大脳病変（{_where(lesion_sides[side])}）と{side}の片麻痺（{_where(paresis_sides[side])}）"
                                 f" → {note}。左右の取り違えでないか"))

    # 7. 数値と向き
    for ln, s, _ in sentences:
        for m in LAB_CHANGE.finditer(s):
            lab, x, ux, y, uy, verb = m.groups()
            if ux and uy and ux != uy:
                continue  # 単位が違う（8 で扱う）
            x, y = float(x), float(y)
            if (verb in UP and y < x) or (verb in DOWN and y > x):
                out.append(("CHECK", f"数値と向き：L{ln} の{lab}は {x:g} → {y:g} なのに「{verb}」 → 数値か言葉のどちらかが逆でないか"))

    # 8. 単位の混在
    units: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    for ln, s, _ in sentences:
        for m in LAB_UNIT.finditer(s):
            units[m.group(1)][m.group(3).replace(" ", "")].append(ln)
    for lab, d in units.items():
        if len(d) > 1:
            out.append(("CHECK", f"単位の混在：{lab}に {'、'.join(f'{u}（{_where(l)}）' for u, l in d.items())} → 換算漏れ・転記ミスでないか（誌規定の単位に統一）"))

    # 9. 薬剤
    drugs: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    routes: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    for ln, s, _ in sentences:
        for m in DRUG.finditer(s):
            name = m.group(1).strip("・")
            if name in NOT_DRUG or any(name.endswith(x) for x in ("テスト", "スコア", "スケール")):
                continue
            drugs[name][f"{m.group(2)} {m.group(3)}"].append(ln)
            r = ROUTE.search(s[m.end():m.end() + 30]) or ROUTE.search(s[max(0, m.start() - 15):m.start()])
            if r:
                routes[name][r.group(0)].append(ln)
    for i, (name, doses) in enumerate(drugs.items(), 1):
        shown = f"薬剤{i}" if no_echo else f"「{name}」"
        masses = {d.split()[1] for d in doses if d.split()[1] in MASS}
        if len({MASS[u] for u in masses}) > 1:
            out.append(("CHECK", f"薬剤の単位：{shown}に {'、'.join(sorted(masses))} の両方（{_where([l for v in doses.values() for l in v])}）"
                                 " → 桁の違う単位の取り違え（mg と μg など）でないか"))
        elif len(doses) > 1:
            out.append(("INFO", f"薬剤の用量：{shown}に複数の用量（{'、'.join(f'{d}（{_where(l)}）' for d, l in doses.items())}）"
                                " → 漸増・減量なら時点が書き分けられているか"))
        if len(routes.get(name, {})) > 1:
            rr = routes[name]
            out.append(("INFO", f"投与経路：{shown}に複数の経路（{'、'.join(f'{r}（{_where(l)}）' for r, l in rr.items())}）"
                                " → 切り替えなら時点が書き分けられているか"))

    # 10. 時系列
    last: dict[tuple[int, str], tuple[int, int]] = {}
    for ln, s, sec in sentences:
        if not COURSE_HEAD.search(sec_names.get(sec, "")):
            continue
        found = []
        masked = s
        for key, pat in COUNTERS:
            for m in pat.finditer(masked):
                if re.match(r"\s*(?:から|より|以降|以来|まで|ごろ|頃)", masked[m.end():]):
                    continue  # 「第3病日から開始」のような期間の起点・終点は順序に数えない
                found.append((m.start(), key, int(m.group(1))))
            masked = pat.sub(lambda m: "□" * len(m.group(0)), masked)
        for _, key, n in sorted(found):
            prev = last.get((sec, key))
            if prev and n < prev[0]:
                label = "第N病日" if key == "病日" else f"{key}N日"
                out.append(("CHECK", f"時系列：{sec_names[sec].lstrip('# ').strip()}の節で{label}が {prev[0]}（L{prev[1]}）→ {n}（L{ln}）と戻っている"
                                     " → 記載順か日数の誤りでないか（振り返りの記載なら時点が分かる書き方か）"))
            last[(sec, key)] = (n, ln)
    return out


def _where(lines: list[int]) -> str:
    return "、".join(f"L{n}" for n in sorted(set(lines))[:6])


def norm_result(r: str) -> str:
    return "陽性" if r in ("陽性", "(+)", "（+）") else "陰性"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file")
    ap.add_argument("--no-echo", action="store_true")
    a = ap.parse_args()
    text = read_manuscript(a.file)
    text = re.sub(r"<!--.*?-->", lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S)

    text = unicodedata.normalize("NFKC", text).replace("頚", "頸").replace("µ", "μ")
    sentences: list[tuple[int, str, int]] = []  # (行番号, 文, 節の番号)
    sec_names: dict[int, str] = {}
    in_refs, section = False, 0
    for i, line in enumerate(text.split("\n"), 1):
        if re.match(r"^#{1,6}\s", line):
            in_refs = bool(REF_HEAD.match(line))
            section += 1
            sec_names[section] = line
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

    for kind, msg in extra_checks(sentences, sec_names, a.no_echo):
        print(f"{'CHECK' if kind == 'CHECK' else 'INFO '} {msg}")
        if kind == "CHECK":
            hits += 1

    print(f"\n前後の食い違いの候補 {hits} 件（候補であり、正しい記載のこともある。時系列・用量・診断の流れは人と AI が全文を読んで確認すること）")
    sys.exit(1 if hits else 0)


if __name__ == "__main__":
    main()
