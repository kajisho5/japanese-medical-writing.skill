# japanese-medical-writing

日本語の医学論文（和文誌の原著・症例報告・短報・総説・学会抄録・査読回答）を、投稿規定・報告ガイドライン・国内倫理指針に沿って書くための Agent Skill（`SKILL.md`）。

> **はじめての方は [GUIDE.md（使い方ガイド）](japanese-medical-writing/GUIDE.md) を読んでください。** 準備から頼み方、匿名化、投稿前の点検、禁止事項まで、順を追って説明しています。
> **原稿を手元から出さずに使いたい方は [LOCAL_LLM.md（ローカル LLM 導入手順・Mac/Windows）](japanese-medical-writing/LOCAL_LLM.md)** を参照してください。

特定の AI に依存しない。オープンな SKILL.md 形式なので、Claude Code・OpenAI Codex・OpenCode など対応エージェントで動き、**ローカル LLM と組み合わせれば原稿を手元から一切出さずに使える**。チェックスクリプトとテンプレートは AI なしでも単体で使える。

英語の科学論文スキルは多数あるが、和文誌の表記慣行（である調、句読点、全角/半角、略語の初出定義）や国内の倫理指針・試験登録（jRCT／UMIN-CTR）まで扱うものが見当たらなかったため作成した。

## 使い方と出力の例

以下はすべて架空の症例・架空の原稿で、このスキルを実際に動かした結果です。

### 例1：AI に症例報告を頼む

**入力（AI への依頼）**

```
架空の症例で、症例報告の練習原稿を作ってください。70歳代男性、発熱と腰痛で入院、
血液培養で黄色ブドウ球菌、MRIでL3/4化膿性脊椎炎、セファゾリン6週間で改善。投稿先は未定です。
```

**出力（7つのファイルと説明）**

| ファイル | 中身 |
|---|---|
| [00_reply.md](examples/case-report-practice/00_reply.md) | AI からの説明（作ったもの、【要確認】の読み方、次にすること） |
| [01_manuscript.md](examples/case-report-practice/01_manuscript.md) | 原稿本体（練習用・投稿不可の表示つき） |
| [02_unresolved.md](examples/case-report-practice/02_unresolved.md) | 未解決リスト（あなたが埋める情報の一覧） |
| [03_care_checklist.md](examples/case-report-practice/03_care_checklist.md) | CARE（症例報告の国際基準）との対応表 |
| [04_claims_ledger.csv](examples/case-report-practice/04_claims_ledger.csv) | 原稿に書いた事実と出どころの台帳 |
| [05_self_review.md](examples/case-report-practice/05_self_review.md) | 査読者の目で見た弱点と総合判定 |
| [06_check_all.txt](examples/case-report-practice/06_check_all.txt) | 機械チェックの結果 |

原稿の一部（与えられた6つの事実以外は作らず、`【要確認】` として残す）：

```markdown
**微生物学的検査**：血液培養で黄色ブドウ球菌が検出された。【要確認：採取セット数と陽性セット数、
採取時期と抗菌薬投与との前後関係、薬剤感受性（メチシリン感受性か否か）】
**画像所見**：MRIでL3/4の化膿性脊椎炎の所見を認めた。【要確認：具体的な信号変化、
硬膜外膿瘍・腸腰筋膿瘍の有無】

## 同意
【要確認：実症例では、患者本人（不能なら代諾者）から論文発表について文書による同意を得た旨を記載】
```

未解決リストの一部：

| No. | 原稿の場所 | 必要な情報 |
|---|---|---|
| 6 | 症例・微生物学的検査 | 血液培養の採取セット数と陽性数、採取と抗菌薬投与の前後関係、薬剤感受性 |
| 8 | 症例・臨床経過 | セファゾリンの投与量・経路、「改善」の判断根拠、心内膜炎の評価の有無、追跡期間 |
| 13 | 考察 第2段落 | 治療期間を検討した臨床研究または診療ガイドライン（版と年） |

セルフ査読の総合判定：**現状では投稿困難**（理由の上位：薬剤感受性・用量・心内膜炎評価がない／「改善」の根拠と追跡期間がない／文献・同意・倫理・COI が未記載）

