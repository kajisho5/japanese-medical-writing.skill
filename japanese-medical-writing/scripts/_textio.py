"""原稿ファイルの読み込み（Python 標準ライブラリのみ・通信なし）。

対応形式:
  .md / .txt  : UTF-8（BOM 付き可）、Shift_JIS（cp932）、EUC-JP を自動判別。改行は LF に統一
  .docx       : Word 文書。本文の段落を取り出し、見出しスタイルは Markdown の見出し（#）に、
                表は「| セル | セル |」形式に変換する。変更履歴の削除部分は除き、挿入部分は含める
"""
from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def setup_stdout() -> None:
    """Windows でリダイレクト・パイプ時に日本語の出力で落ちないようにする。"""
    for stream in (sys.stdout, sys.stderr):
        if not hasattr(stream, "reconfigure"):
            continue
        try:
            if stream.isatty():
                stream.reconfigure(errors="replace")
            else:
                stream.reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            pass


setup_stdout()


HEADING = re.compile(r"^#{1,6}[ \t\u3000]")  # 「#1 高血圧」のような問題リストは見出しではない


def is_heading(line: str) -> bool:
    return bool(HEADING.match(line))


def heading_level(line: str) -> int:
    return len(line) - len(line.lstrip("#")) if is_heading(line) else 0


def body_start(lines: list[str], section: re.Pattern[str] | None = None) -> tuple[int, bool]:
    """本文（表題・著者・所属を除く）が始まる行の添字と、「## 」見出しがない原稿かどうかを返す。

    「## 」見出しがあれば最初の「## 」から。なければ最初の見出しを表題とみなし、2つ目の見出しから
    （最初の見出しが section に当てはまる節名ならそこから）。見出しがなければ len(lines)。
    """
    for i, line in enumerate(lines):
        if line.startswith("## "):
            return i, False
    heads = [i for i, line in enumerate(lines) if is_heading(line)]
    if not heads:
        return len(lines), False
    if section is not None and section.match(lines[heads[0]]):
        return heads[0], True
    return (heads[1] if len(heads) > 1 else len(lines)), True


def _score(text: str) -> int:
    """和文として自然な文字の多さ。半角カナ・外字・制御文字は文字化けの兆候として減点する。"""
    good = bad = 0
    for c in text:
        o = ord(c)
        if 0x3040 <= o <= 0x30FF or 0x4E00 <= o <= 0x9FFF or 0x3000 <= o <= 0x303F or 0xFF01 <= o <= 0xFF5E or c in "\n\t" or 0x20 <= o < 0x7F:
            good += 1
        elif 0xFF61 <= o <= 0xFF9F or 0xE000 <= o <= 0xF8FF or o < 0x20 or 0x7F <= o < 0xA0:
            bad += 1
    return good - 5 * bad


def _decode(data: bytes, name: str) -> str:
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return data.decode("utf-16")
    if b"\x00" in data and len(data) % 2 == 0:
        # BOM なしの UTF-16（和文テキストに NUL は現れないので、NUL があれば UTF-16 とみなす）
        enc = "utf-16-le" if data[1::2].count(0) >= data[0::2].count(0) else "utf-16-be"
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            pass
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        pass
    # Shift_JIS と EUC-JP はどちらでも「読めてしまう」ことがあるので、和文らしさで選ぶ
    cands = []
    for enc in ("cp932", "euc_jp"):
        try:
            cands.append((_score(t := data.decode(enc)), enc == "cp932", t))
        except UnicodeDecodeError:
            continue
    if cands:
        return max(cands)[2]
    sys.exit(f"文字コードを判別できません（UTF-8 か Shift_JIS で保存し直してください）: {name}")


def _run_text(r: ET.Element) -> str:
    parts: list[str] = []
    for node in r:
        if node.tag == W + "t" and node.text:
            parts.append(node.text)
        elif node.tag == W + "tab":
            parts.append("\t")
        elif node.tag in (W + "br", W + "cr"):
            parts.append("\n")
    text = "".join(parts)
    va = r.find(f"{W}rPr/{W}vertAlign")
    if text.strip() and va is not None and va.get(W + "val") == "superscript":
        return f"^{text.strip()}^"  # 上付きの引用番号を本文の数字と区別する
    return text


