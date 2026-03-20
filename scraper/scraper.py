"""
市政だより かなたけの里公園 掲載チェッカー
- 福岡市HP（テキスト版）を巡回し、キーワードに一致する記事を抽出
- 新規掲載があればLINE通知を送信
- 結果を data/articles.json に保存
"""

import requests
from bs4 import BeautifulSoup
import json
import os
import re
from datetime import datetime

# -------------------------------------------------------
# 設定
# -------------------------------------------------------
KEYWORDS = ["かなたけの里公園", "かなたけの里", "かなたけ"]
BASE_URL = "https://www.city.fukuoka.lg.jp"
CONTEXT_CHARS = 400  # マッチ前後に含める文字数

DATA_FILE = os.path.join(os.path.dirname(__file__), "../docs/data/articles.json")


# -------------------------------------------------------
# 年度URL生成
# -------------------------------------------------------
def get_fiscal_year_urls():
    """現在の年度と前年度のテキスト一覧URLを返す。"""
    today = datetime.now()
    reiwa = today.year - 2018
    fiscal = reiwa - 1 if today.month < 4 else reiwa
    urls = []
    for yr in [fiscal, fiscal - 1]:
        if yr >= 1:
            urls.append(f"{BASE_URL}/shicho/koho/shisei/shisei/R{yr}txt.html")
    return urls


# -------------------------------------------------------
# インデックスページからtxtリンクを収集
# -------------------------------------------------------
def get_txt_links(index_url):
    try:
        resp = requests.get(index_url, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        print(f"[WARN] インデックス取得失敗: {index_url} → {e}")
        return []

    soup = BeautifulSoup(resp.content, "html.parser")
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not href.endswith(".txt"):
            continue
        if not href.startswith("http"):
            href = BASE_URL + href
        filename = href.split("/")[-1]
        date_match = re.search(r"(\d{8})", filename)
        date_str = date_match.group(1) if date_match else None
        label = a.get_text(strip=True)
        links.append({"url": href, "filename": filename, "date": date_str, "label": label})
    return links


# -------------------------------------------------------
# テキストファイル取得
# -------------------------------------------------------
def fetch_txt(url):
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        try:
            return resp.content.decode("utf-8")
        except UnicodeDecodeError:
            return resp.content.decode("shift-jis", errors="replace")
    except Exception as e:
        print(f"[WARN] テキスト取得失敗: {url} → {e}")
        return None


# -------------------------------------------------------
# キーワード検索
# -------------------------------------------------------
def search_keywords(text, keywords, context_chars=400):
    """
    テキスト内のキーワードを検索し、前後context_chars文字のコンテキストを返す。
    重複マッチ（同じ行の別キーワード）は排除。
    """
    matches = []
    seen_positions = set()

    for keyword in keywords:
        for m in re.finditer(re.escape(keyword), text):
            pos = m.start()
            # 近傍100文字以内の既存マッチはスキップ（重複防止）
            if any(abs(pos - s) < 100 for s in seen_positions):
                continue
            seen_positions.add(pos)

            start = max(0, pos - context_chars)
            end = min(len(text), m.end() + context_chars)
            context = text[start:end].strip()

            # 直前の■か●見出しを取得
            heading = ""
            heading_match = re.findall(r"[■●][^\n]+", text[:pos])
            if heading_match:
                heading = heading_match[-1].strip()

            matches.append({
                "keyword": keyword,
                "heading": heading,
                "context": context,
            })

    return matches


# -------------------------------------------------------
# データ永続化
# -------------------------------------------------------
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"articles": [], "checked_files": []}


def save_data(data):
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# -------------------------------------------------------
# LINE通知
# -------------------------------------------------------
def send_line_notification(articles):
    token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
    user_id = os.environ.get("LINE_USER_ID")
    if not token or not user_id:
        print("[INFO] LINE認証情報未設定 → 通知スキップ")
        return

    lines = ["📰 市政だよりに「かなたけの里公園」の掲載がありました！\n"]
    for art in articles:
        lines.append(f"▶ {art['date_label']}号（{art['label']}）")
        for m in art["matches"][:2]:
            if m["heading"]:
                lines.append(f"  {m['heading']}")
    lines.append("\n詳細はサイトで確認してください。")

    payload = {
        "to": user_id,
        "messages": [{"type": "text", "text": "\n".join(lines)}],
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    try:
        resp = requests.post(
            "https://api.line.me/v2/bot/message/push",
            headers=headers,
            json=payload,
            timeout=10,
        )
        resp.raise_for_status()
        print("[OK] LINE通知送信完了")
    except Exception as e:
        print(f"[ERROR] LINE通知失敗: {e}")


# -------------------------------------------------------
# ユーティリティ
# -------------------------------------------------------
def format_date(date_str):
    if date_str and len(date_str) == 8:
        y, m, d = date_str[:4], date_str[4:6].lstrip("0"), date_str[6:].lstrip("0")
        return f"{y}年{m}月{d}日"
    return date_str or "不明"


# -------------------------------------------------------
# メイン
# -------------------------------------------------------
def main():
    data = load_data()
    checked_files = set(data.get("checked_files", []))
    new_articles = []

    for index_url in get_fiscal_year_urls():
        print(f"[INFO] チェック中: {index_url}")
        for link in get_txt_links(index_url):
            filename = link["filename"]
            if filename in checked_files:
                continue

            print(f"[INFO] 新規ファイル処理: {filename}")
            text = fetch_txt(link["url"])
            checked_files.add(filename)

            if text is None:
                continue

            matches = search_keywords(text, KEYWORDS)
            if matches:
                article = {
                    "date": link["date"],
                    "date_label": format_date(link["date"]),
                    "label": link["label"],
                    "filename": filename,
                    "source_url": link["url"],
                    "matches": matches,
                }
                new_articles.append(article)
                print(f"[HIT] {filename}: {len(matches)}件マッチ")
            else:
                print(f"[MISS] {filename}: 掲載なし")

    # データ更新（新しい記事を先頭に）
    data["articles"] = new_articles + data.get("articles", [])
    data["checked_files"] = sorted(checked_files)
    data["last_updated"] = datetime.now().isoformat()
    save_data(data)
    print(f"[INFO] 保存完了: 累計{len(data['articles'])}件")

    if new_articles:
        send_line_notification(new_articles)
    else:
        print("[INFO] 新規掲載なし")


if __name__ == "__main__":
    main()
