# 出典の更新見張り結果（2026-11-01）

## 新しい版・日付・PDF の候補（要確認：優先）

- **S039 生成AIサービスの利用に関する注意喚起等について**
  - 見張り先：https://www.ppc.go.jp/news/press/
  - 見る点：生成AIに関する新しい注意喚起
  - 新しく現れた表記：令和8年10月21日、令和8年10月28日、令和８年10月28日

## 本文が変わった（優先度低。ナビゲーション等の変更の場合もある）

- S005 EQUATOR Network（報告ガイドライン一覧）（https://www.equator-network.org/）見る点：新着ガイドライン・改訂
- S013 CARE（公式）（https://www.equator-network.org/reporting-guidelines/care/）見る点：本体の改訂、分野別拡張（CARE-radiology 等）
- S064 日本消化器外科学会雑誌 投稿規程（https://www.jsgs.or.jp/journalindex/jjgs/ifa/）見る点：改正
- S071 Ollama（Windows）（https://docs.ollama.com/windows）見る点：要件・手順の変更
- S072 Ollama（macOS）（https://docs.ollama.com/macos）見る点：要件・手順の変更
- S073 Ollama コンテキスト長（https://docs.ollama.com/context-length）見る点：既定値の変更
- S074 Ollama × OpenCode（https://docs.ollama.com/integrations/opencode）見る点：ollama launch の手順変更
- S077 OpenCode Skills（https://opencode.ai/docs/skills）見る点：スキルの置き場所・frontmatter 要件
- S078 Codex Agent Skills（https://learn.chatgpt.com/docs/build-skills）見る点：スキルの置き場所

## 初回記録（次回から比較）

- S009 PRISMA（公式・翻訳・開発中の拡張）（https://www.prisma-statement.org/）
- S091 疾病、傷害及び死因の統計分類（ICD-11準拠）（https://www.mhlw.go.jp/stf/toukei/goriyou/sippei.html）
- S109 Claude Code GitHub Actions（https://code.claude.com/docs/en/github-actions）

## 対応のしかた

1. 見張り先を開き、本当に新しい版・改正か確認する（一次資料で）。
2. 新版なら `python3 japanese-medical-writing/scripts/sources.py find <名前>` で使っているファイルを探し、記載を直す。
3. `sources.py check-version <ID> --version <新しい版>` で台帳を更新し、テストを通してから取り込む。
4. 詳しくは MAINTENANCE.md。
