#!/usr/bin/env python3
"""このスキルの機械可読な仕様（SPEC）を出力する（内部モジュール。Python 標準ライブラリのみ・通信なし）。

  python3 scripts/_contract.py --json      仕様を JSON で出力
  python3 scripts/_contract.py             人が読む要約

仕様はコードから作る（別に書いて保守しない）。
  - ツールの一覧は scripts/ のうち "_" で始まらない .py すべて
  - 各ツールの引数（input_schema）は、そのスクリプト自身の argparse から実行時に取り出す
  - 引数から読めない事実（役割・原稿の文面を出力するか・書き込むもの・自然言語の依頼例・
    人が確認すべき限界）は下の TOOL_META に一か所で書く
  - 判定規則（用語の改称、前後矛盾の対象、個人情報の検出項目）は、それぞれのデータ・スクリプトから読む

tests/test_contract.py が、この仕様と SKILL.md・README・check_all・出典台帳・CLI のスナップショットが
食い違っていないかを毎回確認する。食い違えば CI が落ちる。説明はリポジトリ直下の SPEC.md。

仕様の版（CONTRACT_VERSION）は、この文書の形が変わったときだけ上げる。スキルの版は SKILL.md から読む。
"""
from __future__ import annotations

import argparse
import contextlib
import importlib.util
import io
import json
import re
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
SKILL_DIR = HERE.parent
sys.path.insert(0, str(HERE))
import _textio  # noqa: E402,F401  標準出力の文字コード設定のため

CONTRACT_VERSION = "1.0"

ROLES = {
    "check": "原稿を読んで問題の候補を報告する。原稿は変えない。check_all.py が必ず実行する",
    "aggregate": "複数の check をまとめて実行する",
    "transform": "原稿の表記を機械的に変えた別ファイルを作る。元ファイルは変えない",
    "maintenance": "スキル自体の保守（出典台帳）。原稿は扱わない",
}
ECHO = {
    "unless_no_echo": "該当箇所の原稿の文面を出力する。--no-echo で出力しない",
    "numbers_only": "行番号と数値だけを出力する（原稿の文は出さない）",
    "dictionary_terms_only": "行番号・数値と辞書にある医学用語を出力する。原稿から取った語（検査名・薬剤名）は --no-echo で伏せる",
    "writes_file": "結果を別ファイルに書く（画面には件数のみ）",
    "none": "原稿を読まない",
}

# argparse から読めない事実。キーは scripts/ のファイル名（.py なし）。
TOOL_META: dict[str, dict[str, Any]] = {
    "lint_ja": dict(
        role="check", echo="unless_no_echo", writes=[],
        purpose="表記・文体・未解決マーカー（【要確認】【要文献】【二次情報】）・過大表現・略語の定義",
        intents=["点検して", "文体を見て", "マーカー残ってない？"],
        limits=["内容の正しさは判定しない", "WARN は文脈で判断する"]),
    "check_refs": dict(
        role="check", echo="numbers_only", writes=[],
        purpose="引用番号と文献リスト、図表番号と参照の対応・順序・欠番",
        intents=["文献番号ずれてない？", "図表番号確かめて"],
        limits=["文献の中身（著者・年・巻号）が正しいかは確認しない"]),
    "check_numbers": dict(
        role="check", echo="numbers_only", writes=[],
        purpose="抄録の数値が本文・表にあるか、割合の再計算",
        intents=["数字合ってる？", "抄録と本文ずれてない？", "割合の計算確かめて"],
        limits=["同じ数が別の意味で出ていても一致とみなす。最後は台帳で確認する"]),
    "check_privacy": dict(
        role="check", echo="unless_no_echo", writes=[],
        purpose="年月日・ID・住所・氏名など個人情報の候補（docx のヘッダ・脚注・コメント・作成者も）",
        intents=["個人情報残ってない？", "匿名化できてる？"],
        limits=["候補にすぎず見逃しもある", "図表・画像・表のセルは人が確認する"]),
    "check_terms": dict(
        role="check", echo="unless_no_echo", writes=[],
        purpose="改称された旧用語・診断基準の版による病名の違い・表記ゆれ（出典つき）",
        intents=["用語合ってる？", "病名が古くないか見て"],
        limits=["辞書（assets/term-changes.json）にない用語は判定できない"]),
    "check_consistency": dict(
        role="check", echo="dictionary_terms_only", writes=[],
        purpose="前後の記載の食い違いの候補（左右・運動方向・検査の陽性/陰性・組織型と分化度・病変側と麻痺側・数値と上昇/低下・単位の混在・薬剤の単位と用量と経路・病日の順序）",
        intents=["前後で矛盾してないか見て", "左右や内旋・外旋が途中で変わってない？", "病理の記載が一貫してるか確かめて",
                 "麻痺の左右と病変の側は合ってる？", "検査値の上がった下がったと数字は合ってる？", "薬の量や単位がずれてないか見て"],
        limits=["候補であり、治療前後の変化や両側の比較など正しい記載も拾う",
                "時系列・用量・診断の流れの矛盾は AI と人が全文を読んで確認する（一貫性表）"]),
    "check_all": dict(
        role="aggregate", echo="unless_no_echo", writes=[],
        purpose="role が check のツールをすべて実行してまとめる",
        intents=["点検して", "チェックして", "投稿前に見て"],
        limits=["機械チェックは一部しか見ない。台帳との照合・セルフ査読・図表と画像の目視は別"]),
    "format_ja": dict(
        role="transform", echo="writes_file", writes=["<原稿名>.formatted.md（元ファイルは変えない）"],
        purpose="句読点・全角英数字・単位の空白・範囲記号の機械的な統一",
        intents=["句読点を，．にして", "全角数字を直して", "範囲を〜に揃えて"],
        limits=["内容（数値・言葉）は変えない"]),
    "sources": dict(
        role="maintenance", echo="none", writes=["references/source-registry.json", "references/source-registry.md"],
        purpose="出典台帳の検索・追加・版と確認日の更新",
        intents=["この指針はどこで使ってる？", "出典を登録して"],
        limits=["改訂の有無は判定しない（毎月の見張りは tools/watch_sources.py）"]),
}

