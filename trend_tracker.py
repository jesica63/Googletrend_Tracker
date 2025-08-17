# trend_tracker.py (v5.1 - Security Hardened)

# --- 導入所有函式庫 ---
import pandas as pd
import gspread
from gspread_dataframe import set_with_dataframe
import json
import feedparser
from datetime import datetime
import time
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import google.generativeai as genai
import html # <<< NEW: 導入 html 函式庫用於轉義

# --- 設定所有全域變數 ---
SHEET_NAME_DASHBOARD = "最新趨勢儀表板"
SHEET_NAME_LOG = "完整歷史日誌"
CNA_FEEDS = { '政治': 'https://feeds.feedburner.com/rsscna/politics', '國際': 'https://feeds.feedburner.com/rsscna/intworld', '兩岸': 'https://feeds.feedburner.com/rsscna/mainland', '產經證券': 'https://feeds.feedburner.com/rsscna/finance', '科技': 'https://feeds.feedburner.com/rsscna/technology', '生活': 'https://feeds.feedburner.com/rsscna/lifehealth', '社會': 'https://feeds.feedburner.com/rsscna/social', '地方': 'https://feeds.feedburner.com/rsscna/local', '文化': 'https://feeds.feedburner.com/rsscna/culture'}
UNINTERESTING_KEYWORDS = ['今彩', '大樂透', '發票', '威力彩', '樂透彩']
GEMINI_MODEL_NAME = 'gemini-1.5-pro-latest'

# --- 讀取金鑰並授權 (GitHub Actions 版本) ---
try:
    gcp_key_str = os.environ['GCP_SA_KEY']
    creds_dict = json.loads(gcp_key_str)
    sheet_id = os.environ['G_SHEET_ID']
    sender_email = os.environ['EMAIL_SENDER']
    receiver_email = os.environ['EMAIL_RECEIVER']
    email_password = os.environ['EMAIL_SENDER_APP_PASSWORD']
    gemini_api_key = os.environ['GEMINI_API_KEY']
    gemini_prompt_template = os.environ['GEMINI_PROMPT']
    print("✅ 所有密鑰從環境變數讀取成功。")
except KeyError as e:
    # <<< MODIFIED: 不直接暴露 e，因為 e 的內容 (金鑰名) 也是一種資訊洩露 >>>
    print(f"❌ 讀取環境變數失敗！請確認 GitHub Secrets 已設定。缺少必要的金鑰。")
    raise

# --- 設定 Gemini API ---
genai.configure(api_key=gemini_api_key)


# --- NEW: 安全性輔助函式 ---
def sanitize_error_message(error_msg: any) -> str:
    """清理錯誤信息，移除可能的敏感數據。"""
    sanitized = str(error_msg)
    # 這裡可以添加更多需要過濾的模式
    patterns_to_remove = [r'AIza[A-Za-z0-9_-]{35}']
    for pattern in patterns_to_remove:
        sanitized = re.sub(pattern, '[REDACTED]', sanitized)
    return sanitized

def escape_html(text: str) -> str:
    """對插入HTML的文本進行轉義，防止XSS攻擊。"""
    return html.escape(str(text))


# --- 定義所有輔助函式 ---
def write_df_to_worksheet(spreadsheet, sheet_name, df, title_text):
    try:
        worksheet = spreadsheet.worksheet(sheet_name)
        worksheet.clear()
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title=sheet_name, rows=len(df)+5, cols=len(df.columns)+1)
    worksheet.update('A1', [[title_text]], value_input_option='USER_ENTERED')
    worksheet.format('A1:G1', {'textFormat': {'bold': True, 'fontSize': 12}})
    set_with_dataframe(worksheet, df, row=3, col=1, include_index=False, resize=True)
    print(f"✅ 成功將資料寫入工作表 '{sheet_name}' (儀表板模式)。")

def append_df_to_worksheet(spreadsheet, sheet_name, df):
    try:
        worksheet = spreadsheet.worksheet(sheet_name)
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title=sheet_name, rows=1000, cols=len(df.columns)+1)
        worksheet.append_row(df.columns.values.tolist())
    worksheet.append_rows(df.values.tolist())
    print(f"✅ 成功將資料附加到工作表 '{sheet_name}' (日誌模式)。")

