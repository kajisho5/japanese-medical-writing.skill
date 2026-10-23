# 仕様（SPEC）と、それを守らせる仕組み

このスキルの「何をするか・何を約束するか」を機械可読な仕様として持ち、コード・文書・データ・出典台帳がその仕様からずれたら自動テスト（CI）が落ちるようにしている。考え方は [ffmpeg-skill の実行契約](https://github.com/kajisho5/ffmpeg-skill/blob/main/docs/contract.md) と同じで、医学論文向けに「規則が出典までたどれること」を加えている。

```bash
python3 japanese-medical-writing/scripts/_contract.py          # 要約
python3 japanese-medical-writing/scripts/_contract.py --json   # 機械可読の仕様
python3 -m unittest tests.test_contract -v                     # 仕様のテスト
```

## 仕様はコードから作る

| 部分 | 作り方 |
|---|---|
| ツールの一覧 | `scripts/` のうち `_` で始まらない `.py` すべて |
| 各ツールの引数 | そのスクリプトの argparse から実行時に取り出す（文書に書き写さない） |
| 役割・原稿の文面を出力するか・書き込むもの・依頼の言い方・限界 | `scripts/_contract.py` の `TOOL_META`（一か所だけ） |
| 用語の規則 | `assets/term-changes.json`（各規則に id・出典台帳の ID・自己テスト用の例） |
| 前後矛盾・個人情報の規則 | `check_consistency.py`・`check_privacy.py` の定義そのもの |

## 約束と、それを確かめるテスト

| 約束 | テスト（`tests/test_contract.py`） |
|---|---|
| スキル内のスクリプトは通信しない（通信用モジュールを import しない） | `test_scripts_never_import_network_modules` |
| Python 標準ライブラリだけで動く | `test_scripts_use_only_the_standard_library` |
| 原稿の文面を出力するツールはすべて `--no-echo` を持ち、`check_all.py` がそれを渡す | `test_tools_that_echo_text_accept_no_echo` |
| `check_all.py` は点検ツールをすべて実行する | `test_check_all_runs_every_check` |
| すべてのツールが SKILL.md（と GUIDE.md）に書かれ、文書に存在しないスクリプト名がない | `test_every_tool_is_documented_in_skill_md`・`test_skill_md_mentions_only_existing_scripts` |
| 用語の規則はすべて出典台帳の ID を持ち、規則に書いた URL も台帳に登録済み | `test_term_rules_trace_to_the_registry` |
| 「必ず直す」（error）用語規則には一次資料が1つ以上ある | `test_error_level_term_rules_have_a_primary_source` |
| 用語の規則は自分の例どおりに検出する／しない | `test_term_rules_match_their_own_examples` |
| 参照資料・SKILL.md・GUIDE.md に書いた URL はすべて出典台帳に登録済み | `test_every_url_in_the_references_is_registered` |
| 二次情報の出典は、人が読む台帳で `【二次情報】` と表示される | `test_secondary_sources_are_marked_in_the_readable_registry` |
| 出典台帳の `used_in` のファイルは実在する | `test_registry_used_in_paths_exist` |
| CLI の引数は削除・改名しない（追加は可） | `test_cli_surface_matches_the_snapshot` |
| SKILL.md・CITATION.cff・CHANGELOG.md の版が一致する | `test_versions_agree` |
| クラウド（または不明）で動くときは、会話ごとに最初に注意を出す（SKILL.md の指示と GUIDE.md の説明） | `test_cloud_notice_is_required_every_conversation` |
| 最終確認を人の目で1人だけで済ませないこと（ダブルチェック）を、SKILL.md・GUIDE.md・README・セルフ査読・`check_all.py` の出力が必ず伝える | `test_double_check_by_humans_is_always_stated` |

## 何が正しくなり、何は正しくならないか

- **正しくなるもの（スキル自体の正しさ）**：根拠のない規則・登録漏れの出典・文書と実装のずれ・通信やプライバシーの約束違反が、人が気づく前に CI で止まる。v0.14.0 の導入時には、実際に次が見つかった：用語規則の出典 URL 6 件が台帳に未登録、「チャーグ・ストラウス症候群」の旧称の根拠が別の資料（多発血管炎性肉芽腫症）を指していた（正しい資料に差し替え）、「精神分裂病」（必ず直す扱い）の根拠が二次情報だけだった（一次資料を追加）。
- **正しくならないもの（原稿の医学的な正しさ）**：仕様は「規則とツールがどう動くか」を保証するだけで、原稿の診断・数値・解釈が正しいことは保証しない。それは台帳（claims ledger）・一次資料での確認・著者の判断で担保する。

## 変えるときの手順

- **ツールを追加**：`scripts/新しい名前.py`（argparse を使う）を作り、`_contract.py` の `TOOL_META` に1項目足し、SKILL.md・GUIDE.md に書く。点検ツールなら `check_all.py` にも足す。足し忘れはテストが落とす。
- **引数を追加**：実装してから `UPDATE_CLI_SNAPSHOT=1 python3 -m unittest tests.test_contract` でスナップショットを更新する（差分がレビューで見える）。
- **引数を削除・改名**：しない。どうしても必要なら、旧名を残したまま新名を足し、次の大きな版で外す（CHANGELOG に書く）。
- **用語の規則を追加**：先に `sources.py add` で出典を台帳に登録し、`term-changes.json` に id・source_ids・examples（検出される文／されない文）を付けて足す。一次資料がなければ level は `warn`。
- **版を上げる**：SKILL.md・CITATION.cff・CHANGELOG.md の3か所。push するとリリースが自動で作られる。