# 守ることを約束している性質と、それを確認するテスト（tests/test_contract.py のメソッド名）
GUARANTEES = [
    {"what": "スキル内のスクリプトは通信しない（ネットワーク用モジュールを import しない）", "test": "test_scripts_never_import_network_modules"},
    {"what": "Python 標準ライブラリだけで動く", "test": "test_scripts_use_only_the_standard_library"},
    {"what": "原稿の文面を出力するツールはすべて --no-echo を持ち、check_all がそれを渡す", "test": "test_tools_that_echo_text_accept_no_echo"},
    {"what": "check_all は role が check のツールをすべて実行する", "test": "test_check_all_runs_every_check"},
    {"what": "すべてのツールが SKILL.md に書かれている", "test": "test_every_tool_is_documented_in_skill_md"},
    {"what": "用語の規則はすべて出典台帳の ID を持ち、本文中の URL も台帳に登録済み", "test": "test_term_rules_trace_to_the_registry"},
    {"what": "必ず直す（error）用語規則には一次資料が1つ以上ある", "test": "test_error_level_term_rules_have_a_primary_source"},
    {"what": "用語の規則は自分の例（examples）どおりに検出する／しない", "test": "test_term_rules_match_their_own_examples"},
    {"what": "参照資料・SKILL.md に書いた URL はすべて出典台帳に登録済み", "test": "test_every_url_in_the_references_is_registered"},
    {"what": "出典台帳の used_in のファイルは実在する", "test": "test_registry_used_in_paths_exist"},
    {"what": "CLI の引数は削除・改名しない（追加のみ）", "test": "test_cli_surface_matches_the_snapshot"},
    {"what": "SKILL.md・CITATION.cff・CHANGELOG の版が一致する", "test": "test_versions_agree"},
    {"what": "クラウド（または不明）で動くときは、会話ごとに最初に注意を出すことを SKILL.md が指示し、GUIDE.md が説明する",
     "test": "test_cloud_notice_is_required_every_conversation"},
    {"what": "最終確認を人の目で1人だけで済ませないこと（ダブルチェック）を、SKILL.md・GUIDE.md・README・セルフ査読・check_all の出力が必ず伝える",
     "test": "test_double_check_by_humans_is_always_stated"},
]


class _Captured(Exception):
    def __init__(self, parser: argparse.ArgumentParser):
        self.parser = parser


def tool_names() -> list[str]:
    return sorted(p.stem for p in HERE.glob("*.py") if not p.name.startswith("_"))


