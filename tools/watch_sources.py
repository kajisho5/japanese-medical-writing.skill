#!/usr/bin/env python3
"""出典の更新見張り（保守用。ネットワークを使う。スキル本体には含めない）。

出典台帳（japanese-medical-writing/references/source-registry.json）の `watch_url` を取得し、
前回の状態（tools/watch-state.json）と比べて、新しい版・新しい PDF・本文の変化を報告する。
GitHub Actions が毎月実行し、変化があれば Issue を立てる。手元でも実行できる。

使い方:
  python3 tools/watch_sources.py                 # 確認して tools/watch-report.md を作る
  python3 tools/watch_sources.py --only S034     # 1件だけ

判定:
  - 「新しい版・日付・PDF の候補」：版表記（第7.0版、2026年、令和8年…）や PDF へのリンクが前回より増えた
  - 「本文が変わった」：ページの文字が変わった（ナビゲーションの変更なども含むので優先度は低い）
  - 初回はその時点の状態を記録するだけ（比較対象がないため）
患者情報や原稿は扱わない（公開ページの取得のみ）。
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REG = ROOT / "japanese-medical-writing" / "references" / "source-registry.json"
STATE = ROOT / "tools" / "watch-state.json"
REPORT = ROOT / "tools" / "watch-report.md"
UA = "Mozilla/5.0 (compatible; japanese-medical-writing-source-watch; +https://github.com/kajisho5/japanese-medical-writing.skill)"

VERSION_PATTERNS = [
    r"第\s*\d+(?:\.\d+)?\s*版",
    r"(?:令和|平成)\s*(?:\d+|元)\s*年\s*\d+\s*月(?:\s*\d+\s*日)?",
    r"20\d\d\s*年\s*\d{1,2}\s*月(?:\s*\d{1,2}\s*日)?",
    r"(?:January|February|March|April|May|June|July|August|September|October|November|December),?\s+20\d\d",
    r"\b[A-Z][A-Za-z+\-]{2,15}\s+20[2-9]\d\b",          # CONSORT 2025, SCARE 2027 等
    r"[Vv]ersion\s*\d+(?:\.\d+)*|第?\s*\d+\.\d+\s*版|ver\.?\s*\d+(?:\.\d+)*",
]


def fetch(url: str) -> tuple[bytes, str]:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "ja,en;q=0.8"})
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read(), r.headers.get("Content-Type", "")


def page_text(raw: bytes, ctype: str) -> str:
    enc = "utf-8"
    m = re.search(r"charset=([\w-]+)", ctype) or re.search(rb'charset=["\']?([\w-]+)', raw[:3000])
    if m:
        enc = m.group(1).decode() if isinstance(m.group(1), bytes) else m.group(1)
    try:
        t = raw.decode(enc, errors="replace")
    except LookupError:
        t = raw.decode("utf-8", errors="replace")
    t = re.sub(r"(?is)<(script|style|noscript|svg).*?</\1>", " ", t)
    return t


def markers(htmltext: str) -> list[str]:
    links = set(re.findall(r'href=["\']([^"\']+\.pdf)["\']', htmltext, re.I))
    text = html.unescape(re.sub(r"(?s)<[^>]+>", " ", htmltext))
    text = re.sub(r"\s+", " ", text)
    found = set()
    for p in VERSION_PATTERNS:
        found.update(m.group(0).strip() for m in re.finditer(p, text))
    return sorted(found | {"PDF:" + l.split("/")[-1] for l in links})


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    reg = json.loads(REG.read_text(encoding="utf-8"))
    state = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
    today = dt.date.today().isoformat()

    targets: dict[str, list[dict]] = {}
    for s in reg["sources"]:
        if s.get("watch_url") and (not a.only or s["id"] == a.only):
            targets.setdefault(s["watch_url"], []).append(s)

    new_ver, changed, failed, first = [], [], [], []
    for url, srcs in targets.items():
        label = " / ".join(f"{s['id']} {s['title']}" for s in srcs)
        hint = "；".join(s["watch_hint"] for s in srcs if s.get("watch_hint"))
        try:
            raw, ctype = fetch(url)
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            failed.append((label, url, str(e)))
            prev = state.get(url, {})
            prev["last_error"] = f"{today}: {e}"
            state[url] = prev
            continue
        if "pdf" in ctype.lower() or url.lower().endswith(".pdf"):
            digest, mk = hashlib.sha256(raw).hexdigest(), []
        else:
            t = page_text(raw, ctype)
            body = re.sub(r"\s+", " ", html.unescape(re.sub(r"(?s)<[^>]+>", " ", t)))
            digest, mk = hashlib.sha256(body.encode("utf-8")).hexdigest(), markers(t)
        prev = state.get(url)
        if not prev or not prev.get("sha256"):
            first.append((label, url))
        else:
            added = sorted(set(mk) - set(prev.get("markers", [])))
            if added:
                new_ver.append((label, url, hint, added[:15]))
            elif digest != prev["sha256"]:
                changed.append((label, url, hint))
        state[url] = {"sha256": digest, "markers": mk, "checked": today, "last_error": ""}

    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")

    lines = [f"# 出典の更新見張り結果（{today}）", ""]
    if new_ver:
        lines += ["## 新しい版・日付・PDF の候補（要確認：優先）", ""]
        for label, url, hint, added in new_ver:
            lines += [f"- **{label}**", f"  - 見張り先：{url}", f"  - 見る点：{hint or '—'}", f"  - 新しく現れた表記：{'、'.join(added)}"]
        lines.append("")
    if changed:
        lines += ["## 本文が変わった（優先度低。ナビゲーション等の変更の場合もある）", ""]
        lines += [f"- {label}（{url}）見る点：{hint or '—'}" for label, url, hint in changed] + [""]
    if failed:
        lines += ["## 取得できなかった（URL の移転・一時的な障害の可能性）", ""]
        lines += [f"- {label}（{url}）：{err}" for label, url, err in failed] + [""]
    if first:
        lines += ["## 初回記録（次回から比較）", ""] + [f"- {label}（{url}）" for label, url in first] + [""]
    lines += [
        "## 対応のしかた",
        "",
        "1. 見張り先を開き、本当に新しい版・改正か確認する（一次資料で）。",
        "2. 新版なら `python3 japanese-medical-writing/scripts/sources.py find <名前>` で使っているファイルを探し、記載を直す。",
        "3. `sources.py check-version <ID> --version <新しい版>` で台帳を更新し、テストを通してから取り込む。",
        "4. 詳しくは MAINTENANCE.md。",
    ]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    flag = "true" if (new_ver or changed or failed) else "false"
    print(REPORT.read_text(encoding="utf-8"))
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as fh:
            fh.write(f"changed={flag}\n")


if __name__ == "__main__":
    main()
