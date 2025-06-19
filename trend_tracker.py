# trend_tracker.py (v3 - with Sheet Link in Email)

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
    print("✅ 所有密鑰從環境變數讀取成功。")
except KeyError as e:
    print(f"❌ 讀取環境變數失敗！請確認 GitHub Secrets 已設定。缺少金鑰: {e}")
    raise

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

# 【已修改】函式現在接收 sheet_url 參數
def format_email_body_html(matched_items, sheet_url):
    """將比對成功的項目格式化為 HTML 郵件內容"""
    header = "<h1>Google Trends 與中央社新聞比對成功通知</h1>"
    body = "<p>在本次執行中，以下熱門關鍵字成功在中央社新聞中找到對應內容：</p>"
    table = "<table border='1' style='border-collapse: collapse; width: 100%;'><tr><th style='padding: 8px; text-align: left;'>關鍵字</th><th style='padding: 8px; text-align: left;'>相關新聞標題</th></tr>"
    for item in matched_items:
        table += f"<tr><td style='padding: 8px;'>{item['keyword']}</td><td style='padding: 8px;'><a href='{item['cna_link']}'>{item['cna_title']}</a></td></tr>"
    table += "</table>"
    # 【已修改】footer 現在包含 sheet_url
    footer = f"""
    <hr>
    <p>
        <a href="{sheet_url}">點此查看完整的 Google Sheet 歷史日誌</a>
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
            matches_for_email.append({'keyword': entry.title, 'cna_title': final_cna_title, 'cna_link': final_cna_link})
        
        rss_data.append({
            '關鍵字 (Title)': entry.title, '預估搜尋量 (Traffic)': entry.get('ht_approx_traffic', 'N/A'),
            '發布時間 (Published)': entry.get('published', 'N/A'),
            '相關新聞標題 (Summary)': f"[{entry.get('ht_news_item_source', '無來源')}] {entry.get('ht_news_item_title', '無直接相關新聞報導')}",
            '相關新聞連結': entry.get('ht_news_item_url', '無'),
            '中央社相關新聞網址': final_cna_link, '趨勢連結 (Link)': entry.link,
        })

    df_rss = pd.DataFrame(rss_data)

    print("\n--- [階段三] 正在將所有結果寫入 Google Sheet ---")
    update_time_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    write_df_to_worksheet(spreadsheet, SHEET_NAME_DASHBOARD, df_rss, f"最新趨勢儀表板 (更新時間: {update_time_str})")
    append_df_to_worksheet(spreadsheet, SHEET_NAME_LOG, df_rss)
    
    # 【已修改】將 spreadsheet.url 傳遞給 format_email_body_html
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
