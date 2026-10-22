# 保守と引き継ぎ

このスキルを、作者がいなくなっても使われ続け、更新され続けるようにするための手順書です。後を引き継ぐ人は、この文書だけ読めば作業できるように書いています。

## 1. 自動で動いているもの

| 仕組み | 内容 | ファイル |
|---|---|---|
| 毎月の出典見張り | 出典台帳の「更新の見張り先」を毎月1日に確認し、新しい版・PDF・本文の変化があれば Issue（ラベル `source-update`）を立てる。結果は `tools/watch-report.md`、状態は `tools/watch-state.json` に記録 | `.github/workflows/watch-sources.yml`、`tools/watch_sources.py` |
| 修正案の自動作成（任意） | Secrets に `ANTHROPIC_API_KEY` がある場合だけ、Claude が一次資料を確認して修正案の PR を作る。**自動では取り込まない** | 同上（`propose` ジョブ） |
| 長期保存の依頼 | 毎月、Software Heritage に保存を依頼する | 同上 |
| テスト | push・PR ごとに Mac・Windows・Linux、Python 3.9/3.13 で点検ツールをテスト | `.github/workflows/test.yml` |
| 仕様（SPEC）のテスト | 同じ CI で、規則が出典台帳の一次資料までたどれるか、文書の URL が台帳に登録済みか、通信しない・`--no-echo` の約束、CLI の引数を削除していないか、版の一致を確認（自動 PR の変更もここで止まる） | `tests/test_contract.py`、[SPEC.md](SPEC.md) |
| リリース | `SKILL.md` の `version` が上がると、テストを通したうえで Release を作り、`.skill` と `.zip` を添付する | `.github/workflows/release.yml`、`tools/package.py` |
| Actions の更新 | Dependabot が使っている Actions の新しい版を月1回 PR で提案する | `.github/dependabot.yml` |

医学の内容を、人の確認なしに自動で書き換える仕組みは**意図的に入れていません**。誤りが入っても気づく人がいなくなるためです。自動化は「検知」と「提案」まで、取り込みは人が判断します。

## 2. 更新候補（`source-update` の Issue）への対応

1. Issue に書かれた見張り先を開き、**一次資料で**本当に新しい版・改正かを確認する。ナビゲーションの変更だけなら Issue を閉じる。
2. 新しい版なら、使っている箇所を探す：`python3 japanese-medical-writing/scripts/sources.py find <名前>`
3. 該当ファイルの記載を直す。一次資料で確かめられない記載には `【二次情報：出典】` を付ける。
4. 台帳を更新する：`python3 japanese-medical-writing/scripts/sources.py check-version <ID> --version "<新しい版>"`（新しい資料は `sources.py add`）
5. テスト：`python3 -m unittest discover -s tests`
6. `japanese-medical-writing/SKILL.md` の `metadata.version` を上げ、`last-reviewed` を更新して main に取り込む。Release が自動で作られる。

修正案の PR が自動で作られた場合も、上の 1・3 を人が確認してから取り込んでください。

## 3. 作者（オーナー）が今のうちにしておくこと

GitHub の公式ドキュメントで確認した仕組みです（2026年10月時点）。

- [ ] **アカウント後継者を指定する**：GitHub の Settings →「Successor settings」で、信頼できる人（GitHub アカウントが必要）を指定し、相手に承諾してもらう。後継者は、作者の死後に public リポジトリをアーカイブ・移管できる（死亡証明書の提出から7日、または訃報から21日後）。後継者は作者のアカウントにはログインできない。指定がない場合も、遺族・共同作業者が GitHub Support に申請できる（Deceased User Policy）。
  - https://docs.github.com/en/repositories/creating-and-managing-repositories/access-to-repositories
  - https://docs.github.com/en/site-policy/other-site-policies/github-deceased-user-policy
- [ ] **Organization に移し、オーナーを2人以上にする**（推奨）：GitHub はオーナーを2人以上置くことを推奨している。リポジトリを移管すると Issue・PR・Star・Secrets も移り、旧 URL は転送される。
  - https://docs.github.com/en/organizations/managing-peoples-access-to-your-organization-with-roles/maintaining-ownership-continuity-for-your-organization
- [ ] **Zenodo 連携を有効にする**：Zenodo に GitHub でログインし、このリポジトリのトグルをオンにする。以後 Release ごとに DOI が付き、GitHub とは別の場所に保存される（public リポジトリのみ）。メタデータは `CITATION.cff` を使う。
  - https://docs.github.com/en/repositories/archiving-a-github-repository/referencing-and-citing-content
- [ ] **（任意）修正案の自動作成を使う**：リポジトリの Settings → Actions → General で「Allow GitHub Actions to create and approve pull requests」をオンにし、Secrets に `ANTHROPIC_API_KEY` を登録する。API の料金は誰かが払い続ける必要があるので、払う人がいなくなったら Secret を削除すればこのジョブは止まる（他の仕組みには影響しない）。
  - https://code.claude.com/docs/en/github-actions

## 4. 止まったときの直し方

- **毎月の見張りが止まった**：public リポジトリでは、60日間リポジトリに動きがないとスケジュール実行が自動で無効になる（GitHub 公式）。見張りは毎月 `tools/watch-state.json` を commit するが、これが「動き」に数えられるかは公式に明記されていない。止まっていたら、Actions タブで `monthly-source-watch` を開き「Enable workflow」を押す。誰でも Issue や PR を出せば動きになる。
  - https://docs.github.com/en/actions/managing-workflow-runs-and-deployments/managing-workflow-runs/disabling-and-enabling-a-workflow
- **見張り先の URL が移転した**：Issue の「取得できなかった」欄に出る。`japanese-medical-writing/references/source-registry.json` の `watch_url` を新しい URL に直す。
- **テストが落ちる**：GitHub Actions のログで失敗したテストを確認する。Windows 固有の文字コード問題が多い。

## 5. 長期保存の場所

| 場所 | 内容 |
|---|---|
| GitHub | 本体。作者の死後は後継者・Organization が管理 |
| Zenodo | Release ごとのスナップショットと DOI（連携を有効にした場合） |
| Software Heritage | ソースコードの長期アーカイブ（毎月保存を依頼。https://www.softwareheritage.org/ ） |

GitHub Arctic Code Vault（2020年のスナップショット）に、今後新しく収蔵されるかは公式に確認できなかったため、保存先として当てにしない。

## 6. ライセンスと引き継ぎ

MIT License なので、誰でもフォーク（複製）して保守を続けられます。作者や後継者と連絡がつかなくなった場合も、フォークした人が新しい本家として更新を続けて構いません。その際は README の出典台帳と MAINTENANCE.md を引き継いでください。
