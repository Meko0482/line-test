import datetime
import sqlite3
import threading
import logging
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage

app = Flask(__name__)

# LINE Bot 的 Channel Access Token 和 Channel Secret
LINE_CHANNEL_ACCESS_TOKEN = 'EVJjdnTQ+p02Btrm/1iTYnFlKcuwbmcSDJSHb2HA/i7DiWMX0zLSito0mejJUmLjafYFdAKduaffBVAq0NIvKsMGLWwggUDdY1tnebNiPf5R9vW9Ns+QJitUTdeVNnNKQCr1VKRDhAJGFZrk3G7nhgdB04t89/1O/w1cDnyilFU='
LINE_CHANNEL_SECRET = 'e9e71edac68e482a57c9d84c6a1862f3'

# 直接在代码中硬编码 LINE Bot 的 Channel Access Token 和 Channel Secret
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# 建立数据库连接
conn = sqlite3.connect('calendar.db')
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
            line_bot_api.broadcast(TextSendMessage(text=message))

    # 設置計時器，每天檢查一次
    threading.Timer(86400, check_reminder).start()  # 86400 秒 = 1 天

# 處理文字訊息
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_message = event.message.text
    if user_message == "1":
        events = get_events()
        if events:
            reply_message = "所有事件：\n"
            for event in events:
                reply_message += f"{event}\n"
        else:
            reply_message = "沒有任何事件。"
    elif user_message.startswith('新增事件:'):
        parts = user_message.split(':')
        if len(parts) == 5:
            title = parts[1].strip()
            date = parts[2].strip()
            time = parts[3].strip()
            location = parts[4].strip()
            add_event(title, date, time, location)
            reply_message = "事件已新增。"
        else:
            reply_message = "輸入格式錯誤。請按以下格式輸入：\n新增事件:<標題>:<日期(YYYY-MM-DD)>:<時間(HH:MM)>:<地點>"
    elif user_message.startswith('刪除事件:'):
        event_id = user_message.split(':')[1].strip()
        delete_event(event_id)
        reply_message = "事件已刪除。"
    elif user_message.lower() == "天氣":
        weather_info = fetch_weather_data("淡水")
        reply_message = f"淡水區的天氣是：\n{weather_info}"
    else:
        reply_message = "請輸入'1'來列出所有事件，或者輸入'新增事件:標題:日期:時間:地點'來新增事件，或者輸入'刪除事件:事件ID'來刪除事件。"

    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_message))

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

# 氣象局 API 的 URL
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

# 主程式功能
def main():
    check_reminder()  # 啟動計時器
    app.run(debug=True)

if __name__ == "__main__":
    main()

