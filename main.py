from datetime import datetime
import requests
import time
import os
import paramiko

# =================================================================
# 您的配置信息
# =================================================================

# 天行数据 API Key
TIAN_API_KEY = os.getenv("TIAN_API_KEY")
# Bark 推送 URL
BARK_URL = os.getenv("BARK_URL")
# SFTP 配置 (您的实际服务器信息)
SFTP_HOST = os.getenv("SFTP_HOST")         # 服务器 IP 或域名
SFTP_PORT = int(os.getenv("SFTP_PORT"))    # SFTP 端口
SFTP_USER = os.getenv("SFTP_USER")         # SFTP 用户名
SFTP_PASS = os.getenv("SFTP_PASS")         # SFTP 密码或密钥路径
# 远程上传目录，对应 Nginx 配置中的 /var/www/reports/
REMOTE_UPLOAD_DIR = os.getenv("REMOTE_UPLOAD_DIR")
# 公共访问 URL 前缀，对应您的域名配置
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL")

# 品牌信息
BRAND_NAME = "新视野N"
BRAND_COLOR = "#1E88E5"
BRAND_SLOGAN = "洞察趋势，拓展新视野"
QR_CODE_URL = "https://github.com/amliubo/New-Vision/blob/main/QR.jpg?raw=true"
# 主题配置
TOPICS = {
    "ai": "Ai资讯",
    "auto": "汽车新闻",
    "military":"军事新闻",
}

# =================================================================
# 核心功能函数
# =================================================================

def fetch_tian_news(category="auto", num=50):
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

def generate_styled_content(news_items, report_date, topic_name):
    """
    生成带品牌化样式的 HTML 文章主体内容片段 (不包含 <html>, <body>)。
    """
    lines = []
    
    # 🌟 A. 顶部品牌识别区 (Header)
    lines.append(f"""
        <div style="
            text-align:center;
            padding: 1px 0;
            margin: 4px 0 10px 0;
            background:#F5F6F7;
            border-radius:6px;
            line-height:1;
        ">
            <div style="
                font-size:18px;
                font-weight:700;
                color:{BRAND_COLOR};
            ">{BRAND_NAME}</div>

            <div style="
                font-size:14px;
                color:#777;
                margin-top:1px;
            ">{BRAND_SLOGAN}</div>
        </div>
    """)

    for idx, n in enumerate(news_items, 1):
        # 🌟 B. 新闻主体品牌润色 (标题和序号)
        title = n.get("title", "") + "。"
        
        lines.append(f"""
            <div style="display:flex; align-items:flex-start; margin-bottom: 10px; line-height: 1.5;">
                <span style="font-size: 16px; font-weight: bold; color: white; background-color: {BRAND_COLOR}; padding: 4px 8px; border-radius: 4px; margin-right: 8px; flex-shrink: 0;">{idx}</span>
                <p style="font-size: 16px; color: #333; font-weight: bold; margin: 0; flex-grow: 1;">{title}</p>
            </div>
        """)

        pic = n.get("picUrl")
        if pic:
            lines.append(f'<img src="{pic}" style="width:100%;height:auto; display: block; border-radius: 8px; margin: 10px 0;"><br>')

        desc = n.get("description", "")
        if desc:
            lines.append(f'<p style="font-size: 15px; color: #555; line-height: 1.7; margin: 0 0 5px 0; text-align: justify; text-indent: 2em;">{desc}</p>')

        # 🌟 B. 新闻主体品牌润色 (分隔线)
        if idx < len(news_items):
            lines.append(f"""
                <div style="width: 40px; height: 2px; background-color: #ddd; margin: 20px auto;"></div>
            """)

    lines.append(f"""
        <div style="
            text-align:center;
            padding: 1px 0;
            margin-top:14px;
            background:#F7F7F7;
            border-radius:6px;
        ">  
            <img src="{QR_CODE_URL}" alt="二维码" 
                style="width:180px; height:180px; margin:0 auto 10px auto; border-radius:6px; display:block;">
            <div style="font-size:12px; color:#888; margin-top:2px;">
                —— 今日 {BRAND_NAME} 资讯已送达 ——
            </div>
            <div style="font-size:12px; color:#bbb; margin-top:4px;">
                © {datetime.now().year} {BRAND_NAME}
            </div>
        </div>
    """)

    return "".join(lines)

