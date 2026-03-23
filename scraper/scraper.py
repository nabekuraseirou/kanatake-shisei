"""
市政だより かなたけの里公園 掲載チェッカー
- 福岡市HP（テキスト版 + HTML版）を巡回し、キーワードに一致する記事を抽出
- 新規掲載があればLINE通知を送信
- 結果を docs/data/articles.json に保存
"""

import requests
from bs4 import BeautifulSoup
import json
import os
import re
from datetime import datetime, timedelta

# -------------------------------------------------------
# 設定
# -------------------------------------------------------
KEYWORDS = ["かなたけの里公園", "かなたけの里", "かなたけ"]
BASE_URL = "https://www.city.fukuoka.lg.jp"
CONTEXT_CHARS = 400  # マッチ前後に含める文字数

DATA_FILE = os.path.join(os.path.dirname(__file__), "../docs/data/articles.json")

# HTML版インデックス
HTML_NUMBERS_URL = f"{BASE_URL}/shicho/koho/fsdweb/numbers.html"

# HTML版バックフィル上限（初回実行時に遡る日数）
HTML_BACKFILL_DAYS = 90


# -------------------------------------------------------
# 年度URL生成（テキスト版用）
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
# テキスト版：インデックスページからtxtリンクを収集
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
# テキスト版：テキストファイル取得
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
# HTML版：号一覧を取得
# -------------------------------------------------------
def get_html_issue_list():
    """numbers.htmlから全号のlist.htmlリストを取得"""
    try:
        resp = requests.get(HTML_NUMBERS_URL, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        print(f"[WARN] HTML号一覧取得失敗: {e}")
        return []

    soup = BeautifulSoup(resp.content, "html.parser")
    issues = []
    seen = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "list.html" not in href:
            continue
        if not href.startswith("http"):
            href = BASE_URL + href
        if href in seen:
            continue
        seen.add(href)
        # path_id例: "reiwa8_dayori/0315"
        parts = href.rstrip("/").split("/")
        path_id = f"{parts[-3]}/{parts[-2]}"
        label = a.get_text(strip=True)
        issues.append({"url": href, "path_id": path_id, "label": label})
    return issues


# -------------------------------------------------------
# HTML版：list.htmlから記事URLを取得
# -------------------------------------------------------
def get_article_links(list_url):
    try:
        resp = requests.get(list_url, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        print(f"[WARN] list.html取得失敗: {list_url} → {e}")
        return []

    soup = BeautifulSoup(resp.content, "html.parser")
    base = "/".join(list_url.split("/")[:-1])
    links = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not href.endswith(".html") or "list" in href:
            continue
        if href.startswith("/"):
            href = BASE_URL + href
        elif not href.startswith("http"):
            href = f"{base}/{href}"
        if "/fsdweb/" in href:
            links.add(href)
    return list(links)


# -------------------------------------------------------
# HTML版：記事ページからテキストを抽出
# -------------------------------------------------------
def fetch_html_text(url):
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, "html.parser")
        # コンテンツ候補セレクタを順に試す
        for selector in [{"class_": "cbody"}, {"id": "main"}, {"class_": "main"}, {"class_": "contents"}]:
            body = soup.find(**selector)
            if body:
                text = body.get_text(separator="\n", strip=True)
                if text:
                    return text
        # フォールバック：ノイズ要素を除去して全文取得
        for tag in soup(["script", "style", "nav", "header", "footer"]):
            tag.decompose()
        return soup.get_text(separator="\n", strip=True)
    except Exception as e:
        print(f"[WARN] HTML記事取得失敗: {url} → {e}")
        return None


# -------------------------------------------------------
# HTML版：path_idから日付・ラベルを生成
# -------------------------------------------------------
def parse_html_issue_date(path_id):
    """
    'reiwa8_dayori/0301' → ('20260301', '令和8年3月1日')
    '2024/0401'          → ('20240401', '令和6年4月1日')
    """
    parts = path_id.split("/")
    year_part = parts[0]
    mmdd = parts[1]
    month = int(mmdd[:2])
    day = int(mmdd[2:])

    if year_part.startswith("reiwa"):
        reiwa_num = int(re.search(r"\d+", year_part).group())
        year = reiwa_num + 2018
    else:
        year = int(year_part)
        reiwa_num = year - 2018

    date_str = f"{year}{mmdd}"
    label = f"令和{reiwa_num}年{month}月{day}日"
    return date_str, label


# -------------------------------------------------------
# キーワード検索（テキスト・HTML共通）
# -------------------------------------------------------
def search_keywords(text, keywords, context_chars=400):
    """
    テキスト内のキーワードを検索し、前後context_chars文字のコンテキストを返す。
    重複マッチ（近傍100文字以内）は排除。
    """
    matches = []
    seen_positions = set()

    for keyword in keywords:
        for m in re.finditer(re.escape(keyword), text):
            pos = m.start()
            if any(abs(pos - s) < 100 for s in seen_positions):
                continue
            seen_positions.add(pos)

            start = max(0, pos - context_chars)
            end = min(len(text), m.end() + context_chars)
            context = text[start:end].strip()

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
    return {"articles": [], "checked_files": [], "checked_html_issues": []}


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
# メイン：テキスト版巡回
# -------------------------------------------------------
def scrape_txt(data):
    checked_files = set(data.get("checked_files", []))
    new_articles = []

    for index_url in get_fiscal_year_urls():
        print(f"[INFO] テキスト版チェック: {index_url}")
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
                    "source_type": "txt",
                }
                new_articles.append(article)
                print(f"[HIT] {filename}: {len(matches)}件マッチ")
            else:
                print(f"[MISS] {filename}: 掲載なし")

    data["checked_files"] = sorted(checked_files)
    return new_articles


