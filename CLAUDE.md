# かなたけの里公園 市政だより監視システム

福岡市の公式市政だより（市政だより）に掲載される「かなたけの里公園」関連記事を自動検知し、LINEで通知するシステム。

## プロジェクト構成

```
scraper/scraper.py       # スクレイピング本体
.github/workflows/       # GitHub Actions（毎日10時JST実行）
docs/index.html          # GitHub Pages（記事ビューワー）
data/articles.json       # ローカルキャッシュ
docs/data/articles.json  # Pages公開用データ
```

## Claude Codeとの協働について

このプロジェクトはClaude Codeとの**継続的な対話・改善**を通じて構築した。

### 協働の原則

- **一度で完成を求めない**：最初から完璧な指示を出すのではなく、動くものを作ってからフィードバックを繰り返した
- **「何をしたいか」を伝える**：「Pythonで○○を書いて」ではなく「公園の情報が更新されたら自分のLINEに届くようにしたい」という目的から始めた
- **結果を見て次を決める**：スクレイパーが動いたら通知を追加し、通知が届いたらUIを作る、という順序で積み上げた

### このアプローチが生んだもの

要件定義から実装・運用自動化まで、単一の完結したシステムとして仕上がった：

- テキスト版・HTML版の両方に対応したスクレイピング
- 令和/平成などの日本語年号変換
- 重複検知（同じ記事を2度通知しない）
- 差分コミット自動化（変更があった時だけpush）
- ダークテーマのWeb UIでコンテキスト付き記事閲覧

## ローカル実行

```bash
pip install -r scraper/requirements.txt
LINE_CHANNEL_ACCESS_TOKEN=xxx LINE_USER_ID=yyy python scraper/scraper.py
```

## 環境変数（GitHub Secrets）

| 変数名 | 説明 |
|---|---|
| `LINE_CHANNEL_ACCESS_TOKEN` | LINE Messaging APIのチャネルアクセストークン |
| `LINE_USER_ID` | 通知先のLINEユーザーID |