def fetch_all_cna_news(feed_urls):
    print("--- [階段一] 正在預先抓取所有中央社 RSS Feeds ---")
    all_articles = []
    for category, url in feed_urls.items():
        try:
            feed = feedparser.parse(url)
            if feed.bozo: print(f"    - [警告] Feed '{category}' 格式可能不完整或有誤。")
            for entry in feed.entries:
                if hasattr(entry, 'title') and hasattr(entry, 'link'):
                    article_title = entry.title
                    if not any(keyword in article_title for keyword in UNINTERESTING_KEYWORDS):
                        all_articles.append({'title': article_title, 'summary': entry.get('summary', ''), 'link': entry.link})
        except Exception as e:
            # <<< MODIFIED: 使用清理函式 >>>
            print(f"  > 讀取 [{category}] 失敗: {sanitize_error_message(e)}")
    print(f"--- [階段一完成] 總共從中央社載入了 {len(all_articles)} 則有效新聞 ---")
    return all_articles

def find_keyword_in_cna_news(main_keyword, google_news_title, cna_database):
    primary_keywords = set(main_keyword.split())
    secondary_keywords = set(google_news_title.split())
    all_keywords = primary_keywords.union(secondary_keywords)
    best_match, highest_score = None, 0
    for article in cna_database:
        current_score = 0
        article_title, article_summary = article['title'], article['summary']
        if all(word in article_title for word in primary_keywords): current_score = 100
        elif all(word in article_title for word in all_keywords): current_score = 80
        elif all(word in (article_title + article_summary) for word in primary_keywords): current_score = 10
        if current_score > highest_score:
            highest_score, best_match = current_score, {'title': article['title'], 'link': article['link']}
    return best_match if highest_score >= 80 else None

def generate_curiosity_questions(model, keyword, title):
    print(f"    - [Gemini] 正在為 '{keyword}' 生成好奇問題...")
    try:
        if not gemini_prompt_template:
            print("❌ 錯誤：在環境變數中找不到 'GEMINI_PROMPT'。")
            return ['N/A'] * 3
        prompt = gemini_prompt_template.format(keyword=keyword, title=title)
        response = model.generate_content(prompt)
        questions_raw = response.text.strip().split('\n')
        questions = [q.split('. ', 1)[-1].strip() for q in questions_raw if '. ' in q]
        while len(questions) < 3: questions.append('N/A')
        print(f"    - [Gemini] ✅ 成功生成問題。")
        return questions[:3]
    except Exception as e:
        # <<< MODIFIED: 使用清理函式 >>>
        print(f"    - [Gemini] ❌ 生成問題時發生錯誤: {sanitize_error_message(e)}")
        return ['N/A'] * 3

def format_email_body_html(matched_items, sheet_url):
    header = "<h1>Google Trends 與中央社新聞比對成功通知</h1>"
    body = "<p>在本次執行中，以下熱門關鍵字成功在中央社新聞中找到對應內容，並已生成讀者可能好奇的問題：</p>"
    table = "<table border='1' style='border-collapse: collapse; width: 100%;'><tr><th style='padding: 8px; text-align: left;'>關鍵字</th><th style='padding: 8px; text-align: left;'>相關新聞標題</th><th style='padding: 8px; text-align: left;'>讀者好奇的問題</th></tr>"
    for item in matched_items:
        # <<< MODIFIED: 對所有動態內容進行 HTML 轉義 >>>
        keyword_safe = escape_html(item['keyword'])
        cna_link_safe = escape_html(item['cna_link'])
        cna_title_safe = escape_html(item['cna_title'])
        questions_html = "<ul style='margin: 0; padding-left: 20px;'>"
        for q in item.get('questions', []):
            if q != 'N/A':
                questions_html += f"<li>{escape_html(q)}</li>"
        questions_html += "</ul>"
        table += f"<tr><td style='padding: 8px;'>{keyword_safe}</td><td style='padding: 8px;'><a href='{cna_link_safe}'>{cna_title_safe}</a></td><td style='padding: 8px;'>{questions_html}</td></tr>"
    table += "</table>"
    footer = f"<hr><p><a href=\"{escape_html(sheet_url)}\">點此查看完整的 Google Sheet 歷史日誌</a></p><p style='color: #888;'>自動化通知，請勿回覆。</p>"
    return f"<html><body>{header}{body}{table}{footer}</body></html>"