### 例2：点検ツールで原稿をチェックする（AI なしでも可）

**入力**：誤りを含む架空の原稿 [sample.md](examples/check-demo/sample.md)

```bash
python3 japanese-medical-writing/scripts/check_all.py sample.md
```

**出力**（抜粋。全文は [check_all_output.txt](examples/check-demo/check_all_output.txt)）

```text
===== 表記・文体（lint_ja.py） =====
ERROR L10: 全角英数字「２」→ 半角に
WARN  L10: 数値と単位が詰まっている「5mg」→「5 mg」（誌規定確認）
ERROR L13: p = 0.000 表記 → p < 0.001 等に
WARN  L16: 「初の報告」「報告はない」系の主張に検索根拠がない
WARN  L16: 「証明」は臨床研究では強すぎることが多い
ERROR L7: です・ます調が混在
===== 文献・図表番号（check_refs.py） =====
ERROR L21: 文献 3 が本文で引用されていない
===== 数値の整合（check_numbers.py） =====
ERROR L13: 割合が合わない 12/48 = 25.0% だが 26.0% と記載
ERROR L4: 抄録の数値 1.82 が本文・表に見当たらない
===== 個人情報の候補（check_privacy.py） =====
CHECK L10: 具体的な年月日  「2025年4月3日」
CHECK L10: カルテ番号・ID・保険証番号  「カルテ番号: 123456」
CHECK L10: 人名（敬称・肩書・イニシャル）  「見本太郎さん」
===== まとめ =====
  要対応  表記・文体
  要対応  文献・図表番号
  要対応  数値の整合
  要対応  個人情報の候補
```

Word（`.docx`）の原稿もそのまま点検できます（ヘッダ・脚注・コメント・作成者名の個人情報も確認）。

### 例3：実名入りの資料をクラウドの AI に渡した場合

**入力**（架空の氏名・番号）

```
症例報告書いて。患者は見本 太郎さん（カルテ番号 A-778812、1958年3月14日生）、2026年2月3日に…
```

**出力**：作業せずに止まる。氏名・カルテ番号・生年月日・具体的な日付が含まれていることを**項目名だけ**で伝え（内容は復唱しない）、原稿や台帳には転記しない。次の手順として、匿名化してから渡す（`check_privacy.py` で確認）／施設に AI 利用の可否を確認する／ローカル LLM で作業する／架空症例で練習する、を案内する。

## 特徴

- **AI非依存・ローカル動作**：同梱の参照資料・テンプレート・チェックスクリプト（標準ライブラリのみ、通信なし）だけで完結する。投稿規定や文献はユーザーが手元のファイルで渡す。Web 検索はユーザーが許可したときだけ、公開情報の検索語に限って使う。
- **動作環境と資料のチェック**：クラウドの AI で動いている（または不明な）ときに、氏名・ID・具体的な日付・住所・顔写真などの直接識別子を含む資料や、施設規程でクラウド AI への入力が認められない資料を受け取ったら、作業を止めて匿名化やローカル LLM での作業を案内する。
- **個人情報保護・法令**：個人情報保護法（要配慮個人情報、学術研究の例外）、守秘義務、次世代医療基盤法、著作権（図表の転載・引用）、肖像の扱いを整理。`check_privacy.py` で年月日・ID・住所・敬称などの候補を検出。

