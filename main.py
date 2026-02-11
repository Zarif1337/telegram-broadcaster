import telebot
import os
import json
import requests
import random
import feedparser
import google.generativeai as genai
from datetime import datetime, timedelta
import pytz
import subprocess
import time

# --- ১. কনফিগারেশন ---
TELEGRAM_TOKEN = os.environ['MY_BOT_TOKEN']
CHANNEL_ID = os.environ['MY_CHANNEL_ID']
GEMINI_KEY = os.environ.get('GEMINI_API_KEY')
WEATHER_KEY = os.environ.get('WEATHER_API_KEY') # আপনার নতুন কি (Key)

# --- ২. Git Sync ফাংশন ---
def git_pull():
    try:
        print("📥 Pulling latest history...")
        subprocess.run(["git", "config", "--global", "user.email", "bot@github.com"])
        subprocess.run(["git", "config", "--global", "user.name", "TeleBot"])
        subprocess.run(["git", "pull", "--rebase"])
    except Exception as e:
        print(f"Git Pull Error: {e}")

def git_push(file_name, commit_msg):
    try:
        print("📤 Pushing update...")
        subprocess.run(["git", "add", file_name])
        subprocess.run(["git", "commit", "-m", commit_msg])
        subprocess.run(["git", "push"])
    except Exception as e:
        print(f"Git Push Error: {e}")

# --- ৩. Gemini সেটআপ ---
genai.configure(api_key=GEMINI_KEY)

system_prompt = """
তুমি 'NoN-Technical' টেলিগ্রাম চ্যানেলের একজন হিউম্যান এডমিন।
অডিয়েন্স: বিগিনার টেক লাভার।
ভাষা:বাংলা, তবে মাঝে মাঝে Banglish (বাংলা + ইংলিশ মিক্স)। টোন: ফ্রেন্ডলি, ক্যাজুয়াল।

কড়া নির্দেশ:
১. নিজেকে নতুন করে পরিচয় দিবে না।
২. মোটিভেশন দেওয়ার সময় ইসলামিক কাহিনী বা হাদীস, অথবা কুরআন এর আলোকে দিবে।
৩. চ্যাটিং স্টাইলে লিখবে।
৪. একইসাথে বাংলা আর ইংলিশ টেক্সট এ লিখবে, মাঝে মাঝে বানান ভুল করবে কেনো অডিয়েন্স ভাবে যে মানুষ টাইপ করসে।
৫. বার বার আগের পোস্ট গুলা তে রিএক্ট দিতে বলবে, চ্যানেল এ সাপোর্ট করতে বলবে।
"""

generation_config = {
  "temperature": 1.1, 
  "top_p": 0.95,
  "max_output_tokens": 8192,
}

# মডেল (Safe Model)
model = genai.GenerativeModel("gemini-3-flash-preview", generation_config=generation_config, system_instruction=system_prompt)

# --- ৪. ভেরিয়েবল ও ফাইল ---
HISTORY_FILE = "history.json"
bd_timezone = pytz.timezone("Asia/Dhaka")
bot = telebot.TeleBot(TELEGRAM_TOKEN)

# --- ৫. হেল্পার ফাংশন ---

def get_weather():
    """আপনার নির্দিষ্ট লোকেশনের আবহাওয়া আনবে"""
    if not WEATHER_KEY:
        return None
    try:
        # Dhunat Coordinates
        lat = "24.6440661"
        lon = "89.4987189"
        url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={WEATHER_KEY}&units=metric"
        
        response = requests.get(url).json()
        
        # ডাটা প্রসেসিং
        temp = response['main']['temp']
        feels_like = response['main']['feels_like']
        condition = response['weather'][0]['description']
        humidity = response['main']['humidity']
        
        return f"Location: Dhunat, Rajshahi. Temp: {temp}°C, Feels like: {feels_like}°C, Sky: {condition}, Humidity: {humidity}%"
    except Exception as e:
        print(f"Weather Error: {e}")
        return None

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f:
                return json.load(f)
        except: pass
    return {"recent_posts": []}

def save_history(data):
    with open(HISTORY_FILE, "w") as f:
        json.dump(data, f, indent=4)

def clean_old_messages(history):
    now = datetime.now(bd_timezone)
    valid_posts = []
    for post in history.get("recent_posts", []):
        try:
            post_time = datetime.fromisoformat(post["time"])
            is_expired = (now - post_time) > timedelta(days=3)
            is_casual = post.get("type") == "casual"
            
            if is_expired or is_casual:
                try: bot.delete_message(CHANNEL_ID, post["id"])
                except: pass
            else:
                valid_posts.append(post)
        except: pass
    history["recent_posts"] = valid_posts
    return history

def ask_ai(task, context_list):
    past_context = "\n".join([f"- {p['topic']}: {p['summary']}" for p in context_list[-3:]])
    full_prompt = f"CONTEXT:\n{past_context}\n\nCURRENT TASK:\n{task}\n\nDo NOT introduce yourself."
    try:
        response = model.generate_content(full_prompt)
        return response.text.strip()
    except: return None