def parser_of(name: str) -> argparse.ArgumentParser:
    """スクリプトの main() を、parse_args の直前で止めて parser を取り出す（原稿は読まない）。"""
    spec = importlib.util.spec_from_file_location(f"_spec_{name}", HERE / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    original = argparse.ArgumentParser.parse_args

    def capture(self, *a, **k):  # noqa: ANN001
        raise _Captured(self)

    argparse.ArgumentParser.parse_args = capture  # type: ignore[assignment]
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            mod.main()
    except _Captured as c:
        return c.parser
    finally:
        argparse.ArgumentParser.parse_args = original  # type: ignore[assignment]
    raise RuntimeError(f"{name}.py の main() が argparse を使っていない")


def input_schema(parser: argparse.ArgumentParser) -> dict[str, Any]:
    args, subcommands = [], {}
    for act in parser._actions:  # noqa: SLF001  argparse に公開 API がない
        if isinstance(act, argparse._HelpAction):  # noqa: SLF001
            continue
        if isinstance(act, argparse._SubParsersAction):  # noqa: SLF001
            for sub, sp in act.choices.items():
                subcommands[sub] = input_schema(sp)["arguments"]
            continue
        kind = "flag" if act.nargs == 0 else "value"
        args.append({
            "name": act.option_strings[-1] if act.option_strings else act.dest,
            "positional": not act.option_strings,
            "kind": kind,
            "required": bool(act.required) if act.option_strings else act.nargs not in ("?", "*"),
            "choices": list(act.choices) if act.choices else None,
            "help": act.help or "",
        })
    out: dict[str, Any] = {"arguments": args}
    if subcommands:
        out["subcommands"] = subcommands
    return out


def skill_version() -> str:
    m = re.search(r'^\s*version:\s*"([^"]+)"', (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8"), re.M)
    return m.group(1) if m else ""


def rules() -> dict[str, Any]:
    terms = json.loads((SKILL_DIR / "assets" / "term-changes.json").read_text(encoding="utf-8"))
    cons_spec = importlib.util.spec_from_file_location("_spec_cons", HERE / "check_consistency.py")
    cons = importlib.util.module_from_spec(cons_spec)
    cons_spec.loader.exec_module(cons)  # type: ignore[union-attr]
    priv_spec = importlib.util.spec_from_file_location("_spec_priv", HERE / "check_privacy.py")
    priv = importlib.util.module_from_spec(priv_spec)
    priv_spec.loader.exec_module(priv)  # type: ignore[union-attr]
    return {
        "terms": [{k: t.get(k) for k in ("id", "pattern", "recommended", "level", "source_ids")} for t in terms["changes"]],
        "term_variants": [{k: v.get(k) for k in ("id", "forms")} for v in terms["variants"]],
        "consistency": {
            "body_parts": len(cons.PARTS),
            "opposite_directions": [list(p) for p in cons.DIRECTIONS],
            "histology": cons.HISTO,
            "cerebral_lesion_sites": cons.CEREBRAL,
            "lesion_side_source_ids": ["S120"],
            "lab_items": len(cons.LABS),
            "timeline_counters": [k for k, _ in cons.COUNTERS],
        },
        "privacy": [c[0] for c in priv.CHECKS],
    }


def contract() -> dict[str, Any]:
    tools = []
    for name in tool_names():
        meta = TOOL_META.get(name, {})
        tools.append({
            "id": f"japanese-medical-writing/{name}",
            "script": f"scripts/{name}.py",
            **meta,
            "network": False,
            "input_schema": input_schema(parser_of(name)),
            "exit_codes": {"0": "問題なし（または処理完了）", "1": "対応が必要な候補がある・処理できなかった", "2": "引数の誤り"},
        })
    return {
        "contract_version": CONTRACT_VERSION,
        "skill": {"name": "japanese-medical-writing", "version": skill_version(),
                  "runtime": "Python 3.9+ 標準ライブラリのみ", "network": False},
        "roles": ROLES,
        "echo_policies": ECHO,
        "guarantees": GUARANTEES,
        "tools": tools,
        "rules": rules(),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    c = contract()
    if a.json:
        print(json.dumps(c, ensure_ascii=False, indent=1))
        return
    print(f"japanese-medical-writing {c['skill']['version']}（仕様 {c['contract_version']}）")
    for t in c["tools"]:
        print(f"- {t['script']}  [{t.get('role', '?')}] {t.get('purpose', '')}")
    r = c["rules"]
    print(f"規則：用語 {len(r['terms'])}・表記ゆれ {len(r['term_variants'])}・個人情報 {len(r['privacy'])} 項目・"
          f"前後矛盾（部位 {r['consistency']['body_parts']}・方向 {len(r['consistency']['opposite_directions'])} 組・組織型など {len(r['consistency']['histology'])}）")
    print(f"約束 {len(c['guarantees'])} 件（tests/test_contract.py が確認）")


if __name__ == "__main__":
    main()
