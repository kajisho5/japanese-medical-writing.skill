#!/usr/bin/env python3
"""全チェックの一括実行（Python 標準ライブラリのみ・通信なし）。

lint_ja.py / check_refs.py / check_numbers.py / check_privacy.py / check_terms.py / check_consistency.py を順に実行し、
結果をまとめて表示する。AI を使わずに人が原稿を点検するときもこれ1本でよい。

使い方:
  python3 check_all.py manuscript.md
  python3 check_all.py --draft manuscript.md        # 下書き段階（未解決マーカー・仮置きは件数のみ）
  python3 check_all.py --no-echo manuscript.md      # 原稿の文面を出力しない
  python3 check_all.py --allow-desu reply.md        # です・ます調を許可（査読回答など）

どれか1つでも問題があれば終了コード 1。
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import _textio  # noqa: E402,F401  標準出力の文字コード設定のため


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file")
    ap.add_argument("--draft", action="store_true")
    ap.add_argument("--no-echo", action="store_true")
    ap.add_argument("--allow-desu", action="store_true")
    a = ap.parse_args()

    lint_opts = [o for o, on in (("--draft", a.draft), ("--no-echo", a.no_echo), ("--allow-desu", a.allow_desu)) if on]
    jobs = [
        ("表記・文体", "lint_ja.py", lint_opts),
        ("文献・図表番号", "check_refs.py", []),
        ("数値の整合", "check_numbers.py", []),
        ("個人情報の候補", "check_privacy.py", ["--no-echo"] if a.no_echo else []),
        ("医学用語", "check_terms.py", ["--no-echo"] if a.no_echo else []),
        ("前後の食い違い", "check_consistency.py", ["--no-echo"] if a.no_echo else []),
    ]
    summary = []
    for label, script, opts in jobs:
        print(f"\n===== {label}（{script}） =====", flush=True)
        r = subprocess.run([sys.executable, "-I", str(HERE / script), *opts, a.file])
        summary.append((label, r.returncode))
    print("\n===== まとめ =====")
    for label, code in summary:
        print(f"  {'OK  ' if code == 0 else '要対応'}  {label}")
    print("※ 機械チェックは一部しか見ない。台帳との照合・セルフ査読・図表と画像の目視確認は別に行う。")
    sys.exit(1 if any(code for _, code in summary) else 0)


if __name__ == "__main__":
    main()
