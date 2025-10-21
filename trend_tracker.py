# trend_tracker.py (v5.0 - with Smart Search & Enhanced Logic)

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
    gemini_api_key = os.environ['GEMINI_API_KEY']
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
    """
    抓取所有中央社 RSS Feeds 的新聞，並過濾掉特定關鍵字。
    """
    print("--- [階段一] 正在預先抓取所有中央社 RSS Feeds ---")
    all_articles = []
    # --- 新增：定義您不想看到的關鍵字 ---
    uninteresting_keywords = ['今彩', '大樂透', '發票', '威力彩', '樂透彩'] # 您可以根據需要繼續添加

    for category, url in feed_urls.items():
        try:
            feed = feedparser.parse(url)
            if feed.bozo: print(f"    - [警告] Feed '{category}' 格式可能不完整或有誤。")
            
            for entry in feed.entries:
                if hasattr(entry, 'title') and hasattr(entry, 'link'):
                    article_title = entry.title
                    
                    # --- 新增：檢查標題是否包含不感興趣的關鍵字 ---
                    is_uninteresting = False
                    for keyword in uninteresting_keywords:
                        if keyword in article_title:
                            is_uninteresting = True
                            break # 找到一個不感興趣的關鍵字就停止檢查，直接跳過這篇文章
                    
                    if not is_uninteresting:
                        all_articles.append({'title': article_title, 'summary': entry.get('summary', ''), 'link': entry.link})
                    else:
                        print(f"    - [過濾] 跳過標題包含不感興趣關鍵字的新聞: \"{article_title}\"")

        except Exception as e:
            print(f"  > 讀取 [{category}] 失敗: {e}")
            
    print(f"--- [階段一完成] 總共從中央社載入了 {len(all_articles)} 則有效新聞 (已過濾不感興趣內容) ---")
    return all_articles

# 【升級版】智慧搜尋函式，加入了關聯性評分邏輯
def find_keyword_in_cna_news(main_keyword, google_news_title, cna_database):
    """
    使用智慧演算法在中央社新聞中尋找高關聯性的新聞。
    1. 優先匹配新聞標題。
    2. 從 Google News 標題中提取輔助關鍵字，提高準確性。
    """
    primary_keywords = set(main_keyword.split())
    secondary_keywords = set(google_news_title.split())
    all_keywords = primary_keywords.union(secondary_keywords)

    best_match = None
    highest_score = 0

    for article in cna_database:
        current_score = 0
        article_title = article['title']
        article_summary = article['summary']

        # --- 關聯性評分機制 ---
        # 1. 主要關鍵字出現在標題中：最高分 (關聯性極高)
        if all(word in article_title for word in primary_keywords):
            current_score = 100
        
        # 2. 所有關鍵字 (包含輔助詞) 都出現在標題中：次高分
        elif all(word in article_title for word in all_keywords):
            current_score = 80

        # 3. 只有主要關鍵字出現在摘要中：低分 (避免誤判)
        elif all(word in (article_title + article_summary) for word in primary_keywords):
            current_score = 10
        
        if current_score > highest_score:
            highest_score = current_score
            best_match = {'title': article['title'], 'link': article['link']}

    # 只有分數夠高 (代表關聯性強) 才回傳結果
    if highest_score >= 80:
        return best_match
    else:
        return None

def generate_curiosity_questions(keyword, title):
    """
    根據關鍵字和新聞標題，使用 Gemini API 生成三個讀者好奇的問題。
    這個函式會從環境變數讀取私密的 Prompt 指令。
    """
    print(f"    - [Gemini] 正在為 '{keyword}' 生成好奇問題...")
    try:
        prompt_template = os.environ.get('GEMINI_PROMPT')
        if not prompt_template:
            print("❌ 錯誤：在環境變數中找不到 'GEMINI_PROMPT'。請檢查 GitHub Secrets 設定。")
            return ['N/A', 'N/A', 'N/A']

        prompt = prompt_template.format(keyword=keyword, title=title)
        
        model = genai.GenerativeModel('gemini-2.0-flash-lite')
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
    """發送郵件通知，支援多個收件人"""
    print("--- [郵件通知] 正在準備發送郵件... ---")
    message = MIMEMultipart("alternative")
    message["Subject"] = f"💡 {subject}" 
    message["From"] = sender_email
    
    # 這裡 receiver_email 依然是完整的字串，用於郵件標頭的顯示
    message["To"] = receiver_email 
    
    message.attach(MIMEText(html_body, "html"))
    context = ssl.create_default_context()
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.login(sender_email, email_password)
            
            # 【關鍵修改】將字串分割成一個 list，這才是 sendmail 函式真正需要的格式
            receiver_email_list = receiver_email.split(',')
            
            server.sendmail(sender_email, receiver_email_list, message.as_string())
        print(f"✅ 郵件通知發送成功！收件人: {receiver_email_list}")
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
        
        # 【修改】使用新的智慧搜尋函式，傳入主要關鍵字和 Google News 上下文標題
        google_news_title = entry.get('ht_news_item_title', '')
        cna_match_from_db = find_keyword_in_cna_news(entry.title, google_news_title, cna_articles_db)
        
        if cna_match_from_db:
            final_cna_link = cna_match_from_db['link']
            final_cna_title = cna_match_from_db['title']
        else:
            # 如果內部搜尋找不到，再檢查一次 Google News 是否直接提供了中央社的連結
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

        # ... (前面的程式碼) ...
    df_rss = pd.DataFrame(rss_data)

    print("\n--- [階段三] 正在準備將結果寫入 Google Sheet ---")

    # 【關鍵修復】檢查 DataFrame 是否為空，如果不為空才執行寫入操作
    if not df_rss.empty:
        update_time_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        print("--> 偵測到新趨勢資料，開始寫入工作表...")
        write_df_to_worksheet(spreadsheet, SHEET_NAME_DASHBOARD, df_rss, f"最新趨勢儀表板 (更新時間: {update_time_str})")
        append_df_to_worksheet(spreadsheet, SHEET_NAME_LOG, df_rss)
        
        if matches_for_email:
            email_subject = f"GoogleTrend洞察：{len(matches_for_email)}個熱門趨勢與讀者意圖分析"
            email_body = format_email_body_html(matches_for_email, spreadsheet.url)
            send_notification_email(email_subject, email_body)
        else:
            print("\n--- [郵件通知] 本次執行無成功比對項目，不發送郵件。 ---")
    else:
        # 如果 df_rss 是空的，打印提示訊息，並跳過所有寫入和郵寄操作
        print("--> Google Trends RSS 未回傳任何資料，本次不更新工作表。")

    print("\n🎉 全部任務執行完畢！")
    print(f"🔗 前往查看儀表板: {spreadsheet.url}")

# --- 執行程式 ---
if __name__ == "__main__":
    main()
