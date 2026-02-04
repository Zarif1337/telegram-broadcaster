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
WEATHER_KEY = os.environ.get('WEATHER_API_KEY')

# --- ২. Git Sync ফাংশন (বটের স্মৃতি রক্ষক) ---
def git_pull():
    """শুরুতেই গিটহাব থেকে লেটেস্ট মেমোরি নামাবে"""
    try:
        print("📥 Pulling latest history from GitHub...")
        subprocess.run(["git", "config", "--global", "user.email", "bot@github.com"])
        subprocess.run(["git", "config", "--global", "user.name", "TeleBot"])
        subprocess.run(["git", "pull", "--rebase"]) # Rebase ensures no merge conflicts
    except Exception as e:
        print(f"Git Pull Error: {e}")

def git_push(file_name, commit_msg):
    """কাজ শেষে মেমোরি আপলোড করবে"""
    try:
        print("📤 Pushing updated history to GitHub...")
        subprocess.run(["git", "add", file_name])
        subprocess.run(["git", "commit", "-m", commit_msg])
        subprocess.run(["git", "push"])
    except Exception as e:
        print(f"Git Push Error: {e}")

# --- ৩. Gemini সেটআপ ---
genai.configure(api_key=GEMINI_KEY)

# এখানে কন্টিনিউটি লজিক দেওয়া হয়েছে
system_prompt = """
তুমি 'NoN-Technical' টেলিগ্রাম চ্যানেলের একজন হিউম্যান এডমিন। তোমার নাম জারা (বা যা খুশি ভাবতে পারো, কিন্তু রোবট বলবে না)।
তোমার অডিয়েন্স: বিগিনার।
ভাষা: Banglish (বাংলা + ইংলিশ মিক্স)। টোন: ফ্রেন্ডলি, ক্যাজুয়াল, মাঝেমধ্যে হালকা টাইপো করবে।

কড়া নির্দেশ (Strict Instructions):
১. কখনো নিজেকে নতুন করে পরিচয় দিবে না (যেমন: "আমি তোমাদের মেন্টর", "আজকে আমি বলবো" - এসব বাদ)।
২. ধরে নিবে তুমি ১০ মিনিট আগেই তাদের সাথে কথা বলেছ। তাই সরাসরি টপিকে চলে যাবে।
৩. আগের পোস্টের সাথে মিল রেখে কথা বলবে।
৪. লেখার স্টাইল চ্যাটিং এর মতো হবে, প্রবন্ধ বা আর্টিকেলের মতো না।
"""

generation_config = {
  "temperature": 1.1, 
  "top_p": 0.95,
  "max_output_tokens": 8192, # টোকেন বাড়ানো হয়েছে যাতে মাঝপথে না থামে
}

# মডেল সিলেকশন (Safe Model)
model = genai.GenerativeModel("gemini-3-flash-preview", generation_config=generation_config, system_instruction=system_prompt)

# --- ৪. ভেরিয়েবল ও ফাইল ---
HISTORY_FILE = "history.json"
bd_timezone = pytz.timezone("Asia/Dhaka")
bot = telebot.TeleBot(TELEGRAM_TOKEN)

# --- ৫. হেল্পার ফাংশন ---

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    return {"last_topic": "Intro", "recent_posts": []}

def save_history(data):
    with open(HISTORY_FILE, "w") as f:
        json.dump(data, f, indent=4)

def clean_old_messages(history):
    """৩ দিনের পুরনো এবং ক্যাজুয়াল মেসেজ ডিলিট করবে"""
    now = datetime.now(bd_timezone)
    valid_posts = []
    
    for post in history.get("recent_posts", []):
        try:
            post_time = datetime.fromisoformat(post["time"])
            msg_id = post["id"]
            
            # ৩ দিন পার হলে অথবা টাইপ 'casual' হলে ডিলিট
            is_expired = (now - post_time) > timedelta(days=3)
            is_casual = post.get("type", "casual") == "casual"
            
            if is_expired or is_casual:
                print(f"🗑 Deleting message {msg_id} ({post.get('type')})")
                try:
                    bot.delete_message(CHANNEL_ID, msg_id)
                except Exception as e:
                    print(f"Delete failed: {e}")
            else:
                valid_posts.append(post)
        except Exception as e:
            print(f"Error processing post: {e}")
            
    history["recent_posts"] = valid_posts
    return history