def get_prayer_times():
    try:
        # ধুনটের জন্য স্থানাঙ্ক ব্যবহার করে নামাজের সময় আনা ভালো, তবে ঢাকা দিয়েও চলে (১-২ মিনিট ডিফারেন্স)
        # এখানে আমরা স্ট্যান্ডার্ড ঢাকার টাইমিং রাখছি, চাইলে কোঅর্ডিনেট বসাতে পারেন
        res = requests.get("http://api.aladhan.com/v1/timingsByCity?city=Dhaka&country=Bangladesh&method=1").json()
        return res['data']['timings']
    except: return None

def get_latest_news():
    try:
        feed = feedparser.parse("https://www.prothomalo.com/feed/")
        if feed.entries: return feed.entries[0].title
    except: return None

# --- ৬. মেইন রানার ---

def run_task():
    git_pull()
    history = load_history()
    history = clean_old_messages(history)
    
    now = datetime.now(bd_timezone)
    current_hour = now.hour
    recent_posts = history.get("recent_posts", [])
    
    final_msg = ""
    msg_type = "casual"
    current_topic = "Chat"
    msg_summary = "General"

    # A. নামাজ (Priority)
    prayer_times = get_prayer_times()
    priority = False
    if prayer_times:
        prayer_map = {'Fajr': 'ফজর', 'Dhuhr': 'জোহর', 'Asr': 'আছর', 'Maghrib': 'মাগরিব', 'Isha': 'এশা'}
        for waqt, time_str in prayer_times.items():
            if waqt in prayer_map:
                p_time = datetime.strptime(time_str, "%H:%M").time()
                p_dt = now.replace(hour=p_time.hour, minute=p_time.minute, second=0)
                if abs((now - p_dt).total_seconds()) <= 900:
                    final_msg = ask_ai(f"এখন {prayer_map[waqt]} নামাজের সময়। বন্ধুদের নামাজে ডাকো।", recent_posts)
                    priority = True
                    break
    
    # B. অন্যান্য কন্টেন্ট
    if not priority:
        if 0 <= current_hour < 6:
            final_msg = ask_ai("রাত হয়েছে, ঘুমানোর কথা বলো।", recent_posts)
        else:
            dice = random.randint(1, 100)
            
            # ৪০% চান্স: টেক সিরিজ
            if dice <= 40:
                msg_type = "important"
                current_topic = "Tech Series"
                last_topic = recent_posts[-1]["topic"] if recent_posts else "Intro"
                final_msg = ask_ai(f"আগের টপিক ছিল '{last_topic}'। এটার সাথে মিলিয়ে নতুন টেক টপিক শেখাও। অ্যাপ রিভিউ, কোনো মজার ওয়েবসাইট, ai ট্রিকস, useful পাইথন লাইব্রেরী, ইত্যাদি যেকোনোটা pick করো", recent_posts)
                msg_summary = "Tech Lesson"

            # ২০% চান্স: আবহাওয়া (ধুনট) - এখন এটা কাজ করবে!
            elif dice <= 60:
                weather_data = get_weather()
                if weather_data:
                    task = f"Weather Data: '{weather_data}'। এই আবহাওয়া নিয়ে বন্ধুদের সাথে টেক বা লাইফ নিয়ে আড্ডা দাও। যেমন খুশুড়ি বা মুরি খেতে বসা"
                    final_msg = ask_ai(task, recent_posts)
                    current_topic = "Weather"
                    msg_summary = "Weather update"
                else:
                    # আবহাওয়া না পেলে নিউজ
                    news = get_latest_news()
                    final_msg = ask_ai(f"News: {news}। এটা নিয়ে আলোচনা করো।", recent_posts)

            # ২০% চান্স: নিউজ
            elif dice <= 80:
                news = get_latest_news()
                final_msg = ask_ai(f"News: {news}। এটা নিয়ে বুঝাইয়া বলো আর এইটাই তোমার মনের অবস্থা রসিকতা সাথে অথবা কষ্টের সাথ বলো।", recent_posts)
                current_topic = "News"
                msg_summary = "News discussion"

            # বাকি সময়: আড্ডা
            else:
                final_msg = ask_ai("বন্ধুদের সাথে হালচাল বা টেক নিয়ে আড্ডা দাও।", recent_posts)
                current_topic = "Chat"

    # মেসেজ পাঠানো
    if final_msg:
        print(f"Sending ({current_topic}): {final_msg[:50]}...")
        try:
            sent = bot.send_message(CHANNEL_ID, final_msg)
            new_post = {
                "id": sent.message_id,
                "time": now.isoformat(),
                "type": msg_type,
                "topic": current_topic,
                "summary": msg_summary
            }
            history["recent_posts"].append(new_post)
            save_history(history)
            git_push(HISTORY_FILE, f"Update: {current_topic}")
            print("Done!")
        except Exception as e:
            print(f"Send Error: {e}")

if __name__ == "__main__":
    run_task()
