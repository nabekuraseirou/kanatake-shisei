# 市政だより × かなたけの里公園

福岡市市政だよりを毎日自動巡回し、「かなたけの里公園」の掲載を検出してLINE通知するシステムです。

## 機能

- 毎日10:00（JST）に福岡市HPのテキスト版を自動チェック
- 「かなたけの里」「かなたけの里公園」などを検出
- 新規掲載があればLINEに通知
- GitHubPagesにアーカイブを表示（コピーボタン付き）

---

## セットアップ手順

### Step 1 — GitHubリポジトリを作成

1. [github.com](https://github.com) にログイン（アカウントがなければ作成）
2. 右上「＋」→「New repository」
3. Repository name: `kanatake-shisei` など
4. **Private** を選択（自分だけが見るため）
5. 「Create repository」

### Step 2 — ファイルをプッシュ

ターミナルで以下を実行（このフォルダ内で）:

```bash
git init
git add .
git commit -m "初期構築"
git remote add origin https://github.com/あなたのユーザー名/kanatake-shisei.git
git push -u origin main
```

### Step 3 — GitHub Pages を有効化

1. リポジトリの「Settings」→「Pages」
2. Source: `Deploy from a branch`
3. Branch: `main` / Folder: `/docs`
4. 「Save」→ 数分後にURLが発行される

### Step 4 — LINE Messaging API のセットアップ

#### 4-1. LINE Official Account を作成

1. [LINE Developers Console](https://developers.line.biz/) にアクセス
2. 「新規プロバイダー作成」→ 名前は何でもOK（例：`kanatake`）
3. 「新規チャネル作成」→「Messaging API」を選択
4. チャネル名、説明を入力して作成

#### 4-2. チャネルアクセストークンを取得

1. 作成したチャネルの「Messaging API設定」タブを開く
2. 一番下の「チャネルアクセストークン」→「発行」
3. 表示された長い文字列をメモ

#### 4-3. 自分のユーザーIDを取得

1. 同ページの「あなたのユーザーID」をメモ（`U`で始まる文字列）
2. LINE公式アカウントを**自分のLINEアプリで友だち追加**する（通知を受け取るために必要）

### Step 5 — GitHub Secrets に登録

1. GitHubリポジトリの「Settings」→「Secrets and variables」→「Actions」
2. 「New repository secret」で以下の2つを登録：

| Name | Value |
|------|-------|
| `LINE_CHANNEL_ACCESS_TOKEN` | Step4-2 で取得したトークン |
| `LINE_USER_ID` | Step4-3 で取得したユーザーID（`U...`） |

### Step 6 — 初回実行（過去分の取り込み）

1. GitHubリポジトリの「Actions」タブを開く
2. 「市政だより巡回」ワークフロー→「Run workflow」
3. 完了後、GitHub Pagesのサイトに記事が表示される

---

## ファイル構成

```
.
├── .github/workflows/scrape.yml  # 自動実行スケジューラー
├── scraper/
│   ├── scraper.py                # スクレイパー本体
│   └── requirements.txt          # Pythonライブラリ
├── data/
│   └── articles.json             # 記事データ（自動更新）
└── docs/
    └── index.html                # 閲覧用サイト（GitHub Pages）
```

## 検索キーワード変更

`scraper/scraper.py` の以下の行を編集:

```python
KEYWORDS = ["かなたけの里公園", "かなたけの里", "かなたけ"]
```
