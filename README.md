# japanese-medical-writing

日本語の医学論文（和文誌の原著・症例報告・短報・総説・学会抄録・査読回答）を、投稿規定・報告ガイドライン・国内倫理指針に沿って書くための Agent Skill（`SKILL.md`）。

英語の科学論文スキルは多数あるが、和文誌の表記慣行（である調、句読点、全角/半角、略語の初出定義）や国内の倫理指針・試験登録（jRCT／UMIN-CTR）まで扱うものが見当たらなかったため作成した。

## 特徴

- **捏造しない設計**：ユーザーが出していない数値・文献・手続き・定型文は書かず、`【要確認】` `【要文献】` マーカーと未解決リストで返す。主張は claims ledger（台帳）で出典・確認者・確認日に紐づける。
- **科学的忠実性**：関連と因果、有意差なしと同等、リスク比とオッズ比、探索的解析と検証的解析を書き分ける。
- **機密保持**：未発表原稿・査読コメント・患者情報を検索クエリや外部サービスに入れない。lint は `--no-echo` で原稿文面を出力しない。
- **報告ガイドライン対応表**：CONSORT 2025 / STROBE / PRISMA 2020 / CARE / STARD / TRIPOD+AI など、デザインから選んで項目ごとの該当箇所を出力。
- **国内規制・申告**：人を対象とする生命科学・医学系研究に関する倫理指針（令和8年改正・2026年12月1日適用を含む）、臨床研究法、COI、著者貢献（CRediT）、データ共有声明、生成AI使用申告（ICMJE 2026年1月改訂）の記載例。
- **和文 lint**（標準ライブラリのみの Python）
  - `scripts/lint_ja.py`：です・ます混在、句読点混在、全角英数字、半角カナ、数値と単位の間隔、`p = 0.000`、p値のない「有意」、未定義略語、長文、未解決マーカー残存、字数カウント
  - `scripts/check_refs.py`：本文の引用番号と文献リストの対応・欠番・未引用・出現順
  - `scripts/check_numbers.py`：和文・英文抄録の数値が本文・表に存在するか

## 構成

```
japanese-medical-writing/
├── SKILL.md
├── references/   guidelines / structure / style-ja / ethics-coi / citations
├── assets/       claims_ledger.csv, templates/（原著・症例報告・学会抄録・査読回答）
└── scripts/      lint_ja.py, check_refs.py
```

## インストール

Claude Code（個人）:

```bash
git clone https://github.com/kajisho5/japanese-medical-writing.skill.git
cp -r japanese-medical-writing.skill/japanese-medical-writing ~/.claude/skills/
```

claude.ai：リリースの `.skill` ファイルをアップロード。

## 使用例

```
70代男性の化膿性脊椎炎の症例報告を書きたい。経過メモを貼るので、CAREに沿って和文誌向けに。
```

```
この原著論文の日本語を投稿前チェックして。投稿先は○○学会誌。
```

```bash
python3 scripts/lint_ja.py manuscript.md
python3 scripts/check_refs.py manuscript.md
python3 scripts/check_numbers.py manuscript.md
python3 scripts/lint_ja.py --count abstract.md
```

## 注意

- 本スキルは執筆補助であり、研究内容・医学的判断・投稿可否の責任は著者にある。
- 法令・指針・ガイドラインは改正される。参照ファイルの記載は作成時点（2026年10月）の確認結果で、使用時に一次情報で再確認すること。
- 生成AIを使った場合は投稿先の規定に従って申告すること。
- テンプレート・例中の人名・誌名・文献はすべて架空。

## 謝辞

設計の一部（証拠の台帳化、捏造禁止項目の範囲、抄録と本文の整合チェック、機密保持、査読対応の手順）は [K-Dense-AI/scientific-agent-skills](https://github.com/K-Dense-AI/scientific-agent-skills) の `scientific-writing`（MIT License）を参考にした。コード・文章の流用はなく、和文誌向けに独自に書き起こしている。

## License

MIT
