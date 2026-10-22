"""バグ修正の回帰テスト（Python 標準ライブラリのみ）。

実行: python3 -m unittest discover -s tests -v   （リポジトリ直下で）
フィクスチャの人名・施設名・番号はすべて架空（見本太郎・架空病院など）。
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "japanese-medical-writing" / "scripts"


def run(script: str, *args: str) -> tuple[int, str]:
    r = subprocess.run([sys.executable, "-I", str(SCRIPTS / script), *args],
                       capture_output=True, text=True, encoding="utf-8")
    return r.returncode, r.stdout + r.stderr


def make_docx(path: Path, body_xml: str) -> None:
    ns = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>')
        z.writestr("word/document.xml", f'<?xml version="1.0" encoding="UTF-8"?><w:document {ns}><w:body>{body_xml}</w:body></w:document>')


def p(text: str, style: str | None = None, sup: bool = False) -> str:
    ps = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
    rpr = '<w:rPr><w:vertAlign w:val="superscript"/></w:rPr>' if sup else ""
    return f"<w:p>{ps}<w:r>{rpr}<w:t>{text}</w:t></w:r></w:p>"


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, text: str, name: str = "ms.md", encoding: str = "utf-8") -> str:
        f = self.dir / name
        f.write_bytes(text.encode(encoding))
        return str(f)


class RefsFixes(Base):
    REFS = "\n## 文献\n1) 見本太郎. 架空誌. 2020.\n"

    def test_duplicate_reference_number_fails(self):  # 1
        code, out = run("check_refs.py", self.write("# 題\n## 緒言\n既報がある1)。\n## 文献\n1) 見本太郎. 架空誌. 2020.\n1) 見本花子. 架空誌. 2021.\n"))
        self.assertEqual(code, 1, out)
        self.assertIn("重複", out)
        self.assertIn("ERROR 1 件", out)

    def test_entry_fullwidth_paren_and_no_space(self):  # 2
        for entry in ("1）見本太郎. 架空誌. 2020.", "1)見本太郎. 架空誌. 2020.", "1．見本太郎. 架空誌. 2020."):
            code, out = run("check_refs.py", self.write(f"# 題\n## 緒言\n既報がある1)。\n## 文献\n{entry}\n"))
            self.assertEqual(code, 0, entry + out)
            self.assertIn("文献リスト 1 件", out)

    def test_doi_continuation_line_is_not_an_entry(self):  # 2
        code, out = run("check_refs.py", self.write("# 題\n## 緒言\n既報がある1)。\n## 文献\n1) 見本太郎. 架空誌. 2020.\n10.1000/xyz123\n"))
        self.assertEqual(code, 0, out)

    def test_enumeration_is_not_citation(self):  # 3
        code, out = run("check_refs.py", self.write("# 題\n## 考察\n本例の特徴は、1)高齢、2)腎障害、3)多剤併用である。\n特徴は1)高齢である。\n"))
        self.assertEqual(code, 0, out)
        self.assertIn("引用番号も文献リストもない", out)

    def test_paren_citation_still_detected(self):  # 3
        code, out = run("check_refs.py", self.write("# 題\n## 緒言\n既報が報告されている1)。同様である2,3)。\n## 文献\n1) 見本太郎. 架空誌. 2020.\n"))
        self.assertEqual(code, 1, out)
        self.assertIn("本文の引用 2 が文献リストにない", out)
        self.assertIn("本文の引用 3 が文献リストにない", out)

    def test_superscript_powers_are_not_citations(self):  # 4
        code, out = run("check_refs.py", self.write("# 題\n## 症例\n白血球数 5.2×10^3^/μL、体表面積 1.5 m^2^、10^9^/L であった[1]。\n## 文献\n1. 見本太郎. 架空誌. 2020.\n"))
        self.assertEqual(code, 0, out)
        self.assertNotIn("混在", out)

    def test_superscript_citation_still_detected(self):  # 4
        code, out = run("check_refs.py", self.write("# 題\n## 緒言\n既報がある^2^。\n## 文献\n1. 見本太郎. 架空誌. 2020.\n"))
        self.assertEqual(code, 1, out)
        self.assertIn("本文の引用 2 が文献リストにない", out)

    def test_docx_superscript_power(self):  # 4
        f = self.dir / "ms.docx"
        body = (p("題", "Title") + p("症例", "Heading1")
                + '<w:p><w:r><w:t>白血球数 5.2×10</w:t></w:r><w:r><w:rPr><w:vertAlign w:val="superscript"/></w:rPr><w:t>3</w:t></w:r>'
                  '<w:r><w:t>/μL であった</w:t></w:r><w:r><w:rPr><w:vertAlign w:val="superscript"/></w:rPr><w:t>1</w:t></w:r><w:r><w:t>。</w:t></w:r></w:p>'
                + p("文献", "Heading1") + p("1. 見本太郎. 架空誌. 2020."))
        make_docx(f, body)
        code, out = run("check_refs.py", str(f))
        self.assertEqual(code, 0, out)

    def test_problem_list_is_not_heading(self):  # 18
        code, out = run("check_refs.py", self.write("# 題\n## 症例\n#1 高血圧\n既報がある[2]。\n## 文献\n1. 見本太郎. 架空誌. 2020.\n"))
        self.assertEqual(code, 1, out)
        self.assertIn("本文の引用 2 が文献リストにない", out)

    def test_only_h1_headings(self):  # 19
        code, out = run("check_refs.py", self.write("# 題\n# 緒言\n既報がある[3]。\n"))
        self.assertEqual(code, 1, out)
        self.assertIn("文献リストが見つからない", out)
        code, out = run("check_refs.py", self.write("# 題\n# 緒言\n既報がある[1]。\n# 文献\n1. 見本太郎. 架空誌. 2020.\n"))
        self.assertEqual(code, 0, out)


class NumbersFixes(Base):
    def test_structured_abstract_subheadings(self):  # 7
        code, out = run("check_numbers.py", self.write("# 題\n## 要旨\n### 目的\n対象は42例。\n### 結果\n改善は30例。\n## 結果\n対象は40例、改善は30例。\n"))
        self.assertEqual(code, 1, out)
        self.assertIn("抄録の数値 42", out)
        self.assertNotIn("抄録の数値 30", out)

    def test_negative_after_japanese(self):  # 8
        code, out = run("check_numbers.py", self.write("# 題\n## 要旨\n変化量は−1.5であった。\n## 結果\n変化量は1.5であった。\n"))
        self.assertEqual(code, 1, out)
        self.assertIn("-1.5", out)
        code, out = run("check_numbers.py", self.write("# 題\n## 要旨\n変化量は-1.5、差は1.2-0.3、範囲 1.2–3.4。\n## 結果\n変化量は−1.5、差は1.2–0.3、範囲 1.2-3.4。\n"))
        self.assertEqual(code, 0, out)

    def test_ci_level_after_japanese(self):  # 13
        code, out = run("check_numbers.py", self.write("# 題\n## 要旨\nオッズ比は2.1（オッズ比の95%信頼区間 1.2–3.4）。\n## 結果\nオッズ比は2.1（1.2–3.4）。\n"))
        self.assertEqual(code, 0, out)

    def test_comma_separated_decimals(self):  # 14
        code, out = run("check_numbers.py", self.write("# 題\n## 要旨\nHR 0.62（0.45,0.89）、症例 1,234 例。\n## 結果\nHR 0.62（0.45–0.89）、症例 1234 例。\n"))
        self.assertEqual(code, 0, out)

    def test_fullwidth_digits(self):  # 21
        code, out = run("check_numbers.py", self.write("# 題\n## 要旨\n対象は４２例。\n## 結果\n対象は42例。\n"))
        self.assertEqual(code, 0, out)

    def test_problem_list_and_h1_only(self):  # 18, 19
        code, out = run("check_numbers.py", self.write("# 題\n## 要旨\n#1 高血圧\n対象は42例。\n## 結果\n#1 高血圧\n対象は42例。\n"))
        self.assertEqual(code, 0, out)
        self.assertIn("抄録の数値 2 個", out)
        code, out = run("check_numbers.py", self.write("# 要旨\n対象は42例。\n# 緒言\n対象は40例。\n"))
        self.assertEqual(code, 1, out)
        self.assertIn("抄録の数値 42", out)


class FormatFixes(Base):
    def fmt(self, text: str, *opts: str) -> str:
        src = self.write(text)
        out = self.dir / "out.md"
        code, msg = run("format_ja.py", *opts, "-o", str(out), src)
        self.assertEqual(code, 0, msg)
        return out.read_text(encoding="utf-8")

    def test_heading_numbers_keep_period(self):  # 5
        out = self.fmt("# 題\n## １．はじめに\n表１．患者背景．\n", "--zenkaku", "--punct", "ten")
        self.assertIn("## 1．はじめに", out)
        self.assertIn("表1．患者背景。", out)
        self.assertNotIn("1。", out)

    def test_unit_space_protects_urls_and_paths(self):  # 6
        out = self.fmt("# 題\n## 本文\n詳細は https://example.org/drug/10mg.html を参照。投与量は5mg。\n![図1](img/slice_5mm.png)\n[資料](a/10mg.pdf) と file_5mg と /20mg と abc-3mg。\n", "--unit-space")
        self.assertIn("https://example.org/drug/10mg.html", out)
        self.assertIn("img/slice_5mm.png", out)
        self.assertIn("(a/10mg.pdf)", out)
        self.assertIn("file_5mg", out)
        self.assertIn("/20mg", out)
        self.assertIn("abc-3mg", out)
        self.assertIn("5 mg。", out)

    def test_fullwidth_decimal(self):  # 16
        out = self.fmt("# 題\n## 本文\n投与量は０．５mgであった。\n", "--zenkaku", "--unit-space")
        self.assertIn("0.5 mg", out)

    def test_negative_ranges(self):  # 17
        out = self.fmt("# 題\n## 本文\n範囲 −3〜−1、1〜3。\n", "--range", "dash")
        self.assertIn("−3–−1", out)
        self.assertIn("1–3", out)
        out = self.fmt("# 題\n## 本文\n範囲 −3–−1、1–3。\n", "--range", "tilde")
        self.assertIn("−3〜−1", out)


class LintFixes(Base):
    def test_desu_masu_only_is_not_mixed(self):  # 9
        code, out = run("lint_ja.py", self.write("# 題\n## 本文\n検査を行いました。結果は良好でした。経過を見ました。\n"))
        self.assertEqual(code, 0, out)
        self.assertNotIn("混在", out)
        self.assertIn("全体がです・ます調", out)

    def test_real_mix_still_detected(self):  # 9
        code, out = run("lint_ja.py", self.write("# 題\n## 本文\n検査を行いました。結果は良好であった。\n"))
        self.assertEqual(code, 1, out)
        self.assertIn("です・ます調が混在", out)

    def test_headings_are_checked(self):  # 12
        code, out = run("lint_ja.py", self.write("# ＣＴ所見の１例\n## 緒言\n本文である。\n## 文献\n1. 見本太郎. 架空誌. 2020.\n"))
        self.assertEqual(code, 1, out)
        self.assertIn("L1", out)
        self.assertIn("全角英数字", out)

    def test_problem_list_line_is_linted(self):  # 18
        code, out = run("lint_ja.py", self.write("# 題\n## 症例\n#1 高血圧（ＨＴ）\n"))
        self.assertEqual(code, 1, out)
        self.assertIn("L3", out)

    def test_no_echo_hides_manuscript_strings(self):  # 23
        code, out = run("lint_ja.py", "--no-echo", self.write("# 題\n## 本文\n値はＱＷ7であった。投与量は5mgであった。ZQXV を用いた。TODO である。\n"))
        self.assertEqual(code, 1, out)
        for secret in ("Ｑ", "5mg", "ZQXV", "TODO"):
            self.assertNotIn(secret, out)
        self.assertIn("全角英数字", out)
        self.assertIn("仮置き", out)

    def test_karyotype_not_placeholder(self):
        code, out = run("lint_ja.py", self.write("# 題\n## 症例\n染色体核型は46,XXであった。\n"))
        self.assertEqual(code, 0, out)
        self.assertNotIn("XX", out)


class TermsFixes(Base):
    def test_title_and_headings_checked(self):  # 12
        code, out = run("check_terms.py", self.write("# 痴呆を呈した1例\n## 緒言\n本文である。\n## 文献\n1. 見本太郎. 痴呆の研究. 架空誌. 2020.\n"))
        self.assertEqual(code, 1, out)
        self.assertIn("L1", out)
        self.assertNotIn("L5", out)


class ReadingFixes(Base):
    def test_docx_content_controls(self):  # 10
        f = self.dir / "ms.docx"
        body = (p("題", "Title") + p("緒言", "Heading1")
                + "<w:sdt><w:sdtContent>" + p("痴呆を呈した症例である。") + "</w:sdtContent></w:sdt>"
                + "<w:sdt><w:sdtContent><w:sdt><w:sdtContent>" + p("頸部と頚部がある。") + "</w:sdtContent></w:sdt></w:sdtContent></w:sdt>"
                + "<w:tbl><w:tr><w:tc><w:sdt><w:sdtContent>" + p("老人性痴呆") + "</w:sdtContent></w:sdt></w:tc></w:tr></w:tbl>")
        make_docx(f, body)
        code, out = run("check_terms.py", str(f))
        self.assertEqual(code, 1, out)
        self.assertIn("L3", out)
        self.assertIn("表記ゆれ", out)
        self.assertGreaterEqual(out.count("ERROR"), 2, out)

    def test_euc_jp_kana_heavy(self):  # 20
        for body in ("かんじゃはびょういんにいる。ちほうをていした。", "患者は外来を受診した。痴呆を呈した。"):
            f = self.write(f"# だい\n## はじめに\n{body}\n", encoding="euc_jp")
            code, out = run("check_terms.py", f)
            self.assertNotIn("判別できません", out)
            if "痴呆" in body:
                self.assertEqual(code, 1, out)
        f = self.write("# 題\n## 緒言\n痴呆を呈した見本太郎さんの症例である。\n", encoding="cp932")
        code, out = run("check_terms.py", f)
        self.assertEqual(code, 1, out)

    def test_euc_jp_decodes_correctly(self):  # 20
        f = self.write("# だい\n## はじめに\nかんじゃはびょういんにいる。\n", encoding="euc_jp")
        sys.path.insert(0, str(SCRIPTS))
        try:
            import _textio
            self.assertIn("かんじゃはびょういんにいる。", _textio.read_manuscript(f))
        finally:
            sys.path.remove(str(SCRIPTS))


class PrivacyFixes(Base):
    def test_false_positives(self):  # 11
        code, out = run("check_privacy.py", self.write(
            "# 題\n## 症例\n右殿部に腫瘤を認めた。左殿部も同様。\n1日尿量は500-1500 mLで推移した。\n"
            "意識レベルは Glasgow Coma Scale で E4V5M6、Barthel Index は 60 点。Kaplan Meier 法で解析した。\n"
            "赤ちゃんの体重は 2,500 g であった。\nがん診療連携拠点病院へ紹介した。特定機能病院でもある。\n"))
        self.assertEqual(code, 0, out)

    def test_real_identifiers_still_detected(self):  # 11
        code, out = run("check_privacy.py", self.write(
            "# 題\n## 症例\n見本太郎さんは架空病院に入院した。〒123-4567。郵便 123-4567 の住所。Taro Mihon was admitted.\n見本殿へ。\n"))
        self.assertEqual(code, 1, out)
        for needle in ("見本太郎さん", "架空病院", "〒123-4567", "「123-4567」", "Taro Mihon", "見本殿"):
            self.assertIn(needle, out)


class SourcesFixes(Base):
    def _copy(self, checked_on: str) -> Path:
        scripts = self.dir / "skill" / "scripts"
        refs = self.dir / "skill" / "references"
        scripts.mkdir(parents=True)
        refs.mkdir()
        for n in ("sources.py", "_textio.py"):
            shutil.copy(SCRIPTS / n, scripts / n)
        reg = {"updated": "2026-01-01", "sources": [
            {"id": "S001", "category": "国内", "title": "架空指針", "url": "", "kind": "一次", "status": "確認済",
             "checked_on": checked_on, "used_in": ["references/ethics-coi.md"]},
            {"id": "S002", "category": "国内", "title": "架空規定", "url": "", "kind": "一次", "status": "確認済",
             "checked_on": "2020-01-01", "used_in": ["references/guidelines.md"]}]}
        (refs / "source-registry.json").write_text(json.dumps(reg, ensure_ascii=False), encoding="utf-8")
        return scripts / "sources.py"

    def _run(self, script: Path, *args: str) -> tuple[int, str]:
        r = subprocess.run([sys.executable, "-I", str(script), *args], capture_output=True, text=True, encoding="utf-8")
        return r.returncode, r.stdout + r.stderr

    def test_check_version_rejects_bad_date(self):  # 15
        script = self._copy("2026-01-01")
        before = (script.parent.parent / "references" / "source-registry.json").read_text(encoding="utf-8")
        for bad in ("2027/01/10", "20270110", "2027-02-30", "tomorrow"):
            code, out = self._run(script, "check-version", "S001", "--date", bad)
            self.assertNotEqual(code, 0, out)
            self.assertIn("YYYY-MM-DD", out)
        self.assertEqual(before, (script.parent.parent / "references" / "source-registry.json").read_text(encoding="utf-8"))

    def test_stale_survives_bad_checked_on(self):  # 15
        script = self._copy("2026/1/1")
        code, out = self._run(script, "stale")
        self.assertEqual(code, 0, out)
        self.assertNotIn("Traceback", out)
        self.assertIn("S001", out)
        self.assertIn("要修正", out)
        self.assertIn("S002", out)

    def test_used_accepts_windows_paths(self):  # 22
        script = self._copy("2026-01-01")
        code, out = self._run(script, "used", "references\\ethics-coi.md")
        self.assertEqual(code, 0, out)
        self.assertIn("S001", out)
        self.assertIn("1 件", out)


class CheckAllFixes(Base):
    def test_known_and_ignore_pass_through(self):  # 24
        f = self.write("# 題\n## 要旨\nZQXV を用いた。対象は2031例。\n## 結果\nZQXV を用いた。対象は40例である。\n")
        code, out = run("check_all.py", f)
        self.assertIn("ZQXV", out)
        self.assertIn("抄録の数値 2031", out)
        code, out = run("check_all.py", "--known", "ZQXV", "--ignore", "2031", f)
        self.assertNotIn("略語「ZQXV」", out)
        self.assertNotIn("抄録の数値 2031", out)

    def test_double_check_line(self):
        f = self.write("# 題\n## 緒言\n本文である。\n")
        _, out = run("check_all.py", f)
        lines = out.splitlines()
        i = next(n for n, x in enumerate(lines) if x.startswith("※ 機械チェックは一部しか見ない。"))
        self.assertEqual(lines[i + 1], "※ 最終確認は必ず人の目で、1人だけで済ませず、共著者など別の人も確認すること（ダブルチェック）。")


class PackageFixes(Base):
    def test_hidden_files_excluded(self):  # 25
        root = self.dir / "repo"
        (root / "tools").mkdir(parents=True)
        shutil.copy(ROOT / "tools" / "package.py", root / "tools" / "package.py")
        skill = root / "japanese-medical-writing"
        (skill / "scripts" / "__pycache__").mkdir(parents=True)
        (skill / ".hidden").mkdir()
        (skill / "SKILL.md").write_text("x", encoding="utf-8")
        (skill / "scripts" / "a.py").write_text("x", encoding="utf-8")
        (skill / "scripts" / "__pycache__" / "a.cpython.pyc").write_text("x", encoding="utf-8")
        (skill / ".DS_Store").write_text("x", encoding="utf-8")
        (skill / "scripts" / ".env").write_text("x", encoding="utf-8")
        (skill / ".hidden" / "b.md").write_text("x", encoding="utf-8")
        r = subprocess.run([sys.executable, "-I", str(root / "tools" / "package.py")], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(r.returncode, 0, r.stderr)
        with zipfile.ZipFile(root / "dist" / "japanese-medical-writing.skill") as z:
            names = sorted(z.namelist())
        self.assertEqual(names, ["japanese-medical-writing/SKILL.md", "japanese-medical-writing/scripts/a.py"])


if __name__ == "__main__":
    unittest.main()
