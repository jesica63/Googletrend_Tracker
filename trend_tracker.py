# trend_tracker.py (v4.1 - GitHub Actions-Optimized Version)

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
import google.generativeai as genai # 導入 Gemini API 函式庫

# --- 設定所有全域變數 ---
SHEET_NAME_DASHBOARD = "最新趨勢儀表板"
SHEET_NAME_LOG = "完整歷史日誌"
CNA_FEEDS = { '政治': 'https://feeds.feedburner.com/rsscna/politics', '國際': 'https://feeds.feedburner.com/rsscna/intworld', '兩岸': 'https://feeds.feedburner.com/rsscna/mainland', '產經證券': 'https://feeds.feedburner.com/rsscna/finance', '科技': 'https://feeds.feedburner.com/rsscna/technology', '生活': 'https://feeds.feedburner.com/rsscna/lifehealth', '社會': 'https://feeds.feedburner.com/rsscna/social', '地方': 'https://feeds.feedburner.com/rsscna/local', '文化': 'https://feeds.feedburner.com/rsscna/culture'}

# --- 讀取金鑰並授權 (GitHub Actions 版本) ---
try:
    gcp_key_str = os.environ['GCP_SA_KEY']
    creds_dict = json.loads(gcp_key_str)
    sheet_id = os.environ['G_SHEET_ID']
    sender_email = os.environ['EMAIL_SENDER']
    receiver_email = os.environ['EMAIL_RECEIVER']
    email_password = os.environ['EMAIL_SENDER_APP_PASSWORD']
    gemini_api_key = os.environ['GEMINI_API_KEY'] # 讀取 Gemini API 金鑰
    print("✅ 所有密鑰從環境變數讀取成功。")
except KeyError as e:
    print(f"❌ 讀取環境變數失敗！請確認 GitHub Secrets 已設定。缺少金鑰: {e}")
    raise

# --- 設定 Gemini API ---
genai.configure(api_key=gemini_api_key)

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
                    all_articles.append({'title': entry.title, 'summary': entry.get('summary', ''), 'link': entry.link})
        except Exception as e:
            print(f"  > 讀取 [{category}] 失敗: {e}")
    print(f"--- [階段一完成] 總共從中央社載入了 {len(all_articles)} 則有效新聞 ---")
    return all_articles

def find_keyword_in_cna_news(keyword, cna_database):
    sub_keywords = keyword.split()
    for article in cna_database:
        full_text = article['title'] + article['summary']
        if all(sub_word in full_text for sub_word in sub_keywords):
            return {'title': article['title'], 'link': article['link']}
    return None

def generate_curiosity_questions(keyword, title):
    """
    根據關鍵字和新聞標題，使用 Gemini API 生成三個讀者好奇的問題。
    """
    print(f"    - [Gemini] 正在為 '{keyword}' 生成好奇問題...")
    try:
        prompt = f"""
        請扮演一個台灣財經媒體的典型讀者。你的閱讀習慣是使用手機迅速滑動瀏覽新聞。你特別關注以下幾類資訊：

        1.  **個人利益相關：** 例如各種優惠、熱門股票的獲利機會、自己在法律上或政策下能享受的權利與受惠。
        2.  **個人與國家安危相關：** 例如國家大事、全球政治緊張局勢、軍事動態、交通安全等。
        3.  **陌生但會令你好奇的事情或字眼：** 任何引起你好奇心的新概念或事件。

        現在，請根據以下提供的「關鍵字」與「新聞標題」，從上述任一或多個角度，發想出三個你會最想知道、最令你好奇的問題。

        請直接列出這三個好奇問題，使用編號列表格式 (例如 1. 2. 3.)。除了問題列表，請勿包含任何其他文字。

        ---
        關鍵字：{keyword}
        新聞標題：{title}
        ---
        """
        
        model = genai.GenerativeModel('gemini-1.5-pro-latest')
        response = model.generate_content(prompt)
        
        questions_raw = response.text.strip().split('\n')
        questions = [q.split('. ', 1)[-1].strip() for q in questions_raw if '. ' in q]
        
        while len(questions) < 3:
            questions.append('N/A')
            
        print(f"    - [Gemini] ✅ 成功生成問題。")
        return questions[:3]

    except Exception as e:
        print(f"    - [Gemini] ❌ 生成問題時發生錯誤: {e}")
        return ['N/A', 'N/A', 'N/A']

