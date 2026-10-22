"""仕様（SPEC）の自動テスト（Python 標準ライブラリのみ）。

scripts/_contract.py が出す仕様と、実際のスクリプト・SKILL.md・出典台帳・用語データが
食い違っていないかを確認する。どれかがずれたら CI が落ちる。説明は SPEC.md。

実行: python3 -m unittest discover -s tests -v   （リポジトリ直下で）
CLI のスナップショットを意図して更新するとき: UPDATE_CLI_SNAPSHOT=1 python3 -m unittest tests.test_contract
"""
from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "japanese-medical-writing"
SCRIPTS = SKILL / "scripts"
SNAPSHOT = Path(__file__).resolve().parent / "fixtures" / "cli_snapshot.json"
NETWORK_MODULES = {"urllib", "http", "socket", "ssl", "ftplib", "smtplib", "poplib", "imaplib", "telnetlib",
                   "xmlrpc", "requests", "httpx", "aiohttp", "urllib3", "webbrowser", "asyncio"}


def contract() -> dict:
    r = subprocess.run([sys.executable, "-I", str(SCRIPTS / "_contract.py"), "--json"],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


C = contract()
REG = json.loads((SKILL / "references" / "source-registry.json").read_text(encoding="utf-8"))
REG_BY_ID = {s["id"]: s for s in REG["sources"]}
REG_URLS = {s["url"] for s in REG["sources"] if s["url"]} | {s.get("watch_url") for s in REG["sources"] if s.get("watch_url")}
TERMS = json.loads((SKILL / "assets" / "term-changes.json").read_text(encoding="utf-8"))


def imports_of(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            out.add(node.module.split(".")[0])
    return out


class Contract(unittest.TestCase):
    def test_every_tool_has_meta(self):
        for t in C["tools"]:
            self.assertIn(t.get("role"), C["roles"], f"{t['script']} に TOOL_META がない（scripts/_contract.py）")
            self.assertIn(t.get("echo"), C["echo_policies"], t["script"])
            self.assertTrue(t.get("purpose") and t.get("intents") and t.get("limits"), t["script"])

    def test_scripts_never_import_network_modules(self):
        for p in SCRIPTS.glob("*.py"):
            bad = imports_of(p) & NETWORK_MODULES
            self.assertFalse(bad, f"{p.name} が通信用モジュールを import している：{bad}")

    def test_scripts_use_only_the_standard_library(self):
        local = {p.stem for p in SCRIPTS.glob("*.py")}
        stdlib = getattr(sys, "stdlib_module_names", None)
        if stdlib is None:  # Python 3.9
            self.skipTest("sys.stdlib_module_names は 3.10 以降")
        for p in SCRIPTS.glob("*.py"):
            extra = imports_of(p) - set(stdlib) - local - {"__future__"}
            self.assertFalse(extra, f"{p.name} が標準ライブラリ以外を import している：{extra}")

    def test_tools_that_echo_text_accept_no_echo(self):
        for t in C["tools"]:
            names = {a["name"] for a in t["input_schema"]["arguments"]}
            if t["echo"] in ("unless_no_echo", "dictionary_terms_only"):
                self.assertIn("--no-echo", names, t["script"])
        src = (SCRIPTS / "check_all.py").read_text(encoding="utf-8")
        for t in C["tools"]:
            if t["role"] == "check" and t["echo"] in ("unless_no_echo", "dictionary_terms_only"):
                name = Path(t["script"]).name
                line = next((l for l in src.splitlines() if f'"{name}"' in l), "")
                self.assertTrue("no_echo" in line or "lint_opts" in line, f"check_all が {name} に --no-echo を渡していない")

    def test_check_all_runs_every_check(self):
        src = (SCRIPTS / "check_all.py").read_text(encoding="utf-8")
        for t in C["tools"]:
            if t["role"] == "check":
                self.assertIn(f'"{Path(t["script"]).name}"', src, f"check_all.py が {t['script']} を実行していない")

    def test_every_tool_is_documented_in_skill_md(self):
        skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        guide = (SKILL / "GUIDE.md").read_text(encoding="utf-8")
        for t in C["tools"]:
            name = Path(t["script"]).name
            self.assertIn(name, skill, f"SKILL.md に {name} の説明がない")
            if t["role"] in ("check", "aggregate", "transform"):
                self.assertIn(name, guide, f"GUIDE.md に {name} の説明がない")

    def test_skill_md_mentions_only_existing_scripts(self):
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8") + (SKILL / "GUIDE.md").read_text(encoding="utf-8") \
            + (ROOT / "README.md").read_text(encoding="utf-8")
        real = {p.name for p in SCRIPTS.glob("*.py")} | {"watch_sources.py", "package.py"} | {p.name for p in (ROOT / "tests").glob("*.py")}
        for name in set(re.findall(r"\b([a-z_]+\.py)\b", text)):
            self.assertIn(name, real, f"文書に存在しないスクリプト {name} が書かれている")


class Rules(unittest.TestCase):
    def test_term_rules_trace_to_the_registry(self):
        ids = set()
        for t in TERMS["changes"] + TERMS["variants"]:
            self.assertNotIn(t["id"], ids, f"id の重複 {t['id']}")
            ids.add(t["id"])
            for sid in t.get("source_ids", []):
                self.assertIn(sid, REG_BY_ID, f"{t['id']} の出典 {sid} が台帳にない")
        for t in TERMS["changes"]:
            self.assertTrue(t.get("source_ids"), f"{t['id']} に source_ids がない")
            for url in re.findall(r"https?://[^\s】／）]+", t["source"]):
                self.assertIn(url, REG_URLS, f"{t['id']} の出典 URL が台帳に未登録：{url}")
            for sid in t["source_ids"]:
                self.assertIn("assets/term-changes.json", REG_BY_ID[sid]["used_in"],
                              f"{t['id']} の出典 {sid} の used_in に assets/term-changes.json がない")

    def test_error_level_term_rules_have_a_primary_source(self):
        for t in TERMS["changes"]:
            if t["level"] == "error":
                kinds = {REG_BY_ID[s]["kind"] for s in t["source_ids"]}
                self.assertIn("一次", kinds, f"{t['id']}（{t['pattern']}）は error だが一次資料がない")
            if "【二次情報" in t["source"] and t["level"] == "error":
                self.assertTrue(any(REG_BY_ID[s]["kind"] == "一次" for s in t["source_ids"]), t["id"])

    def test_term_rules_match_their_own_examples(self):
        for t in TERMS["changes"]:
            pat = re.compile(t["pattern"])
            ex = t.get("examples", {})
            self.assertTrue(ex.get("hit") and ex.get("ok"), f"{t['id']} に examples（hit と ok）がない")
            for s in ex["hit"]:
                self.assertTrue(pat.search(s), f"{t['id']} が例「{s}」を検出しない")
            for s in ex["ok"]:
                self.assertFalse(pat.search(s), f"{t['id']} が正しい例「{s}」を検出してしまう")

    def test_every_url_in_the_references_is_registered(self):
        files = list((SKILL / "references").glob("*.md")) + [SKILL / "SKILL.md", SKILL / "GUIDE.md"]
        allowed_examples = {"https://doi.org/", "https://example.go.jp/guideline"}
        for f in files:
            if f.name.startswith("source-registry"):
                continue
            for url in re.findall(r"https?://[^\s)）\]>`】、。|]+", f.read_text(encoding="utf-8")):
                url = url.rstrip(".,")
                if url in allowed_examples or url.startswith("https://github.com/kajisho5/japanese-medical-writing.skill"):
                    continue
                self.assertIn(url, REG_URLS, f"{f.name} の URL が出典台帳に未登録：{url}（sources.py add で登録）")

    def test_registry_used_in_paths_exist(self):
        for s in REG["sources"]:
            for u in s.get("used_in", []):
                self.assertTrue((SKILL / u).exists() or (ROOT / u).exists(), f"{s['id']} の used_in が存在しない：{u}")

    def test_secondary_sources_are_marked_in_the_readable_registry(self):
        md = (SKILL / "references" / "source-registry.md").read_text(encoding="utf-8")
        for s in REG["sources"]:
            row = next((l for l in md.splitlines() if l.startswith(f"| {s['id']} |")), "")
            self.assertTrue(row, f"{s['id']} が source-registry.md にない（sources.py render）")
            self.assertEqual(s["kind"] == "二次", "【二次情報】" in row, f"{s['id']} の【二次情報】表示が kind と合わない")


class Stability(unittest.TestCase):
    def test_cli_surface_matches_the_snapshot(self):
        now = {Path(t["script"]).name: {
            "arguments": sorted(a["name"] for a in t["input_schema"]["arguments"]),
            "required": sorted(a["name"] for a in t["input_schema"]["arguments"] if a["required"]),
            "subcommands": {k: sorted(a["name"] for a in v) for k, v in t["input_schema"].get("subcommands", {}).items()},
        } for t in C["tools"]}
        if os.environ.get("UPDATE_CLI_SNAPSHOT") == "1" or not SNAPSHOT.exists():
            SNAPSHOT.write_text(json.dumps(now, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        old = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
        for script, spec in old.items():
            self.assertIn(script, now, f"{script} が削除された（ツールは削除・改名しない）")
            removed = set(spec["arguments"]) - set(now[script]["arguments"])
            self.assertFalse(removed, f"{script} の引数が削除・改名された：{removed}")
            newly_required = set(now[script]["required"]) - set(spec["required"])
            self.assertFalse(newly_required, f"{script} の引数が新たに必須になった：{newly_required}")
            for sub, args in spec["subcommands"].items():
                self.assertIn(sub, now[script]["subcommands"], f"{script} のサブコマンド {sub} が削除された")
                self.assertFalse(set(args) - set(now[script]["subcommands"][sub]), f"{script} {sub} の引数が削除された")
        self.assertEqual(old, now, "引数が追加された。意図した追加なら UPDATE_CLI_SNAPSHOT=1 でスナップショットを更新する")

    def test_versions_agree(self):
        v = C["skill"]["version"]
        cff = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
        self.assertIn(f'version: "{v}"', cff, "CITATION.cff の version が SKILL.md と違う")
        top = re.search(r"^## (\d+\.\d+\.\d+)", (ROOT / "CHANGELOG.md").read_text(encoding="utf-8"), re.M)
        self.assertTrue(top and top.group(1) == v, "CHANGELOG.md の先頭の版が SKILL.md と違う")

    def test_guarantees_point_to_real_tests(self):
        names = {n for cls in (Contract, Rules, Stability) for n in dir(cls) if n.startswith("test_")}
        for g in C["guarantees"]:
            self.assertIn(g["test"], names, f"約束「{g['what']}」を確かめるテスト {g['test']} がない")


if __name__ == "__main__":
    unittest.main()
