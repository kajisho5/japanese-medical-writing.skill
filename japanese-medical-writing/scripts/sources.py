#!/usr/bin/env python3
"""出典台帳（references/source-registry.json）の検索・追加・一覧表示（Python 標準ライブラリのみ・通信なし）。

このスキルの参照資料が根拠にしている法令・指針・ガイドライン・投稿規定・ツール文書の
URL・版・確認日・更新の見張り先を一か所で管理する。ガイドラインの改訂時に、どのファイルの
どの記載を直せばよいかをすぐ探せるようにするためのもの。

使い方:
  python3 sources.py find CONSORT              キーワードで検索（題名・発行元・メモ・カテゴリ）
  python3 sources.py list --category 国内       カテゴリで絞り込み（部分一致）
  python3 sources.py list --kind 二次           二次情報だけ
  python3 sources.py stale --months 6           確認日が古いものを一覧
  python3 sources.py used references/ethics-coi.md   そのファイルが根拠にしている出典
  python3 sources.py add --category "国際・報告GL" --title "XXX 2027" --url https://... \\
      --publisher "..." --version "2027" --kind 一次 --status 確認済 --used references/guidelines.md \\
      --watch https://... --hint "改訂の告知"
  python3 sources.py check-version S006 --version "2027" --date 2027-01-10   版・確認日の更新
  python3 sources.py render                     人が読む一覧（references/source-registry.md）を作り直す
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _textio  # noqa: E402,F401  標準出力の文字コード設定のため

REG = Path(__file__).resolve().parent.parent / "references" / "source-registry.json"
MD = REG.with_suffix(".md")


def load() -> dict:
    return json.loads(REG.read_text(encoding="utf-8"))


def save(data: dict) -> None:
    data["updated"] = dt.date.today().isoformat()
    tmp = REG.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    tmp.replace(REG)


def show(s: dict) -> None:
    mark = "【二次情報】" if s.get("kind") == "二次" else ""
    print(f"{s['id']} [{s['category']}] {mark}{s['title']}")
    for key, label in (("publisher", "発行元"), ("version", "版"), ("url", "URL"), ("status", "確認状況"),
                       ("checked_on", "確認日"), ("watch_url", "更新の見張り先"), ("watch_hint", "見る点"), ("notes", "メモ")):
        if s.get(key):
            print(f"    {label}：{s[key]}")
    if s.get("used_in"):
        print(f"    使っているファイル：{', '.join(s['used_in'])}")


def render(data: dict) -> None:
    lines = [
        "# 出典台帳",
        "",
        f"最終更新：{data['updated']}　件数：{len(data['sources'])}",
        "",
        "このスキルが根拠にしている資料の一覧。機械で読める元データは `source-registry.json`。"
        "検索・追加は `python3 scripts/sources.py`（使い方は同スクリプトの説明）。"
        "`【二次情報】` は一次資料で確認できていないもの。毎月の自動見張り（リポジトリの GitHub Actions）が `更新の見張り先` を確認する。",
        "",
    ]
    cats: dict[str, list[dict]] = {}
    for s in data["sources"]:
        cats.setdefault(s["category"], []).append(s)
    for cat, items in cats.items():
        lines += [f"## {cat}", "", "| ID | 資料 | 発行元・版 | 確認 | 使っているファイル |", "|---|---|---|---|---|"]
        for s in items:
            title = s["title"] if not s["url"] else f"[{s['title']}]({s['url']})"
            if s.get("kind") == "二次":
                title = "【二次情報】" + title
            pv = " / ".join(x for x in (s.get("publisher", ""), s.get("version", "")) if x)
            lines.append(f"| {s['id']} | {title} | {pv} | {s['status']}（{s['checked_on']}） | {', '.join(s.get('used_in', []))} |")
        lines.append("")
    MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"作成：{MD}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("find"); f.add_argument("keyword")
    li = sub.add_parser("list"); li.add_argument("--category", default=""); li.add_argument("--kind", default=""); li.add_argument("--status", default="")
    st = sub.add_parser("stale"); st.add_argument("--months", type=int, default=6)
    us = sub.add_parser("used"); us.add_argument("file")
    ad = sub.add_parser("add")
    for k in ("category", "title", "url"):
        ad.add_argument(f"--{k}", required=k != "url", default="")
    for k in ("publisher", "version", "notes", "watch", "hint"):
        ad.add_argument(f"--{k}", default="")
    ad.add_argument("--kind", choices=["一次", "二次", "ツール文書"], default="一次")
    ad.add_argument("--status", choices=["確認済", "一部確認", "未確認"], default="確認済")
    ad.add_argument("--used", nargs="*", default=[])
    cv = sub.add_parser("check-version"); cv.add_argument("id"); cv.add_argument("--version", default=""); cv.add_argument("--date", default=""); cv.add_argument("--notes", default="")
    sub.add_parser("render")
    a = ap.parse_args()
    data = load()
    S = data["sources"]

    if a.cmd == "find":
        k = a.keyword.lower()
        hits = [s for s in S if any(k in str(s.get(x, "")).lower() for x in ("title", "publisher", "notes", "category", "url", "version"))]
        for s in hits:
            show(s)
        print(f"\n{len(hits)} 件")
    elif a.cmd == "list":
        hits = [s for s in S if a.category in s["category"] and (not a.kind or s.get("kind") == a.kind) and (not a.status or s["status"] == a.status)]
        for s in hits:
            show(s)
        print(f"\n{len(hits)} 件")
    elif a.cmd == "stale":
        limit = dt.date.today() - dt.timedelta(days=30 * a.months)
        hits = [s for s in S if dt.date.fromisoformat(s["checked_on"]) < limit]
        for s in hits:
            show(s)
        print(f"\n確認日が {a.months} か月より前：{len(hits)} 件")
    elif a.cmd == "used":
        hits = [s for s in S if any(a.file in u or u in a.file for u in s.get("used_in", []))]
        for s in hits:
            show(s)
        print(f"\n{len(hits)} 件")
    elif a.cmd == "add":
        if a.url and any(s["url"] == a.url for s in S):
            sys.exit(f"同じ URL が既に登録されています：{a.url}（check-version で更新してください）")
        new_id = f"S{max(int(s['id'][1:]) for s in S) + 1:03d}" if S else "S001"
        S.append({"id": new_id, "category": a.category, "title": a.title, "publisher": a.publisher, "version": a.version,
                  "url": a.url, "kind": a.kind, "status": a.status, "checked_on": dt.date.today().isoformat(),
                  "used_in": a.used, "watch_url": a.watch, "watch_hint": a.hint, "sha256": "", "notes": a.notes})
        save(data)
        render(data)
        print(f"追加：{new_id} {a.title}")
    elif a.cmd == "check-version":
        for s in S:
            if s["id"] == a.id:
                if a.version:
                    s["version"] = a.version
                if a.notes:
                    s["notes"] = (s.get("notes", "") + " / " + a.notes).strip(" /")
                s["checked_on"] = a.date or dt.date.today().isoformat()
                save(data)
                render(data)
                show(s)
                break
        else:
            sys.exit(f"ID が見つかりません：{a.id}")
    elif a.cmd == "render":
        render(data)


if __name__ == "__main__":
    main()
