# 出典の更新見張り結果（2026-10-17）

## 取得できなかった（URL の移転・一時的な障害の可能性）

- S009 PRISMA（公式・翻訳・開発中の拡張）（https://prisma-statement.org/in-development）：HTTP Error 404: Not Found

## 初回記録（次回から比較）

- S001 ICMJE Recommendations（最新版の告知） / S003 ICMJE Recommendations 日本語訳（2026年1月版）（https://www.icmje.org/）
- S005 EQUATOR Network（報告ガイドライン一覧）（https://www.equator-network.org/）
- S007 CONSORT/SPIRIT 翻訳一覧（https://www.consort-spirit.org/translations）
- S011 STROBE（公式）（https://www.strobe-statement.org/）
- S013 CARE（公式）（https://www.equator-network.org/reporting-guidelines/care/）
- S030 人を対象とする生命科学・医学系研究に関する倫理指針（令和8年一部改正の公表） / S031 倫理指針 ガイダンス（令和6年4月1日改訂版）（https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/hokabunya/kenkyujigyou/i-kenkyu/index.html）
- S035 臨床研究法（厚生労働省ページ）（https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/0000163417.html）
- S039 生成AIサービスの利用に関する注意喚起等について（https://www.ppc.go.jp/news/press/）
- S046 次世代医療基盤法（内閣府 健康・医療戦略推進事務局）（https://www8.cao.go.jp/iryou/）
- S049 AI事業者ガイドライン（https://www.soumu.go.jp/main_sosiki/kenkyu/ai_network/02ryutsu20_04000019.html）
- S053 研究活動における不正行為への対応等に関するガイドライン（https://www.mext.go.jp/a_menu/jinzai/fusei/1352820.htm）
- S056 医学雑誌編集ガイドライン 2022 / S057 日本医学会 COI 管理ガイドライン（https://jams.med.or.jp/guideline/）
- S062 日本小児科学会雑誌 投稿規程（https://www.jpeds.or.jp/uploads/files/contribution2025_4.pdf）
- S064 日本消化器外科学会雑誌 投稿規程（https://www.jsgs.or.jp/journalindex/jjgs/ifa/）
- S071 Ollama（Windows）（https://docs.ollama.com/windows）
- S072 Ollama（macOS）（https://docs.ollama.com/macos）
- S073 Ollama コンテキスト長（https://docs.ollama.com/context-length）
- S074 Ollama × OpenCode（https://docs.ollama.com/integrations/opencode）
- S077 OpenCode Skills（https://opencode.ai/docs/skills）
- S078 Codex Agent Skills（https://learn.chatgpt.com/docs/build-skills）

## 対応のしかた

1. 見張り先を開き、本当に新しい版・改正か確認する（一次資料で）。
2. 新版なら `python3 japanese-medical-writing/scripts/sources.py find <名前>` で使っているファイルを探し、記載を直す。
3. `sources.py check-version <ID> --version <新しい版>` で台帳を更新し、テストを通してから取り込む。
4. 詳しくは MAINTENANCE.md。
