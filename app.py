import sqlite3
import datetime
import threading
import logging
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage, LocationMessage
import requests

app = Flask(__name__)

# LINE Bot 的 Channel Access Token 和 Channel Secret
LINE_CHANNEL_ACCESS_TOKEN = 'EVJjdnTQ+p02Btrm/1iTYnFlKcuwbmcSDJSHb2HA/i7DiWMX0zLSito0mejJUmLjafYFdAKduaffBVAq0NIvKsMGLWwggUDdY1tnebNiPf5R9vW9Ns+QJitUTdeVNnNKQCr1VKRDhAJGFZrk3G7nhgdB04t89/1O/w1cDnyilFU='
LINE_CHANNEL_SECRET = 'e9e71edac68e482a57c9d84c6a1862f3'

# 建立主数据库连接
conn = sqlite3.connect('calendar.db', check_same_thread=False)
cursor = conn.cursor()

# 建立行事历数据库连接
calendar_conn = sqlite3.connect('calendar_events.db', check_same_thread=False)
calendar_cursor = calendar_conn.cursor()

# LINE Bot API 初始化
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# 新增备忘录事件
def add_event(username, title, date, time=None, location=None):
    cursor.execute('''
        INSERT INTO events (title, date, time, location, username)
        VALUES (?, ?, ?, ?, ?)
    ''', (title, date, time, location, username))
    conn.commit()

# 查詢备忘录事件
def get_events(username, date):
    cursor.execute('SELECT * FROM events WHERE date = ? AND username = ?', (date, username))
    return cursor.fetchall()

# 查詢行事历事件
def get_calendar_events(date):
    calendar_cursor.execute('SELECT * FROM calendar WHERE date = ?', (date,))
    return calendar_cursor.fetchall()

# 刪除备忘录事件
def delete_event(event_id, username):
    cursor.execute('DELETE FROM events WHERE id = ? AND username = ?', (event_id, username))
    conn.commit()

# 檢查並提醒事件
def check_reminder():
    today = datetime.date.today()
    users = cursor.execute('SELECT DISTINCT username FROM events').fetchall()
    for user in users:
        events = get_events(user[0], str(today))
        calendar_events = get_calendar_events(str(today))
        for event in events:
            message = "提醒：今天有 '{}' 事件，地點：{}，時間：{}".format(event[1], event[4], event[3])
            line_bot_api.push_message(user[0], TextSendMessage(text=message))
        for event in calendar_events:
            message = "提醒：今天有 '{}' 行事曆事件".format(event[1])
            line_bot_api.push_message(user[0], TextSendMessage(text=message))

    # 設置計時器，每天檢查一次
    threading.Timer(86400, check_reminder).start()  # 86400 秒 = 1 天

# LINE Bot 訊息處理
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

# 處理文字訊息
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_message = event.message.text
    user_id = event.source.user_id  # 获取用户ID
    if user_message == "1":
        reply_message = "請輸入日期（YYYY-MM-DD）："
    elif user_message.startswith('日期：'):
        date = user_message.split('：')[1]
        events = get_events(user_id, date)
        calendar_events = get_calendar_events(date)
        reply_message = "日期 {} 的事件如下：\n".format(date)
        if events:
            for event in events:
                reply_message += "{} - {}\n".format(event[2], event[1])
        if calendar_events:
            reply_message += "\n行事曆事件如下：\n"
            for event in calendar_events:
                reply_message += "{}\n".format(event[1])
        if not events and not calendar_events:
            reply_message = "日期 {} 沒有任何事件。".format(date)
    elif user_message == "2":
        reply_message = "請輸入事件標題："
    elif user_message.startswith('標題：'):
        title = user_message.split('：')[1]
        date = input("請輸入日期（YYYY-MM-DD）：")
        time = input("請輸入時間（HH:MM）：")
        location = input("請輸入地點：")
        add_event(user_id, title, date, time, location)
        reply_message = "事件已新增。"
    elif user_message == "3":
        reply_message = "請輸入要刪除的事件 ID："
    elif user_message.startswith('ID：'):
        event_id = user_message.split('：')[1]
        delete_event(event_id, user_id)
        reply_message = "事件已刪除。"
    elif user_message.lower() == "天氣":
        weather_info = fetch_weather_data("淡水")
        reply_message = f"淡水區的天氣是：\n{weather_info}"
    else:
        reply_message = "請輸入'1'、'2' 或 '3' 來分別啟用'檢視備忘錄'、'新增備忘錄' 或 '刪除備忘錄' 。"
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_message))
    # 取得天氣資訊
def fetch_weather_data(city):
    # 氣象局 API 的 URL
    url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/O-A0003-001?Authorization=CWA-7A752AE1-2953-4680-A2BA-6B1B13AAB708&format=JSON&StationId=466900"

    try:
        # 發送 GET 請求
        response = requests.get(url)

        # 檢查請求是否成功
        if response.status_code == 200:
            # 解析 JSON 回應
            data = response.json()

            # 提取並返回天氣資料
            if "records" in data and "location" in data["records"]:
                location = data["records"]["location"][0]  # 只取第一個城市的資料
                weather_element = location["weatherElement"]
                weather = weather_element[0]["elementValue"]
                temperature = weather_element[1]["elementValue"]
                humidity = weather_element[5]["elementValue"]
                return f"天氣狀況: {weather}, 溫度: {temperature}℃, 濕度: {humidity}%"
            else:
                return "無法取得天氣資訊。"
        else:
            return "無法取得天氣資訊。"
    except Exception as e:
        return f"發生錯誤: {e}"

# 主程式功能
def main():
    check_reminder()  # 啟動計時器
    app.run(debug=True)

if __name__ == "__main__":
    main()
