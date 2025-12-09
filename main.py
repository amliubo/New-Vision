import os
import time
import json
import requests
from datetime import datetime
from typing import List, Dict, Any, Optional
from openai import OpenAI

# =================================================================
# 配置信息
# =================================================================

TIAN_API_KEY = os.getenv("TIAN_API_KEY", "")
BARK_URL = os.getenv("BARK_URL", "")

MEDIASTACK_API_KEY = os.getenv("MEDIASTACK_API_KEY", "")
MEDIASTACK_BASE_URL = os.getenv("MEDIASTACK_BASE_URL", "")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "") 
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "")
# Supabase 配置
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

# 确保所有配置都已导入
try:
    from supabase import create_client, Client
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except ImportError:
    print("Warning: Supabase client not initialized. Install 'supabase-py'.")
    class MockSupabase:
        def table(self, name): return self
        def select(self, *args): return self
        def eq(self, *args): return self
        def limit(self, *args): return self
        def execute(self): return type('MockResponse', (object,), {'data': []})()
        def insert(self, record): return self
    supabase = MockSupabase()
except Exception as e:
    print(f"Supabase Client Error: {e}")
    class MockSupabase:
        def table(self, name): return self
        def select(self, *args): return self
        def eq(self, *args): return self
        def limit(self, *args): return self
        def execute(self): return type('MockResponse', (object,), {'data': []})()
        def insert(self, record): return self
    supabase = MockSupabase()


TOPICS = {
    "ai": "Ai资讯",
    "auto": "汽车新闻",
    "military": "军事新闻",
    "world": "国际新闻 (MediaStack EN)",
}

openai_client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)


# =================================================================
# 核心功能函数
# =================================================================

def fetch_tian_news(category="auto", num=50) -> List[Dict[str, Any]]:
    """从天行数据接口获取新闻列表"""
    try:
        resp = requests.post(
            f"https://apis.tianapi.com/{category}/index",
            data={"key": TIAN_API_KEY, "num": num},
            timeout=10
        )
        data = resp.json()
        if data.get("code") == 200:
            news_list = data.get("result", {}).get("newslist", [])
            print(f"[INFO] {TOPICS.get(category, category)}: 接口返回 {len(news_list)} 条新闻")
            return news_list
        print(f"[错误] 天行API返回错误码: {data.get('code')}, 消息: {data.get('msg')}")
        return []
    except Exception as e:
        print(f"[错误] 拉取 {category} 新闻异常: {str(e)}")
        return []

def fetch_mediastack_news(limit=50, lang='en', sources: Optional[str] = None, categories: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """从 MediaStack 接口获取新闻列表，允许指定语言和来源。"""
    try:
        params = {
            'access_key': MEDIASTACK_API_KEY,
            'languages': lang,
            'sort': 'published_desc',
            'limit': limit,
        }
        
        if sources:
            params['sources'] = sources
            
        if categories:
            params['categories'] = ','.join(categories)

        resp = requests.get(MEDIASTACK_BASE_URL, params=params, timeout=15)
        resp.raise_for_status() 
        
        data = resp.json()
        news_list = data.get("data", [])
        print(f"[INFO] MediaStack ({lang}): 接口返回 {len(news_list)} 条新闻")
        return news_list
        
    except requests.exceptions.RequestException as e:
        print(f"[错误] 拉取 MediaStack 新闻异常: {str(e)}")
        return []

def translate_and_summarize_by_gpt(title: str, description: str) -> Dict[str, str]:
    """使用 ChatGPT API 翻译并简单解读新闻内容"""
    
    if not title and not description:
        return {"title_zh": "", "summary_zh": ""}

    print(f"[DeepSeek] 正在翻译和解读: {title[:30]}...")
        
    prompt = f"""
    请完成以下任务，并严格以 JSON 格式返回结果，JSON 中只包含 'title_zh' 和 'summary_zh' 两个键：
    1. 将英文标题翻译成中文。
    2. 将英文描述翻译成中文，并在此基础上生成一个 50 字以内的中文解读/摘要。
    
    英文标题 (Title): "{title}"
    英文描述 (Description): "{description}"
    
    返回示例: {{"title_zh": "中文翻译标题", "summary_zh": "中文摘要解读内容..."}}
    """
    
    try:
        response = openai_client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[
                {"role": "system", "content": "你是一名专业的翻译和新闻摘要专家，请严格按照用户要求输出 JSON 格式的结果。"},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}, 
            temperature=0.0
        )
        
        result_json_str = response.choices[0].message.content.strip()
        result = json.loads(result_json_str)
        
        return {
            "title_zh": result.get("title_zh", title),
            "summary_zh": result.get("summary_zh", description)
        }
        
    except Exception as e:
        print(f"[错误] ChatGPT API 调用失败: {e}")
        # 失败时返回原文
        return {"title_zh": title, "summary_zh": description}

def check_duplicate(title: str, publish_time: str, category: str) -> bool:
    """检查 Supabase 中是否已存在相同标题和发布时间的新闻"""
    try:
        res = supabase.table("news_items").select("id").eq("title", title).eq("publish_time", publish_time).limit(1).execute()
        return len(res.data) > 0
    except Exception as e:
        print(f"[错误] 检查重复数据时发生异常: {e}")
        return False