def send_notification_email(subject, html_body):
    print("--- [郵件通知] 正在準備發送郵件... ---")
    message = MIMEMultipart("alternative")
    message["Subject"], message["From"], message["To"] = f"💡 {subject}", sender_email, receiver_email
    message.attach(MIMEText(html_body, "html"))
    context = ssl.create_default_context()
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.login(sender_email, email_password)
            receiver_email_list = [email.strip() for email in receiver_email.split(',')]
            server.sendmail(sender_email, receiver_email_list, message.as_string())
        print(f"✅ 郵件通知發送成功！收件人: {receiver_email_list}")
    except Exception as e:
        # <<< MODIFIED: 使用清理函式 >>>
        print(f"❌ 郵件通知發送失敗！錯誤: {sanitize_error_message(e)}")

# --- 主邏輯函式 ---
def main():
    print("🚀 [主流程開始] 準備執行所有任務...")
    gc = gspread.service_account_from_dict(creds_dict)
    spreadsheet = gc.open_by_key(sheet_id)
    gemini_model = genai.GenerativeModel(GEMINI_MODEL_NAME) # <<< MODIFIED: 初始化一次模型
    
    cna_articles_db = fetch_all_cna_news(CNA_FEEDS)
    print("\n" + "="*20 + " 開始 Google Trends 分析與交叉比對 " + "="*20)
    feed = feedparser.parse("https://trends.google.com/trending/rss?geo=TW")
    
    rss_data, matches_for_email = [], []
    print("--- [階段二] 開始處理與比對每一個關鍵字 ---")
    for entry in feed.entries:
        final_cna_link, final_cna_title = '無', ''
        google_news_title = entry.get('ht_news_item_title', '')
        cna_match = find_keyword_in_cna_news(entry.title, google_news_title, cna_articles_db)
        if cna_match:
            final_cna_link, final_cna_title = cna_match['link'], cna_match['title']
        elif '中央社' in entry.get('ht_news_item_source', ''):
            final_cna_link, final_cna_title = entry.get('ht_news_item_url', '無'), entry.get('ht_news_item_title', entry.title)
        
        q1, q2, q3 = 'N/A', 'N/A', 'N/A'
        if final_cna_link != '無':
            print(f"  > [比對成功] '{entry.title}' 在中央社找到相關新聞！")
            questions = generate_curiosity_questions(gemini_model, entry.title, final_cna_title) # <<< MODIFIED: 傳入模型物件
            q1, q2, q3 = questions
            matches_for_email.append({'keyword': entry.title, 'cna_title': final_cna_title, 'cna_link': final_cna_link, 'questions': questions})
        
        rss_data.append({'關鍵字 (Title)': entry.title, '預估搜尋量 (Traffic)': entry.get('ht_approx_traffic', 'N/A'), '發布時間 (Published)': entry.get('published', 'N/A'), '相關新聞標題 (Summary)': f"[{entry.get('ht_news_item_source', '無來源')}] {entry.get('ht_news_item_title', '無')}", '相關新聞連結': entry.get('ht_news_item_url', '無'), '中央社相關新聞網址': final_cna_link, '趨勢連結 (Link)': entry.link, '好奇1': q1, '好奇2': q2, '好奇3': q3})

    df_rss = pd.DataFrame(rss_data)
    print("\n--- [階段三] 正在準備將結果寫入 Google Sheet ---")
    if not df_rss.empty:
        update_time_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        write_df_to_worksheet(spreadsheet, SHEET_NAME_DASHBOARD, df_rss, f"最新趨勢儀表板 (更新時間: {update_time_str})")
        append_df_to_worksheet(spreadsheet, SHEET_NAME_LOG, df_rss)
        if matches_for_email:
            subject = f"GoogleTrend洞察：{len(matches_for_email)}個熱門趨勢與讀者意圖分析"
            body = format_email_body_html(matches_for_email, spreadsheet.url)
            send_notification_email(subject, body)
        else:
            print("\n--- [郵件通知] 本次執行無成功比對項目，不發送郵件。 ---")
    else:
        print("--> Google Trends RSS 未回傳任何資料，本次不更新工作表。")

    print("\n🎉 全部任務執行完畢！")
    print(f"🔗 前往查看儀表板: {spreadsheet.url}")

# --- 執行程式 ---
if __name__ == "__main__":
    main()
