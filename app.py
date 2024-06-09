import datetime
import sqlite3
import threading\
import requests
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage

# 建立 Flask 應用
app = Flask(__name__)

# Line Bot 的 Channel Access Token 和 Channel Secret
line_bot_api = LineBotApi('EVJjdnTQ+p02Btrm/1iTYnFlKcuwbmcSDJSHb2HA/i7DiWMX0zLSito0mejJUmLjafYFdAKduaffBVAq0NIvKsMGLWwggUDdY1tnebNiPf5R9vW9Ns+QJitUTdeVNnNKQCr1VKRDhAJGFZrk3G7nhgdB04t89/1O/w1cDnyilFU=')
handler = WebhookHandler('e9e71edac68e482a57c9d84c6a1862f3')

# 建立連接
conn = sqlite3.connect('calendar.db', check_same_thread=False)
cursor = conn.cursor()

# 建立事件表格
cursor.execute('''
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY,
        title TEXT NOT NULL,
        date DATE NOT NULL,
        time TIME,
        location TEXT
    )
''')
conn.commit()

# 新增事件
def add_event(title, date, time=None, location=None):
    cursor.execute('''
        INSERT INTO events (title, date, time, location)
        VALUES (?, ?, ?, ?)
    ''', (title, date, time, location))
    conn.commit()

# 查詢事件
def get_events():
    cursor.execute('SELECT * FROM events')
    return cursor.fetchall()

# 刪除事件
def delete_event(event_id):
    cursor.execute('DELETE FROM events WHERE id = ?', (event_id,))
    conn.commit()

# 檢查並提醒事件
def check_reminder():
    today = datetime.date.today()
    events = get_events()
    for event in events:
        event_date = datetime.datetime.strptime(event[2], '%Y-%m-%d').date()
        if event_date == today:
            message = "提醒：今天有 '{}' 事件，地點：{}，時間：{}".format(event[1], event[4], event[3])
            # 這裡可以改成將提醒訊息發送到指定的 Line 使用者
            print(message)

    # 設置計時器，每天檢查一次
    threading.Timer(86400, check_reminder).start()  # 86400 秒 = 1 天

# 處理 Line Bot 的訊息事件
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    # 解析接收到的訊息
    user_message = event.message.text.strip().lower()
    
    if user_message == '列出所有事件':
        events = get_events()
        if events:
            reply = "所有事件：\n"
            for event in events:
                reply += f"{event[0]}. {event[1]} - {event[2]} {event[3]} {event[4]}\n"
        else:
            reply = "沒有任何事件。"
    elif user_message.startswith('新增事件'):
        parts = user_message.split(',')
        if len(parts) == 5:
            _, title, date, time, location = parts
            add_event(title.strip(), date.strip(), time.strip(), location.strip())
            reply = "事件已新增。"
        else:
            reply = "新增事件格式錯誤。請使用格式：新增事件, 標題, 日期(YYYY-MM-DD), 時間(HH:MM), 地點"
    elif user_message.startswith('刪除事件'):
        parts = user_message.split(',')
        if len(parts) == 2:
            _, event_id = parts
            delete_event(event_id.strip())
            reply = "事件已刪除。"
        else:
            reply = "刪除事件格式錯誤。請使用格式：刪除事件, 事件ID"
    elif event.message.text.lower() == "天氣":
        weather_info = fetch_weather_data("淡水")
        reply = f"淡水區的天氣是：\n{weather_info}"
    else:
        reply = "無效的指令。請重新輸入。"
    
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
def fetch_weather_data(city):
    # 氣象局 API 的 URL
    url = "https://opendata.cwa.gov.tw/api/v1/rest/datastore/O-A0003-001?Authorization=CWA-7A752AE1-2953-4680-A2BA-6B1B13AAB708&format=JSON&StationId=466900"

    try:
        # 發送 GET 請求
        response = requests.get(url)

        # 檢查請求是否成功
        if response.status_code == 200:
            # 解析 JSON 回應
            data = response.json()

            # 提取並返回天氣資料
            if "records" in data and "Station" in data["records"]:
                station = data["records"]["Station"][0]  # 只取第一個城市的資料
                station_name = station["StationName"]
                weather_element = station["WeatherElement"]
                weather = weather_element.get("Weather", "N/A")
                temperature = weather_element.get("AirTemperature", "N/A")
                humidity = weather_element.get("RelativeHumidity", "N/A")
                return f"城市: {station_name}, 天氣: {weather}, 溫度: {temperature}, 濕度: {humidity}"
            else:
                return "無法取得天氣資訊。"
        else:
            return "無法取得天氣資訊。"
    except Exception as e:
        return f"發生錯誤: {e}"

if __name__ == "__main__":
    # 在啟動伺服器之前，啟動檢查提醒功能
    check_reminder()
    app.run()
