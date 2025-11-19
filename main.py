from datetime import datetime
import requests
import time
import os

TIAN_API_KEY = os.getenv("TIAN_API_KEY")
BARK_URL = os.getenv("BARK_URL")

# 支持的新闻分类
TOPICS = {
    "auto": "汽车新闻",
    "ai": "AI资讯",
    "military":'军事新闻'
    # "world": "国际新闻"
}
MAX_BODY_LEN = 3000

def fetch_tian_news(category="auto", num=50):
    try:
        resp = requests.post(
            f"https://apis.tianapi.com/{category}/index",
            data={"key": TIAN_API_KEY, "num": num},
            timeout=10
        )
        data = resp.json()
        if data.get("code") == 200 and data.get("result") and "newslist" in data["result"]:
            news_list = data["result"]["newslist"]
            print(f"[INFO] {TOPICS.get(category, category)}: 接口返回 {len(news_list)} 条新闻")
            return news_list
        return []
    except Exception as e:
        print(f"[错误] 拉取 {category} 新闻异常: {str(e)}")
        return []

def generate_wechat_article(news_items, report_date, topic_name):
    lines = [f"<h2>{report_date} {topic_name} 精选（共 {len(news_items)} 条）</h2><br>"]
    for idx, n in enumerate(news_items, 1):
        lines.append(f"<h3><span style='font-weight:bold; font-size:18px'>{idx}.</span> "
                     f"<span style='font-weight:bold'>{n.get('title','')}</span></h3>")
        if n.get("picUrl"):
            lines.append(f'<img src="{n["picUrl"]}" style="max-width:100%"><br>')
        lines.append(f"{n.get('description','')}<br><br>")
    return "".join(lines)


def push_wechat_article_to_bark(title, article):
    bark_urls = [u.strip().rstrip("/") for u in BARK_URL.split(",") if u.strip()]
    
    # 拆分过长内容
    parts = []
    while len(article) > MAX_BODY_LEN:
        split_idx = article.rfind('<br><br>', 0, MAX_BODY_LEN)
        if split_idx == -1:
            split_idx = MAX_BODY_LEN
        parts.append(article[:split_idx])
        article = article[split_idx:]
    if article.strip():
        parts.append(article)
    
    for part_idx, part in enumerate(parts, 1):
        payload = {
            "title": f"{title}" + (f" (续 {part_idx}/{len(parts)})" if len(parts) > 1 else ""),
            "body": part,
            "group": "每日新闻日报"
        }
        for bark in bark_urls:
            try:
                res = requests.post(bark, json=payload, timeout=15)
                try:
                    data = res.json()
                    print(f"[Bark] {data}")
                except Exception:
                    print(f"[Bark 返回非 JSON] {res.text}")
            except Exception as e:
                print(f"[Bark 推送异常] {e}")
        time.sleep(1.5)

def main():
    today = datetime.now().strftime("%Y-%m-%d")
    
    for category, topic_name in TOPICS.items():
        newslist = fetch_tian_news(category, num=50)
        filtered = [n for n in newslist if today in n.get("ctime","")]
        print(f"[INFO] {topic_name} 当日新闻数量: {len(filtered)} 条")
        
        if not filtered:
            push_wechat_article_to_bark(f"{today} {topic_name}（无更新）", "今天没有新闻更新。")
            continue
        
        article = generate_wechat_article(filtered, today, topic_name)
        push_wechat_article_to_bark(f"{today} {topic_name}日报", article)
        print(f"[完成] 已推送 {len(filtered)} 条 {topic_name} 新闻到 Bark！")
        time.sleep(1.5)

if __name__ == "__main__":
    main()
