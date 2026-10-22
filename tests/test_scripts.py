"""点検ツールの自動テスト（Python 標準ライブラリのみ）。

実行: python3 -m unittest discover -s tests -v   （リポジトリ直下で）
フィクスチャの人名・施設名・番号はすべて架空。
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "japanese-medical-writing" / "scripts"
FIX = Path(__file__).resolve().parent / "fixtures"


def run(script: str, *args: str) -> tuple[int, str]:
    r = subprocess.run([sys.executable, "-I", str(SCRIPTS / script), *args],
                       capture_output=True, text=True, encoding="utf-8")
    return r.returncode, r.stdout + r.stderr


def make_docx(path: Path, body_xml: str, extra: dict[str, str] | None = None) -> None:
    ns = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>')
        z.writestr("word/document.xml", f'<?xml version="1.0" encoding="UTF-8"?><w:document {ns}><w:body>{body_xml}</w:body></w:document>')
        for name, xml in (extra or {}).items():
            z.writestr(name, xml)


def p(text: str, style: str | None = None, sup: bool = False) -> str:
    ps = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
    rpr = '<w:rPr><w:vertAlign w:val="superscript"/></w:rPr>' if sup else ""
    return f"<w:p>{ps}<w:r>{rpr}<w:t>{text}</w:t></w:r></w:p>"


class Lint(unittest.TestCase):
    def test_good_is_clean(self):
        code, out = run("lint_ja.py", str(FIX / "good.md"))
        self.assertEqual(code, 0, out)
        self.assertIn("ERROR 0 件", out)

    def test_bad_detects_errors(self):
        code, out = run("lint_ja.py", str(FIX / "bad.md"))
        self.assertEqual(code, 1)
        for needle in ("全角英数字", "p = 0.000", "です・ます調が混在", "読点", "未解決マーカー"):
            self.assertIn(needle, out)

    def test_draft_mode_counts_markers_only(self):
        code, out = run("lint_ja.py", "--draft", str(FIX / "bad.md"))
        self.assertIn("--draft のため", out)

    def test_priority_and_overclaim(self):
        _, out = run("lint_ja.py", str(FIX / "prio.md"))
        self.assertIn("検索根拠がない", out)
        self.assertIn("証明", out)

    def test_no_echo(self):
        _, out = run("lint_ja.py", "--no-echo", str(FIX / "prio.md"))
        self.assertNotIn("本邦初の報告である", out)


class SecondaryMarker(unittest.TestCase):
    def test_secondary_marker_blocks_final_but_not_draft(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "s.md"
            f.write_text("## 考察\n本制度は改正された【二次情報：架空新聞 2026年1月1日】。\n", encoding="utf-8")
            code, out = run("lint_ja.py", str(f))
            self.assertEqual(code, 1)
            self.assertIn("【二次情報】1 件", out)
            code, out = run("lint_ja.py", "--draft", str(f))
            self.assertEqual(code, 0, out)
            code, out = run("check_privacy.py", str(f))
            self.assertEqual(code, 0, out)  # 報道日は患者の日付として拾わない


class Refs(unittest.TestCase):
    def test_uncited_reference(self):
        code, out = run("check_refs.py", str(FIX / "bad.md"))
        self.assertEqual(code, 1)
        self.assertIn("文献 3 が本文で引用されていない", out)

    def test_figures(self):
        code, out = run("check_refs.py", str(FIX / "fig.md"))
        self.assertEqual(code, 1)
        self.assertIn("表3に対応するタイトル行がない", out)
        self.assertIn("表2が本文で参照されていない", out)
        self.assertIn("図1が本文で参照されていない", out)


class Numbers(unittest.TestCase):
    def test_percentage(self):
        code, out = run("check_numbers.py", str(FIX / "pct.md"))
        self.assertEqual(code, 1)
        self.assertIn("5/48 = 10.4%", out)
        self.assertNotIn("12/48", out)

    def test_sign_and_japanese_fraction(self):
        _, out = run("check_numbers.py", str(FIX / "num2.md"))
        self.assertIn("-0.5", out)
        self.assertIn("12/45 = 26.7% だが 30.0%", out)
        self.assertNotIn("2.74", out)  # 範囲の「–」を符号と誤認しない

    def test_good(self):
        code, out = run("check_numbers.py", str(FIX / "good.md"))
        self.assertEqual(code, 0, out)


class Privacy(unittest.TestCase):
    def test_many_identifiers(self):
        code, out = run("check_privacy.py", str(FIX / "pii_many.md"))
        self.assertEqual(code, 1)
        for needle in ("令和7年4月3日", "R7.4.3", "93歳", "保険者番号", "123456789012", "0312345678",
                       "512号室", "架空総合病院", "T.M.", "見本先生", "mihon@example.com", "S7.4.3"):
            self.assertIn(needle, out, needle)
        self.assertNotIn("X年Y月", out)

    def test_medical_prose_no_false_positive(self):
        code, out = run("check_privacy.py", str(FIX / "good_medical_prose.md"))
        self.assertEqual(code, 0, out)

    def test_exclusion_does_not_hide_neighbors(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "x.md"
            f.write_text("## 症例\n見本太郎さん（倫理承認番号 2025-01）が来院した。\nカルテ番号: 7654321 （UMIN登録済）\n", encoding="utf-8")
            _, out = run("check_privacy.py", str(f))
        self.assertIn("見本太郎さん", out)
        self.assertIn("カルテ番号: 7654321", out)
        self.assertNotIn("2025-01", out)

    def test_headings_comments_markers_are_scanned(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "x.md"
            f.write_text("# 見本太郎さんの症例\n<!-- カルテ番号 1234567 -->\n## 症例\n【要確認：2025年4月3日の値】\n", encoding="utf-8")
            _, out = run("check_privacy.py", str(f))
        for needle in ("見本太郎さん", "カルテ番号 1234567", "2025年4月3日"):
            self.assertIn(needle, out)

    def test_author_section_names_allowed(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "x.md"
            f.write_text("## 著者\nTaro Mihon, Hanako Mihon\n架空大学病院\n## 症例\n70歳代男性。\n", encoding="utf-8")
            code, out = run("check_privacy.py", str(f))
        self.assertEqual(code, 0, out)


class Reading(unittest.TestCase):
    def test_encodings(self):
        src = (FIX / "bad.md").read_text(encoding="utf-8").replace("–", "-")
        with tempfile.TemporaryDirectory() as d:
            for name, data in (("sjis.txt", src.replace("\n", "\r\n").encode("cp932")),
                               ("bom.md", b"\xef\xbb\xbf" + src.encode("utf-8")),
                               ("euc.md", src.encode("euc_jp")),
                               ("u16.md", src.encode("utf-16"))):
                f = Path(d) / name
                f.write_bytes(data)
                code, out = run("lint_ja.py", str(f))
                self.assertIn("全角英数字", out, name)

    def test_empty_and_unsupported(self):
        with tempfile.TemporaryDirectory() as d:
            e = Path(d) / "e.md"
            e.write_text("", encoding="utf-8")
            code, out = run("lint_ja.py", str(e))
            self.assertNotEqual(code, 0)
            self.assertIn("空", out)
            doc = Path(d) / "a.doc"
            doc.write_bytes(b"\xd0\xcf\x11\xe0")
            code, out = run("lint_ja.py", str(doc))
            self.assertNotEqual(code, 0)
            self.assertIn(".docx", out)

    def test_docx_body_superscript_trackchanges_extras(self):
        body = (p("架空研究", "Title") + p("はじめに", "Heading1")
                + '<w:p><w:r><w:t>架空疾患は高齢者に多い</w:t></w:r><w:r><w:rPr><w:vertAlign w:val="superscript"/></w:rPr><w:t>1</w:t></w:r><w:r><w:t>。</w:t></w:r></w:p>'
                + '<w:p><w:del><w:r><w:delText>削除済みの見本次郎さん。</w:delText></w:r></w:del><w:ins><w:r><w:t>挿入された文である。</w:t></w:r></w:ins></w:p>'
                + p("文献", "Heading1") + p("1) 架空太郎. 架空誌. 2023;1:1-2."))
        extra = {
            "word/header1.xml": '<w:hdr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:p><w:r><w:t>カルテ番号 1234567</w:t></w:r></w:p></w:hdr>',
            "docProps/core.xml": '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:creator>見本太郎</dc:creator></cp:coreProperties>',
        }
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "ms.docx"
            make_docx(f, body, extra)
            code, out = run("check_refs.py", str(f))
            self.assertEqual(code, 0, out)  # 上付き ^1^ を引用として認識
            code, out = run("check_privacy.py", str(f))
            self.assertIn("[ヘッダ]", out)
            self.assertIn("作成者情報", out)
            self.assertNotIn("見本次郎", out)  # 削除済みの文は読まない


class Format(unittest.TestCase):
    def test_format_does_not_touch_markers_and_original(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "a.md"
            src = "## 結果\n対象は２０２４年の48例で、5mg投与した。範囲は1〜3。【要確認：5mgの根拠、２回目】\n値は12．3であった．\n"
            f.write_text(src, encoding="utf-8")
            code, out = run("format_ja.py", "--zenkaku", "--unit-space", "--punct", "comma", "--range", "dash", str(f))
            self.assertEqual(code, 0, out)
            self.assertEqual(f.read_text(encoding="utf-8"), src)  # 元ファイルは不変
            res = (Path(d) / "a.formatted.md").read_text(encoding="utf-8")
            self.assertIn("2024年の48例で，5 mg投与した．範囲は1–3．", res)
            self.assertIn("【要確認：5mgの根拠、２回目】", res)  # マーカー内は不変
            code, out = run("format_ja.py", "--punct", "ten", "-o", str(Path(d) / "b.md"), str(Path(d) / "a.formatted.md"))
            res2 = (Path(d) / "b.md").read_text(encoding="utf-8")
            self.assertIn("値は12．3であった。", res2)  # 全角の小数点は句点にしない

    def test_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "a.md"
            f.write_text("## 本文\nテスト。\n", encoding="utf-8")
            code, out = run("format_ja.py", "--punct", "comma", "-o", str(f), str(f))
            self.assertNotEqual(code, 0)


class Terms(unittest.TestCase):
    def test_old_terms_and_variants(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "t.md"
            f.write_text("## 症例\n痴呆と精神分裂病の既往。看護婦が対応。双極性障害、NAFLD。頸部と頚部。自閉スペクトラム症。\n## 文献\n1) 架空. 痴呆の研究. 架空誌. 1990;1:1-2.\n", encoding="utf-8")
            code, out = run("check_terms.py", str(f))
        self.assertEqual(code, 1)
        for needle in ("認知症", "統合失調症", "看護師", "双極症", "MASLD", "表記ゆれ"):
            self.assertIn(needle, out)
        self.assertNotIn("L4", out)  # 文献の題名は対象外
        self.assertNotIn("自閉スペクトラム症」→", out)

    def test_clean_prose(self):
        code, out = run("check_terms.py", str(FIX / "good_medical_prose.md"))
        self.assertEqual(code, 0, out)


class Registry(unittest.TestCase):
    def test_registry_is_consistent(self):
        import json
        reg = json.loads((ROOT / "japanese-medical-writing" / "references" / "source-registry.json").read_text(encoding="utf-8"))
        ids = [s["id"] for s in reg["sources"]]
        self.assertEqual(len(ids), len(set(ids)))
        for s in reg["sources"]:
            self.assertIn(s["kind"], ("一次", "二次", "ツール文書"))
            self.assertIn(s["status"], ("確認済", "一部確認", "未確認"))
        code, out = run("sources.py", "find", "CONSORT")
        self.assertEqual(code, 0, out)
        self.assertIn("CONSORT 2025", out)


class All(unittest.TestCase):
    def test_check_all_good(self):
        code, out = run("check_all.py", str(FIX / "good.md"))
        self.assertEqual(code, 0, out)

    def test_check_all_bad(self):
        code, out = run("check_all.py", str(FIX / "bad.md"))
        self.assertEqual(code, 1)
        self.assertIn("要対応", out)


class Templates(unittest.TestCase):
    def test_templates_have_no_identifiers_or_lint_errors(self):
        for t in (ROOT / "japanese-medical-writing" / "assets" / "templates").glob("*.md"):
            code, out = run("check_privacy.py", str(t))
            self.assertEqual(code, 0, f"{t.name}: {out}")
            code, out = run("lint_ja.py", "--draft", "--allow-desu", str(t))
            self.assertIn("ERROR 0 件", out, t.name)

    def test_case_report_template_has_no_asserted_consent(self):
        s = (ROOT / "japanese-medical-writing" / "assets" / "templates" / "case-report.md").read_text(encoding="utf-8")
        body = "\n".join(l for l in s.splitlines() if not l.strip().startswith("<!--"))
        self.assertNotIn("同意を得た。", body)


class Consistency(unittest.TestCase):
    def test_detects_side_direction_finding_and_pathology(self):
        code, out = run("check_consistency.py", str(FIX / "inconsistent.md"))
        self.assertEqual(code, 1)
        for s in ("CHECK 左右：「股関節」", "内旋（L4、L7）と外旋（L13）", "「Patrickテスト」が陽性", "組織型が複数", "分化度が複数"):
            self.assertIn(s, out)

    def test_side_by_side_rom_and_same_histology_are_not_flagged(self):
        code, out = run("check_consistency.py", str(FIX / "consistent.md"))
        self.assertEqual(code, 0, out)

    def test_reference_section_and_bilateral_are_ignored(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "m.md"
            f.write_text("# 架空\n\n## 症例\n両側股関節に疼痛。右股関節と左股関節の可動域は同等。\n\n"
                         "## 文献\n1. 架空. 腺癌と扁平上皮癌. 架空誌. 2020.\n", encoding="utf-8")
            code, out = run("check_consistency.py", str(f))
        self.assertEqual(code, 0, out)

    def test_no_echo_hides_test_names(self):
        code, out = run("check_consistency.py", "--no-echo", str(FIX / "inconsistent.md"))
        self.assertNotIn("Patrick", out)
        self.assertIn("検査・徴候が陽性", out)

    def _check(self, body: str) -> tuple[int, str]:
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "m.md"
            f.write_text("# 架空\n\n" + body, encoding="utf-8")
            return run("check_consistency.py", str(f))

    def test_false_positives_found_in_bug_check(self):
        cases = [
            "## 症例\n右膝関節の可動域は屈曲120°、伸展0°であった。\n\n## 経過\n術後3か月で屈曲130°まで改善した。伸展制限はなかった。\n",
            "## 症例\n右肺に結節を認めた。左肺に異常はなかった。\n",
            "## 症例\n生検で腺癌と診断した。扁平上皮癌の成分は認めなかった。\n",
            "## 症例\n右股関節に疼痛があり、左股関節に異常はなかった。\n",
            "## 症例\n外反母趾の手術歴あり。内反制限を認めた。\n",
            "## 症例\n良性発作性頭位めまい症の既往。悪性腫瘍は否定的であった。\n",
        ]
        for body in cases:
            code, out = self._check(body)
            self.assertEqual(code, 0, f"{body}\n{out}")

    def test_misses_found_in_bug_check(self):
        cases = [
            ("## 症例\n右股関節痛で受診。\n\n## 経過\n術後、内旋制限は残存した。\n\n## 考察\n股関節の外旋制限が主体であった。\n", "内旋"),
            ("## 症例\n左膝に腫脹を認めた。\n\n## 考察\n右膝関節の腫脹は軽快した。\n", "膝関節"),
            ("## Abstract\nInternal rotation of the right hip was limited.\n\n## 症例\n左股関節の内旋制限。\n", "左右"),
            ("## Abstract\nA moderately differentiated adenocarcinoma.\n\n## 症例\n生検で高分化腺癌。\n", "分化度"),
            ("## 症例\n右下肢伸展挙上テストは陽性。\n\n## 経過\n下肢伸展挙上テストは陰性となった。\n", "陽性"),
        ]
        for body, expect in cases:
            code, out = self._check(body)
            self.assertEqual(code, 1, f"{body}\n{out}")
            self.assertIn(expect, out)

    def test_realistic_consistent_case_has_no_check(self):
        code, out = run("check_consistency.py", str(FIX / "realistic_case.md"))
        self.assertEqual(code, 0, out)

    def test_error_types_are_detected_in_realistic_case(self):
        base = (FIX / "realistic_case.md").read_text(encoding="utf-8")
        mutations = [
            ("本例でも左被殻の出血により右片麻痺", "本例でも左被殻の出血により左片麻痺", "病変側と麻痺側"),
            ("0.3 mg/dLから12.4 mg/dLに上昇", "0.3 mg/dLから12.4 mg/dLに低下", "数値と向き"),
            ("WBCも6200/μLまで減少", "WBCは13800/μLから6200/μLに増加", "数値と向き"),
            ("CRPは12.4 mg/dL、WBC", "CRPは124 mg/L、WBC", "単位の混在"),
            ("アムロジピン 5 mgを内服していた。", "アムロジピン 5 mgを内服していた。アムロジピン 5 μgを継続した。", "薬剤の単位"),
            ("第10病日にはCRP", "第6病日にはCRP", "時系列"),
        ]
        for old, new, expect in mutations:
            self.assertIn(old, base)
            code, out = self._check(base.replace(old, new).split("\n", 2)[2])
            self.assertEqual(code, 1, f"{new}\n{out}")
            self.assertIn(expect, out, new)

    def test_drug_names_hidden_with_no_echo(self):
        code, out = self._check("## 症例\nフェンタニル 100 μgを静注。\n\n## 経過\nフェンタニル 100 mgを投与。\n")
        self.assertIn("フェンタニル", out)
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "m.md"
            f.write_text("# 架空\n\n## 症例\nフェンタニル 100 μgを静注。\n\n## 経過\nフェンタニル 100 mgを投与。\n", encoding="utf-8")
            code, out = run("check_consistency.py", "--no-echo", str(f))
        self.assertEqual(code, 1)
        self.assertNotIn("フェンタニル", out)

    def test_practice_case_report_has_no_false_positive(self):
        code, out = run("check_consistency.py", str(ROOT / "examples" / "case-report-practice" / "01_manuscript.md"))
        self.assertEqual(code, 0, out)


if __name__ == "__main__":
    unittest.main()