def format_email_body_html(matched_items, sheet_url):
    """將比對成功的項目格式化為 HTML 郵件內容"""
    header = "<h1>Google Trends 與中央社新聞比對成功通知</h1>"
    body = "<p>在本次執行中，以下熱門關鍵字成功在中央社新聞中找到對應內容，並已生成讀者可能好奇的問題：</p>"
    
    table = "<table border='1' style='border-collapse: collapse; width: 100%;'><tr><th style='padding: 8px; text-align: left; width: 20%;'>關鍵字</th><th style='padding: 8px; text-align: left; width: 40%;'>相關新聞標題</th><th style='padding: 8px; text-align: left; width: 40%;'>讀者好奇的問題</th></tr>"
    
    for item in matched_items:
        questions_html = "<ul style='margin: 0; padding-left: 20px;'>"
        for q in item.get('questions', []):
            if q != 'N/A':
                questions_html += f"<li>{q}</li>"
        questions_html += "</ul>"
        
        table += f"<tr><td style='padding: 8px; vertical-align: top;'>{item['keyword']}</td><td style='padding: 8px; vertical-align: top;'><a href='{item['cna_link']}'>{item['cna_title']}</a></td><td style='padding: 8px; vertical-align: top;'>{questions_html}</td></tr>"
        
    table += "</table>"
    footer = f"""
    <hr>
    <p>
        <a href="{sheet_url}">點此查看完整的 Google Sheet 歷史日誌 (含所有欄位)</a>
    </p>
    <p style='color: #888; font-size: 12px;'>
        這是一封自動化通知郵件，請勿回覆。
    </p>
    """
    return f"<html><body>{header}{body}{table}{footer}</body></html>"

def send_notification_email(subject, html_body):
    """發送郵件通知"""
    print("--- [郵件通知] 正在準備發送郵件... ---")
    message = MIMEMultipart("alternative")
    message["Subject"] = f"🚀 {subject}"
    message["From"] = sender_email
    message["To"] = receiver_email
    message.attach(MIMEText(html_body, "html"))
    context = ssl.create_default_context()
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.login(sender_email, email_password)
            server.sendmail(sender_email, receiver_email, message.as_string())
        print("✅ 郵件通知發送成功！")
    except Exception as e:
        print(f"❌ 郵件通知發送失敗！錯誤: {e}")

# --- 主邏輯函式 ---
def main():
    print("🚀 [主流程開始] 準備執行所有任務...")
    gc = gspread.service_account_from_dict(creds_dict)
    spreadsheet = gc.open_by_key(sheet_id)
    
    cna_articles_db = fetch_all_cna_news(CNA_FEEDS)

    print("\n" + "="*20 + " 開始 Google Trends 分析與交叉比對 " + "="*20)
    rss_url = "https://trends.google.com/trending/rss?geo=TW"
    feed = feedparser.parse(rss_url)
    
    rss_data = []
    matches_for_email = []

    print("--- [階段二] 開始處理與比對每一個關鍵字 ---")
    for entry in feed.entries:
        final_cna_link = '無'
        final_cna_title = ''
        
        q1, q2, q3 = 'N/A', 'N/A', 'N/A'
        
        cna_match_from_db = find_keyword_in_cna_news(entry.title, cna_articles_db)
        if cna_match_from_db:
            final_cna_link = cna_match_from_db['link']
            final_cna_title = cna_match_from_db['title']
        else:
            google_news_source = entry.get('ht_news_item_source', '')
            if '中央社' in google_news_source or 'CNA' in google_news_source:
                final_cna_link = entry.get('ht_news_item_url', '無')
                final_cna_title = entry.get('ht_news_item_title', entry.title)
        
        if final_cna_link != '無':
            print(f"  > [比對成功] '{entry.title}' 在中央社找到相關新聞！")
            
            questions = generate_curiosity_questions(entry.title, final_cna_title)
            q1, q2, q3 = questions
            
            matches_for_email.append({
                'keyword': entry.title, 
                'cna_title': final_cna_title, 
                'cna_link': final_cna_link,
                'questions': questions
            })
        
        rss_data.append({
            '關鍵字 (Title)': entry.title, '預估搜尋量 (Traffic)': entry.get('ht_approx_traffic', 'N/A'),
            '發布時間 (Published)': entry.get('published', 'N/A'),
            '相關新聞標題 (Summary)': f"[{entry.get('ht_news_item_source', '無來源')}] {entry.get('ht_news_item_title', '無直接相關新聞報導')}",
            '相關新聞連結': entry.get('ht_news_item_url', '無'),
            '中央社相關新聞網址': final_cna_link, '趨勢連結 (Link)': entry.link,
            '好奇1': q1,
            '好奇2': q2,
            '好奇3': q3,
        })

    df_rss = pd.DataFrame(rss_data)

    print("\n--- [階段三] 正在將所有結果寫入 Google Sheet ---")
    update_time_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    write_df_to_worksheet(spreadsheet, SHEET_NAME_DASHBOARD, df_rss, f"最新趨勢儀表板 (更新時間: {update_time_str})")
    append_df_to_worksheet(spreadsheet, SHEET_NAME_LOG, df_rss)
    
    if matches_for_email:
        email_subject = f"GoogleTrend快報：{len(matches_for_email)}個熱門關鍵字在中央社找到關聯新聞！"
        email_body = format_email_body_html(matches_for_email, spreadsheet.url)
        send_notification_email(email_subject, email_body)
    else:
        print("\n--- [郵件通知] 本次執行無成功比對項目，不發送郵件。 ---")

    print("\n🎉 全部任務執行完畢！")
    print(f"🔗 前往查看儀表板: {spreadsheet.url}")

# --- 執行程式 ---
if __name__ == "__main__":
    main()
