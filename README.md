# japanese-medical-writing

日本語の医学論文（和文誌の原著・症例報告・短報・総説・学会抄録・査読回答）を、投稿規定・報告ガイドライン・国内倫理指針に沿って書くための Agent Skill（`SKILL.md`）。

特定の AI に依存しない。オープンな SKILL.md 形式なので、Claude Code・OpenAI Codex・OpenCode など対応エージェントで動き、**ローカル LLM と組み合わせれば原稿を手元から一切出さずに使える**。チェックスクリプトとテンプレートは AI なしでも単体で使える。

英語の科学論文スキルは多数あるが、和文誌の表記慣行（である調、句読点、全角/半角、略語の初出定義）や国内の倫理指針・試験登録（jRCT／UMIN-CTR）まで扱うものが見当たらなかったため作成した。

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
- **和文 lint**（標準ライブラリのみの Python）
  - `scripts/lint_ja.py`：です・ます混在、句読点混在、全角英数字、半角カナ、数値と単位の間隔、`p = 0.000`、p値のない「有意」「優れていた」、未定義・低頻度の略語、「本邦初」の検索根拠、「証明」等の過大表現、長文、仮置き（TBD/XX/○○）・未解決マーカー残存、字数カウント
  - `scripts/check_refs.py`：本文の引用番号と文献リスト、図表番号と参照の対応・欠番・未参照・出現順
  - `scripts/check_privacy.py`：個人情報の候補（具体的な年月日、詳細な年齢、カルテ番号、電話・郵便番号・メール、住所、敬称・イニシャル、勤務先、画像ファイル名）
  - `scripts/check_numbers.py`：和文・英文抄録の数値が本文・表に存在するか、`12/48例（25.0%）` の割合の再計算
  - `scripts/check_all.py`：上の4つをまとめて実行
- **投稿前セルフ査読**：統計記述のチェックリスト、よく落とされる理由、主張ごとの判定（維持／弱める／修正／削除）、3段階の総合判定

## 構成

```
japanese-medical-writing/
├── SKILL.md
├── references/   guidelines / structure / style-ja / ethics-coi / citations / figures-tables /
│                 statistics-checklist / self-review / privacy-law / japanese-sources
├── assets/       claims_ledger.csv, journal_policy_record.md,
│                 templates/（原著・症例報告・学会抄録・査読回答）
└── scripts/      lint_ja.py, check_refs.py, check_numbers.py, check_privacy.py, check_all.py
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

患者情報を含む原稿は、ローカル LLM で動かすのが最も安全。例として Ollama＋OpenCode：

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

## 使用例（AI エージェントに）

```
70代男性の化膿性脊椎炎の症例報告を書きたい。経過メモを貼るので、CAREに沿って和文誌向けに。
```

```
この原著論文の日本語を投稿前チェックして。投稿先は○○学会誌。
```

## 注意

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