def insert_news_to_supabase(news_items: List[Dict[str, Any]], category: str, api_source: str, source_format: str = 'tianapi'):
    """将新闻条目写入 Supabase，并进行去重检查，source_format用于区分数据结构"""
    inserted_count = 0
    duplicate_count = 0
    
    for n in news_items:
        if source_format == 'tianapi':
            title = n.get("title", "")
            publish_time = n.get("ctime", "")
            description = n.get("description", "")
            pic_url = n.get("picUrl", "")
        elif source_format.startswith('mediastack'):
            title = n.get("title", "")
            publish_time = n.get("published_at", "")
            description = n.get("description", "")
            pic_url = n.get("image", "")
            
        # 排除没有标题或发布时间的条目
        if not title or not publish_time:
            continue 

        if check_duplicate(title, publish_time, category):
            duplicate_count += 1
            continue

        record = {
            "category": category,
            "title": title,
            "description": description,
            "pic_url": pic_url,
            "api_source": api_source,
            "publish_time": publish_time
        }
        
        try:
            if hasattr(supabase, 'table') and supabase.__class__.__name__ != 'MockSupabase':
                supabase.table("news_items").insert(record).execute()
                inserted_count += 1
        except Exception as e:
            print(f"[致命错误] 插入 Supabase 数据失败: {e}, record: {record}")
            
    print(f"[INFO] 已处理 {len(news_items)} 条 {category} 新闻。")
    print(f"[INFO] 成功插入: {inserted_count} 条。已跳过重复数据: {duplicate_count} 条。")

def push_news_to_bark(news_items: List[Dict[str, Any]], category: str, report_date: str, api_source: str):
    """推送当日新闻标题到 Bark，并遵循新格式"""
    if not BARK_URL or not news_items:
        return
    bark_urls = [u.strip().rstrip("/") for u in BARK_URL.split(",") if u.strip()] 
    
    # 1. 构造 Body 内容列表
    content_lines = []
    
    # 2. Body 第一行：日期 + 分类
    content_lines.append(f"{report_date} {TOPICS.get(category, category)}") 
    
    # 3. 循环添加新闻标题 (只添加标题，避免过长)
    for i, n in enumerate(news_items):
        title = n.get('title', '')
        content_lines.append(f"{i+1}. {title}")

    content = "\n".join(content_lines) + '日报'
    
    # 4. 构造 Payload
    payload = {
        "title": f"{report_date} {TOPICS.get(category, category)} ({api_source.capitalize()})",
        "body": content,
        "group": f"{TOPICS.get(category, category)}日报",
        "level": "timeSensitive" if category == 'world' else "passive"
    }

    for bark in bark_urls:
        try:
            res = requests.post(bark, json=payload, timeout=15)
            print(f"[Bark] 推送结果: {res.text}") 
        except Exception as e:
            print(f"[Bark 推送异常] {e}")
    time.sleep(1.5)


# =================================================================
# 主流程
# =================================================================
def main():
    today_str = datetime.now().strftime("%Y-%m-%d")

    # --- 1. Tian API 数据拉取 ---
    print("\n--- 开始拉取 Tian API 数据 ---")
    tian_categories = [k for k in TOPICS.keys() if k not in ('world')]
    
    for category in tian_categories:
        topic_name = TOPICS.get(category, category)
        newslist = fetch_tian_news(category, num=50)
        filtered = [n for n in newslist if n.get("ctime", "").startswith(today_str)]
        print(f"[INFO] {topic_name} 当日新闻数量: {len(filtered)} 条")

        if filtered:
            insert_news_to_supabase(filtered, category, 'tianapi', source_format='tianapi')
            push_news_to_bark(filtered, category, today_str, api_source='tianapi') 
        else:
            print(f"[INFO] {topic_name} 今日无新闻。")
        time.sleep(1.5)

    # --- 2. MediaStack API 数据拉取 (只拉取英文，统一翻译) ---

    # 2.1. 国际英文新闻
    print("\n--- 2.1. 开始拉取 MediaStack 国际英文新闻 (翻译中) ---")
    ms_en_news = fetch_mediastack_news(
        limit=24,
        lang='en', 
        categories=['general', 'business','science', 'technology']
    ) 
    
    ms_en_filtered = [n for n in ms_en_news if n.get("published_at", "").startswith(today_str)]
    print(f"[INFO] {TOPICS['world']} 当日新闻数量: {len(ms_en_filtered)} 条")

    if ms_en_filtered:
        processed_news = []
        for n in ms_en_filtered:
            translation = translate_and_summarize_by_gpt(
                n.get("title", ""),
                n.get("description", "")
            )
            
            n['title'] = translation['title_zh']
            n['description'] = translation['summary_zh']
            
            processed_news.append(n)
            time.sleep(0.5)
            
        insert_news_to_supabase(processed_news, 'world', 'mediastack', source_format='mediastack')
        push_news_to_bark(processed_news, 'world', today_str, api_source='mediastack') 
    else:
        print(f"[INFO] {TOPICS['world']} 今日无新闻。")
    time.sleep(1.5)

    print("\n--- 数据采集完成 ---")


if __name__ == "__main__":
    main()