- **捏造しない設計**：ユーザーが出していない数値・文献・手続き・定型文は書かず、`【要確認】` `【要文献】` マーカーと未解決リストで返す。主張は claims ledger（台帳）で出典・確認者・確認日に紐づける。
- **科学的忠実性**：関連と因果、有意差なしと同等、リスク比とオッズ比、探索的解析と検証的解析を書き分ける。
- **機密保持**：未発表原稿・査読コメント・患者情報を検索クエリや外部サービスに入れない。チェックスクリプトは `--no-echo` で原稿文面を出力しない。
- **報告ガイドライン対応表**：CONSORT 2025 / STROBE / PRISMA 2020 / CARE / STARD / TRIPOD+AI など、デザインから選んで項目ごとの該当箇所を出力。
- **国内の一次資料**：JAMJE 医学雑誌編集ガイドライン（2022）、ICMJE 日本語訳（2026）、日本医学会 COI 管理ガイドライン（2025）、倫理指針ガイダンス（症例報告の扱い）、臨床研究法改正（2025年5月施行）、和文誌の投稿規定の違い、日本語版報告ガイドラインの所在。
- **国内規制・申告**：人を対象とする生命科学・医学系研究に関する倫理指針（令和8年改正・2026年12月1日適用を含む）、臨床研究法、COI、著者貢献（CRediT）、データ共有声明、生成AI使用申告（ICMJE 2026年1月改訂）の記載例。
- **Word・文字コード対応**：`.docx`（本文・表・上付き引用番号・変更履歴、ヘッダ・脚注・コメント・作成者名）、UTF-8／Shift_JIS／EUC-JP／UTF-16 のテキストを読める
- **和文 lint**（標準ライブラリのみの Python）
  - `scripts/lint_ja.py`：です・ます混在、句読点混在、全角英数字、半角カナ、数値と単位の間隔、`p = 0.000`、p値のない「有意」「優れていた」、未定義・低頻度の略語、「本邦初」の検索根拠、「証明」等の過大表現、長文、仮置き（TBD/XX/○○）・未解決マーカー残存、字数カウント
  - `scripts/check_refs.py`：本文の引用番号と文献リスト、図表番号と参照の対応・欠番・未参照・出現順
  - `scripts/check_privacy.py`：個人情報の候補（具体的な年月日、詳細な年齢、カルテ番号、電話・郵便番号・メール、住所、敬称・イニシャル、勤務先、画像ファイル名）
  - `scripts/check_numbers.py`：和文・英文抄録の数値が本文・表に存在するか、`12/48例（25.0%）` の割合の再計算
  - `scripts/check_all.py`：上の4つをまとめて実行
- **投稿前セルフ査読**：統計記述のチェックリスト、よく落とされる理由、主張ごとの判定（維持／弱める／修正／削除）、3段階の総合判定

## 構成

```
japanese-medical-writing/          ← スキル本体（このフォルダごとインストール）
├── SKILL.md                       AI が読む手順書
├── GUIDE.md                       利用者向け使い方ガイド
├── LOCAL_LLM.md                   ローカル LLM 導入手順（Mac/Windows）
├── references/                    guidelines / structure / style-ja / ethics-coi / citations /
│                                  figures-tables / statistics-checklist / self-review /
│                                  privacy-law / japanese-sources / fields
├── assets/                        claims_ledger.csv, journal_policy_record.md,
│                                  templates/（原著・症例報告・学会抄録・査読回答・カバーレター）
└── scripts/                       check_all.py, lint_ja.py, check_refs.py, check_numbers.py,
                                   check_privacy.py, _textio.py
examples/                          出力例（架空）
tests/                             点検ツールの自動テスト
```

## インストール

```bash
git clone https://github.com/kajisho5/japanese-medical-writing.skill.git
```

置き場所はエージェントごとに違う（いずれも `japanese-medical-writing/` フォルダごと置く）。

| エージェント | 個人用 | プロジェクト用 |
|---|---|---|
| Claude Code | `~/.claude/skills/` | `.claude/skills/` |
| OpenAI Codex | `~/.agents/skills/` | `.agents/skills/` |
| OpenCode | `~/.config/opencode/skills/`（`~/.agents/skills/`・`~/.claude/skills/` も読む） | `.opencode/skills/`（`.agents/skills/`・`.claude/skills/` も読む） |
| その他の SKILL.md 対応ツール | 各ツールの説明に従う | |

```bash
# 例：Codex と OpenCode の両方から使う
mkdir -p ~/.agents/skills
cp -r japanese-medical-writing.skill/japanese-medical-writing ~/.agents/skills/
```

claude.ai：リリースの `.skill` ファイルをアップロード（claude.ai はクラウドで処理される）。

## 原稿を手元から出さずに使う（ローカル LLM）

患者情報を含む原稿は、ローカル LLM で動かすのが最も安全。**初心者向けの詳しい手順（Mac/Windows）は [LOCAL_LLM.md](japanese-medical-writing/LOCAL_LLM.md)。** 概要は Ollama＋OpenCode：