def ask_ai(task, context_list):
    """AI কে আগের স্মৃতি মনে করিয়ে প্রশ্ন করা"""
    # গত ৩টি পোস্টের সামারি তৈরি
    past_context = "\n".join([f"- {p['topic']}: {p['summary']}" for p in context_list[-3:]])
    
    full_prompt = f"""
    CONTEXT (What you posted recently):
    {past_context}
    
    CURRENT TASK:
    {task}
    
    REMEMBER: Do NOT introduce yourself. Just continue the flow.
    """
    try:
        response = model.generate_content(full_prompt)
        return response.text.strip()
    except Exception as e:
        print(f"AI Error: {e}")
        return None

def get_prayer_times():
    try:
        res = requests.get("http://api.aladhan.com/v1/timingsByCity?city=Dhaka&country=Bangladesh&method=1").json()
        return res['data']['timings']
    except:
        return None

def get_latest_news():
    try:
        feed = feedparser.parse("https://www.prothomalo.com/feed/")
        if feed.entries: return feed.entries[0].title
    except: return None

# --- ৬. মেইন রানার ---

def run_task():
    # ধাপ ১: শুরুতেই মেমোরি সিংক করা (Force Git Pull)
    git_pull()
    
    history = load_history()
    # আগের আবর্জনা পরিষ্কার
    history = clean_old_messages(history)
    
    now = datetime.now(bd_timezone)
    current_hour = now.hour
    
    # লাস্ট টপিক এবং রিসেন্ট পোস্ট লিস্ট
    recent_posts = history.get("recent_posts", [])
    last_topic = recent_posts[-1]["topic"] if recent_posts else "None"
    
    final_msg = ""
    msg_type = "casual"
    current_topic = "Chat"
    msg_summary = "Just chatting"
    
    # ধাপ ২: কন্টেন্ট ডিসিশন
    
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
                    final_msg = ask_ai(f"এখন {prayer_map[waqt]} নামাজের সময়। ছোট করে নামাজে ডাকো।", recent_posts)
                    priority = True
                    msg_type = "casual" # নামাজ রিমাইন্ডার সেভ রাখার দরকার নেই
                    break
    
    # B. অন্যান্য কন্টেন্ট
    if not priority:
        if 0 <= current_hour < 6:
            final_msg = ask_ai("রাত হয়েছে, ঘুমানোর কথা বলো।", recent_posts)
            msg_type = "casual"
        else:
            dice = random.randint(1, 100)
            
            # ৪০% চান্স: টেক সিরিজ (Important)
            if dice <= 40:
                msg_type = "important"
                current_topic = "Tech Series"
                task = f"আগের টপিক ছিল '{last_topic}'। এটার সাথে কানেক্ট করে নতুন একটা টেক টপিক বা টিউটোরিয়াল দাও। লেখাটা যেন আগেরটার পার্ট-২ মনে হয়।"
                final_msg = ask_ai(task, recent_posts)
                msg_summary = "Tech tutorial follow-up"

            # ২০% চান্স: নিউজ
            elif dice <= 60:
                news = get_latest_news()
                task = f"News: '{news}'। এটা নিয়ে টেক লাভারদের মতো করে ২ লাইন বলো।"
                final_msg = ask_ai(task, recent_posts)
                current_topic = "News"
                msg_summary = f"Discussed news: {news}"

            # বাকি সময়: আড্ডা / মোটিভেশন
            else:
                msg_type = "important" if dice > 80 else "casual"
                task = "বন্ধুদের সাথে টেক বা লাইফ নিয়ে আড্ডা দাও। জিজ্ঞেস করো আগের পোস্টটা কাজে লেগেছে কিনা।"
                final_msg = ask_ai(task, recent_posts)
                current_topic = "Chat/Motivation"
                msg_summary = "Casual chat"

    # ধাপ ৩: মেসেজ পাঠানো ও সেভ
    if final_msg:
        print(f"Sending ({current_topic}): {final_msg[:50]}...")
        try:
            sent = bot.send_message(CHANNEL_ID, final_msg)
            
            # মেমোরিতে যোগ করা
            new_post = {
                "id": sent.message_id,
                "time": now.isoformat(),
                "type": msg_type,
                "topic": current_topic,
                "summary": msg_summary
            }
            history["recent_posts"].append(new_post)
            
            # সেভ এবং পুশ
            save_history(history)
            git_push(HISTORY_FILE, f"Update history: {current_topic}")
            print("History Synced!")
            
        except Exception as e:
            print(f"Send Error: {e}")

if __name__ == "__main__":
    run_task()