def _para_text(p: ET.Element) -> str:
    out: list[str] = []
    for node in p.iter():
        if node.tag == W + "r":
            # 変更履歴で削除された部分（w:del 内の w:delText）は w:t を持たないので自然に除かれる
            out.append(_run_text(node))
    return "".join(out).replace("^^", "")


def _heading_level(p: ET.Element) -> int:
    ps = p.find(f"{W}pPr/{W}pStyle")
    if ps is None:
        return 0
    style = ps.get(W + "val", "")
    m = re.search(r"(?:Heading|heading|見出し)\s*(\d)", style)
    if m:
        return int(m.group(1))
    if style.lower() == "title" or style == "表題":
        return -1
    return 0


def _blocks(parent: ET.Element):
    """段落と表を文書順に返す。コンテンツコントロール（w:sdt）等の入れ物の中にも入る。"""
    for el in parent:
        if el.tag in (W + "p", W + "tbl"):
            yield el
        elif el.tag in (W + "sdt", W + "sdtContent", W + "customXml", W + "smartTag"):
            yield from _blocks(el)


def _docx_to_markdown(path: Path) -> str:
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml")
    root = ET.fromstring(xml)
    body = root.find(W + "body")
    lines: list[str] = []
    if body is None:
        return ""
    for el in _blocks(body):
        if el.tag == W + "p":
            text = _para_text(el)
            lvl = _heading_level(el)
            if lvl == -1 and text.strip():
                lines.append("# " + text.strip())
            elif lvl and text.strip():
                lines.append("#" * min(lvl + 1, 6) + " " + text.strip())
            else:
                lines.append(text)
        elif el.tag == W + "tbl":
            for tr in el.iter(W + "tr"):
                cells = [" ".join(_para_text(p) for p in tc.iter(W + "p")).strip() for tc in tr.iter(W + "tc")]
                lines.append("| " + " | ".join(cells) + " |")
            lines.append("")
    return "\n".join(lines)


def read_manuscript(path_str: str) -> str:
    path = Path(path_str)
    if not path.exists():
        sys.exit(f"ファイルが見つかりません: {path_str}")
    if path.suffix.lower() == ".docx":
        try:
            text = _docx_to_markdown(path)
        except (zipfile.BadZipFile, KeyError, ET.ParseError):
            sys.exit(f"Word ファイルとして読めません（.doc の古い形式は .docx で保存し直してください）: {path_str}")
    elif path.suffix.lower() in (".doc", ".pdf", ".rtf", ".pages"):
        sys.exit(f"{path.suffix} 形式は読めません。Word なら .docx、またはテキスト（.txt/.md）で保存し直してください: {path_str}")
    else:
        text = _decode(path.read_bytes(), path_str)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if not text.strip():
        sys.exit(f"ファイルの中身が空です（保存し忘れ・形式違いの可能性）: {path_str}")
    return text


def read_docx_extras(path_str: str) -> list[tuple[str, str]]:
    """本文以外の部分（ヘッダ・フッタ・脚注・文末脚注・コメント）と作成者情報を返す。"""
    out: list[tuple[str, str]] = []
    labels = {"header": "ヘッダ", "footer": "フッタ", "footnotes": "脚注", "endnotes": "文末脚注", "comments": "コメント"}
    with zipfile.ZipFile(path_str) as z:
        for name in z.namelist():
            m = re.match(r"word/(header|footer|footnotes|endnotes|comments)\d*\.xml$", name)
            if not m:
                continue
            root = ET.fromstring(z.read(name))
            text = "\n".join(_para_text(p) for p in root.iter(W + "p"))
            if text.strip():
                out.append((labels[m.group(1)], text))
        if "docProps/core.xml" in z.namelist():
            root = ET.fromstring(z.read("docProps/core.xml"))
            vals = []
            for el in root:
                tag = el.tag.split("}")[-1]
                if tag in ("creator", "lastModifiedBy") and el.text and el.text.strip():
                    vals.append(f"{tag}={el.text.strip()}")
            if vals:
                out.append(("作成者情報", "\n".join(vals)))
    return out