```bash
# Ollama を入れてモデルを取得した上で
ollama launch opencode
```

- OpenCode は 64k トークン以上のコンテキストを必要とする（Ollama 公式ドキュメント）。ローカルモデル側でコンテキスト長を設定する。
- Ollama にはクラウドで動くモデルもある。ローカル実行のモデルを選ぶこと（クラウドモデルを選ぶと外部で処理される）。
- 長い原稿・日本語の品質はモデルの性能に大きく左右される。品質が足りない場合でも、チェックスクリプト・テンプレート・参照資料は AI なしで使える。

## AI を使わずに使う

`scripts/` は Python 3.9 以上があれば単体で動く（追加インストール不要、通信なし）。`references/` は和文医学論文の手引きとして、`assets/templates/` はひな形としてそのまま読める。

```bash
python3 japanese-medical-writing/scripts/check_all.py 原稿.md
python3 japanese-medical-writing/scripts/check_all.py --draft 原稿.md      # 下書き段階
python3 japanese-medical-writing/scripts/check_privacy.py 原稿.md         # AI に渡す前の匿名化確認
python3 japanese-medical-writing/scripts/lint_ja.py --count 抄録.md       # 字数カウント
```

## テスト

```bash
python3 -m unittest discover -s tests -v
```

点検ツールの動作（検出・誤検出・文字コード・Word 読み込み）を確認する。GitHub Actions で Mac・Windows・Linux、Python 3.9 / 3.13 で実行している。

## 使用例（AI エージェントに）

```
70代男性の化膿性脊椎炎の症例報告を書きたい。経過メモを貼るので、CAREに沿って和文誌向けに。
```

```
この原著論文の日本語を投稿前チェックして。投稿先は○○学会誌。
```

## 注意

**禁止事項の一覧は [GUIDE.md の9節](japanese-medical-writing/GUIDE.md#9-禁止事項絶対にしないこと) を必ず読むこと。**

- 本スキルは執筆補助であり、研究内容・医学的判断・投稿可否の責任は著者にある。法令の記載は一般的な整理で、法的助言ではない。個別の判断は所属機関の倫理審査委員会・個人情報保護担当・法務に確認すること。
- 患者情報を含む原稿をクラウドの生成AI（Claude・ChatGPT・Gemini 等）に入力する前に、所属機関の規程と同意の範囲を確認すること。AI に渡す前に、自分の PC で `check_privacy.py` を実行して匿名化を確認するのが推奨。可能ならローカル LLM を使う。
- 法令・指針・ガイドラインは改正される。参照ファイルの記載は作成時点（2026年10月）の確認結果で、使用時に一次情報で再確認すること。
- 生成AIを使った場合は投稿先の規定に従って申告すること。
- テンプレート・例中の人名・誌名・文献はすべて架空。

## 謝辞

設計にあたり、以下の公開スキルの考え方を参考にした。コード・文章の流用はなく、和文誌向けに独自に書き起こしている。

- [K-Dense-AI/scientific-agent-skills](https://github.com/K-Dense-AI/scientific-agent-skills)（MIT）：証拠の台帳化、捏造禁止の範囲、抄録と本文の整合、機密保持、主張の強さ、図表チェック、投稿規定の記録
- [K-Dense-AI/claude-scientific-writer](https://github.com/K-Dense-AI/claude-scientific-writer)（MIT）：統計記述の誤り、指摘の書式、セルフ査読の区分
- [luwill/research-skills](https://github.com/luwill/research-skills)（README 記載 MIT）：数値の文脈欠落、出典の役割の取り違え、仮置き文字列の検出
- [aipoch/medical-research-skills](https://github.com/aipoch/medical-research-skills)（MIT）：主張強度の階層、図表参照の整合、限界の書き方
- [galaxy-dawn/claude-scholar](https://github.com/galaxy-dawn/claude-scholar)（MIT）：主張ごとの判定、回答書の根拠必須ルール
- [jaechang-hits/SciAgent-Skills](https://github.com/jaechang-hits/SciAgent-Skills)（CC BY 4.0）：用いる頻度の低い略語、誤差棒の定義

## License

MIT
