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


if __name__ == "__main__":
    unittest.main()