def generate_simple_summary_card(news_items, report_title):
    """生成一个简单的摘要卡片，用于浏览器预览"""
    
    # 仅展示前5条新闻，用于快速预览
    lines = [f"""
    <div style="background-color: white; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); padding: 25px; font-family: 'Microsoft YaHei', sans-serif; max-width: 400px; margin: 20px auto;">
        <h3 style="color: {BRAND_COLOR}; margin-top: 0; border-bottom: 2px solid #eee; padding-bottom: 10px;">{report_title}</h3>
        <p style="color: #666; font-size: 14px; margin-bottom: 20px; text-align: center;">简要事件汇总 (仅供浏览器预览)</p>
        <ul style="list-style-type: none; padding: 0;">
    """]
    
    for idx, n in enumerate(news_items[:5], 1): 
        title = n.get("title", "")
        lines.append(f'<li style="margin-bottom: 12px; font-size: 15px;"><span style="color: {BRAND_COLOR}; font-weight: bold; margin-right: 5px;">{idx}.</span> {title}</li>')
        
    lines.append("""
        </ul>
        <p style="text-align: center; margin-top: 20px; font-size: 12px; color: #aaa;">请使用上方的按钮获取完整排版内容。</p>
    </div>
    """)
    return "".join(lines)


def generate_full_html_document(title, styled_content, news_items):
    """
    将样式内容包装成完整的 HTML 文档，并添加一键复制功能。
    """
    
    # 1. HTML 转义 styled_content，以便安全地放入 textarea
    escaped_styled_content = styled_content.replace('<', '&lt;').replace('>', '&gt;')
    
    # 2. 生成浏览器预览用的卡片
    simple_card_html = generate_simple_summary_card(news_items, title)

    # ⚠️ 关键：添加 <meta charset="UTF-8"> 解决乱码问题
    html_template = f"""<!DOCTYPE html>
<html lang="zh">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        /* 这里的 body 字体堆栈是必要的，确保浏览器预览效果正常 */
        body {{
            font-family: "Microsoft YaHei", "微软雅黑", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif, "Apple Color Emoji", "Segoe UI Emoji", "Segoe UI Symbol";
            line-height: 1.6;
            color: #333;
            margin: 0;
            padding: 0;
            background-color: #f4f4f4; /* 浅灰色背景 */
        }}
        #article-wrapper {{
            max-width: 600px;
            margin: 0 auto;
            padding: 20px 10px;
        }}
        /* 复制区域样式 */
        #copy-area {{
            background-color: #f0f7ff; /* 浅蓝色背景，更贴合品牌色 */
            border: 1px solid {BRAND_COLOR};
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 25px;
            text-align: center;
        }}
        .copy-button {{
            background-color: {BRAND_COLOR};
            color: white;
            padding: 10px 20px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-weight: bold;
            transition: background-color 0.3s;
            margin-top: 5px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .copy-button:hover {{
            background-color: #0d47a1;
        }}
        #raw-html-source {{
            /* 保持隐藏 */
            position: absolute;
            left: -9999px;
            width: 1px;
            height: 1px;
            opacity: 0;
        }}
        #status-message {{
            min-height: 1.2em;
            margin-top: 10px;
            color: #4CAF50;
            font-weight: bold;
        }}
        
        /* 浏览器预览区样式 (只包含卡片) */
        #article-content {{
            padding: 15px 0; 
        }}
        
    </style>
</head>
<body>
    <div id="article-wrapper">
        
        <!-- 🌟 顶部：HTML 源码复制区 (最可靠的复制方式) 🌟 -->
        <div id="copy-area">
            <p style="font-size: 16px; font-weight: bold; color: #333; margin-bottom: 10px;">🏆 复制步骤：获取公众号排版源码</p>
            <button class="copy-button" id="copy-btn">一键复制 HTML 源码</button>
            <p id="status-message"></p>
            <p style="font-size: 12px; color: #666; margin-top: 10px;">将此源码粘贴到公众号编辑器的“HTML代码”模式，即可获得完整排版。</p>
            <!-- 隐藏的 textarea 包含原始 HTML 片段 (已转义) -->
            <textarea id="raw-html-source">{escaped_styled_content}</textarea>
        </div>

        <!-- 🌟 浏览器渲染的【简单卡片】预览区 🌟 -->
        <div id="article-content">
            {simple_card_html}
        </div>
        
    </div>
    
    <script>
        // 实现自定义的非 alert 提示框
        function showStatus(message, isSuccess) {{
            const statusMessage = document.getElementById('status-message');
            statusMessage.style.color = isSuccess ? '#4CAF50' : '#F44336';
            statusMessage.innerText = message;
            setTimeout(() => statusMessage.innerText = '', 5000); // 5秒后清除
        }}

        document.getElementById('copy-btn').addEventListener('click', function() {{
            const textarea = document.getElementById('raw-html-source');
            
            // 确保内容被选中
            textarea.select();
            textarea.setSelectionRange(0, 99999); // 针对移动设备
            
            // 使用 execCommand('copy') (系统要求)
            try {{
                const successful = document.execCommand('copy');
                if (successful) {{
                    showStatus('源码已复制！', true);
                }} else {{
                    showStatus('复制失败！', false);
                }}
            }} catch (err) {{
                showStatus('复制失败！', false);
            }}
        }});
    </script>
</body>
</html>"""
    return html_template