# -------------------------------------------------------
# メイン：HTML版巡回
# -------------------------------------------------------
def scrape_html(data):
    checked_html = set(data.get("checked_html_issues", []))
    existing_dates = {a["date"] for a in data.get("articles", [])}
    cutoff = (datetime.now() - timedelta(days=HTML_BACKFILL_DAYS)).strftime("%Y%m%d")
    new_articles = []

    issues = get_html_issue_list()
    print(f"[INFO] HTML版号数: {len(issues)}件取得")

    for issue in issues:
        path_id = issue["path_id"]

        if path_id in checked_html:
            continue

        date_str, date_label = parse_html_issue_date(path_id)

        # バックフィル上限：古い号はスキップ（済みとしてマーク）
        if date_str < cutoff:
            checked_html.add(path_id)
            continue

        # テキスト版で既に取得済みの号はスキップ
        if date_str in existing_dates:
            print(f"[INFO] HTML版スキップ（テキスト版取得済み）: {date_label}号")
            checked_html.add(path_id)
            continue

        print(f"[INFO] HTML版チェック: {date_label}号")
        article_urls = get_article_links(issue["url"])
        print(f"[INFO]   記事数: {len(article_urls)}件")

        issue_matches = []
        matched_url = None
        for art_url in article_urls:
            text = fetch_html_text(art_url)
            if text is None:
                continue
            matches = search_keywords(text, KEYWORDS)
            if matches:
                issue_matches.extend(matches)
                matched_url = art_url
                print(f"[HIT] {art_url}: {len(matches)}件マッチ")

        checked_html.add(path_id)

        if issue_matches:
            article = {
                "date": date_str,
                "date_label": date_label,
                "label": issue["label"] or f"{date_label}号",
                "filename": f"html_{path_id.replace('/', '_')}",
                "source_url": matched_url or issue["url"],
                "matches": issue_matches,
                "source_type": "html",
            }
            new_articles.append(article)

    data["checked_html_issues"] = sorted(checked_html)
    return new_articles


# -------------------------------------------------------
# メイン
# -------------------------------------------------------
def main():
    data = load_data()

    # テキスト版巡回
    new_txt = scrape_txt(data)

    # HTML版巡回
    new_html = scrape_html(data)

    new_articles = new_txt + new_html

    # 重複排除（同一日付は1件に）
    existing_dates = {a["date"] for a in data.get("articles", [])}
    deduped = [a for a in new_articles if a["date"] not in existing_dates]

    # データ更新（新しい記事を先頭に）
    data["articles"] = deduped + data.get("articles", [])
    data["last_updated"] = datetime.now().isoformat()
    save_data(data)
    print(f"[INFO] 保存完了: 累計{len(data['articles'])}件（新規{len(deduped)}件）")

    if deduped:
        send_line_notification(deduped)
    else:
        print("[INFO] 新規掲載なし")


if __name__ == "__main__":
    main()