def upload_html_via_sftp(article_content, filename):
    """通过 SFTP 将 HTML 文件上传到远程服务器"""
    
    # 创建临时目录
    temp_dir = "/tmp/newvision_reports"
    os.makedirs(temp_dir, exist_ok=True)
    temp_filename = os.path.join(temp_dir, filename)
    
    remote_path = os.path.join(REMOTE_UPLOAD_DIR, filename)
    public_url = os.path.join(PUBLIC_BASE_URL, filename)
    
    # 将内容写入本地临时文件
    with open(temp_filename, "w", encoding="utf-8") as f:
        f.write(article_content)
    
    # SFTP 上传
    try:
        transport = paramiko.Transport((SFTP_HOST, SFTP_PORT))
        transport.connect(username=SFTP_USER, password=SFTP_PASS)
        sftp = paramiko.SFTPClient.from_transport(transport)
        
        print(f"[SFTP] 正在上传 {temp_filename} 到 {remote_path}")
        sftp.put(temp_filename, remote_path)
        
        sftp.close()
        transport.close()
        
        # 清理本地临时文件
        os.remove(temp_filename)
        
        print(f"[SFTP] 文件已上传成功。")
        return public_url
        
    except Exception as e:
        print(f"[错误] SFTP 上传失败: {e}")
        if os.path.exists(temp_filename):
            os.remove(temp_filename)
        return None


def push_article_link_to_bark(title, article_url):
    """推送文章链接到 Bark"""
    bark_urls = [u.strip().rstrip("/") for u in BARK_URL.split(",") if u.strip()]
    
    link_body = f"""
[{BRAND_NAME}日报] - 已更新：{article_url}
    """
    payload = {
        "title": f"{title} (源码复制)",
        "body": link_body,
        "group": "每日新闻日报",
        "url": article_url
    }

    for bark in bark_urls:
        try:
            res = requests.post(bark, json=payload, timeout=15)
            print(f"[Bark] 链接推送结果: {res.text}")
        except Exception as e:
            print(f"[Bark 推送异常] {e}")
    time.sleep(1.5)


def main():
    today = datetime.now().strftime("%Y-%m-%d")

    for category, topic_name in TOPICS.items():
        newslist = fetch_tian_news(category, num=50)
        filtered = [n for n in newslist if n.get("ctime", "").startswith(today)]
        print(f"[INFO] {topic_name} 当日新闻数量: {len(filtered)} 条")

        if not filtered:
            push_article_link_to_bark(f"{today} {topic_name}（无更新）", "今天没有新闻更新。")
            continue

        report_title = f"{today} {topic_name}日报"

        # 1. 生成带品牌化的 HTML 内容片段 (这是要被复制的精简内容)
        styled_content = generate_styled_content(filtered, today, topic_name)
        
        # 2. 包装成完整 HTML 文档，但预览区显示卡片 (已加入一键复制逻辑)
        full_html_document = generate_full_html_document(report_title, styled_content, filtered)
        
        filename = f"{today}-{category}-{BRAND_NAME}.html" 
        
        # 3. 上传到服务器
        article_url = upload_html_via_sftp(full_html_document, filename)
        
        if article_url:
            # 4. 推送链接到 Bark
            push_article_link_to_bark(report_title, article_url)
            print(f"[完成] 已推送 {len(filtered)} 条 {topic_name} 新闻的链接到 Bark！")
        else:
            print(f"[失败] 未能获取 {topic_name} 文章链接，未推送 Bark 通知。")

        time.sleep(1.5)


if __name__ == "__main__":
    main()
