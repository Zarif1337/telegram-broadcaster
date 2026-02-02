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

# --- ১. কনফিগারেশন ---
TELEGRAM_TOKEN = os.environ['MY_BOT_TOKEN']
CHANNEL_ID = os.environ['MY_CHANNEL_ID']
GEMINI_KEY = os.environ.get('GEMINI_API_KEY')
WEATHER_KEY = os.environ.get('WEATHER_API_KEY')

# --- ২. Gemini সেটআপ ---
genai.configure(api_key=GEMINI_KEY)

# হিউম্যান পারসোনা এবং কন্টিনিউটি সেটআপ
system_prompt = """
তুমি 'NoN-Technical' টেলিগ্রাম চ্যানেলের একজন এডমিন। তুমি কোনো রোবট নও, তুমি একজন মানুষ।
তোমার ব্যবহারকারীদের সাথে তোমার সম্পর্ক বন্ধুর মতো।

তোমার লেখার স্টাইল:
১. সম্পূর্ণ 'Banglish' বা 'বাংলা-ইংরেজি' মিক্স করে লিখবে। (যেমন: "Ajke amra Linux niye kotha bolbo").
২. মাঝে মাঝে ইচ্ছা করে ১-২ টা বানান ভুল করবে বা টাইপো (typo) দিবে, যাতে মনে হয় তাড়াহুড়ো করে মোবাইল দিয়ে লিখছো।
৩. খুব কঠিন টেকনিক্যাল টার্ম ব্যবহার করবে না। একদম পানির মতো সহজ করে বোঝাবে।
৪. লেখার টোন হবে ক্যাজুয়াল (Casual)। "Bro", "Mama", "Boss" এসব ডাক ব্যবহার করতে পারো।
৫. আগের পোস্টের সাথে পরের পোস্টের একটা লিংক বা ধারাবাহিকতা রাখার চেষ্টা করবে।

তোমার কাজ:
- টেকনোলজি (Linux, AI, Android, Security) শেখানো।
- মাঝে মাঝে খোঁজ খবর নেওয়া।
- কোনো সিরিয়াস টিউটোরিয়াল দিলে সেটা যেন পূর্ণাঙ্গ হয়।
"""

generation_config = {
  "temperature": 1.1, # একটু বেশি হিউম্যান ও র‍্যান্ডম হওয়ার জন্য
  "top_p": 0.95,
  "max_output_tokens": 1024,
}

# Gemma 3 বা Flash মডেল
try:
    model = genai.GenerativeModel("gemini-3-flash-preview", generation_config=generation_config, system_instruction=system_prompt)
except:
    model = genai.GenerativeModel("gemini-3-pro", generation_config=generation_config, system_instruction=system_prompt)

# --- ৩. ভেরিয়েবল ও ডাটাবেস ---
HISTORY_FILE = "history.json"
bd_timezone = pytz.timezone("Asia/Dhaka")
bot = telebot.TeleBot(TELEGRAM_TOKEN)

# --- ৪. হেল্পার ফাংশন ---

def ask_ai(prompt, context=""):
    """AI কে কনটেক্সট সহ প্রশ্ন করা"""
    try:
        full_prompt = f"Previous Context: {context}\n\nTask: {prompt}"
        response = model.generate_content(full_prompt)
        return response.text.strip()
    except Exception as e:
        print(f"AI Error: {e}")
        return None

def load_history():
    """ডাটাবেস লোড করা"""
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            return json.load(f)
    return {"last_topic": "Intro", "messages": []}

def save_history(data):
    """ডাটাবেস সেভ করা"""
    with open(HISTORY_FILE, "w") as f:
        json.dump(data, f, indent=4)

def clean_old_messages(history):
    """মেসেজ ডিলিট করার লজিক (৩ দিন vs তাৎক্ষণিক)"""
    now = datetime.now(bd_timezone)
    remaining_messages = []
    
    # কপি তৈরি করে লুপ চালানো হচ্ছে যাতে রিমুভ করলে সমস্যা না হয়
    for msg in history["messages"]:
        msg_time = datetime.fromisoformat(msg["time"])
        msg_id = msg["id"]
        msg_type = msg["type"] # 'important' or 'casual'
        
        should_delete = False
        
        if msg_type == "casual":
            # ক্যাজুয়াল মেসেজ প্রতিবার ডিলিট হবে (Run হওয়ার সাথে সাথে)
            should_delete = True
            print(f"Deleting Casual msg: {msg_id}")
            
        elif msg_type == "important":
            # ইম্পর্ট্যান্ট মেসেজ ৩ দিন (৭২ ঘণ্টা) পর ডিলিট হবে
            if (now - msg_time) > timedelta(days=3):
                should_delete = True
                print(f"Deleting Expired Important msg: {msg_id}")
        
        if should_delete:
            try:
                bot.delete_message(CHANNEL_ID, msg_id)
            except Exception as e:
                print(f"Could not delete {msg_id}: {e}")
        else:
            remaining_messages.append(msg)
            
    history["messages"] = remaining_messages
    return history

def get_latest_news():
    try:
        feed = feedparser.parse("https://www.prothomalo.com/feed/")
        if feed.entries:
            return feed.entries[0].title
        return None
    except:
        return None

def get_prayer_times():
    try:
        url = "http://api.aladhan.com/v1/timingsByCity?city=Dhaka&country=Bangladesh&method=1"
        res = requests.get(url).json()
        return res['data']['timings']
    except:
        return None

# --- ৫. মেইন লজিক ---

def run_task():
    try:
        print("--- Bot Started (Human Mode) ---")
        
        # ১. ইতিহাস লোড এবং ক্লিন করা
        history = load_history()
        history = clean_old_messages(history)
        
        # ২. সময় এবং অবস্থা
        now = datetime.now(bd_timezone)
        current_hour = now.hour
        last_topic = history.get("last_topic", "General Tech")
        
        final_message = ""
        msg_type = "casual" # ডিফল্ট টাইপ
        new_topic = last_topic
        
        # ৩. নামাজের চেক (Priority 1 - Casual Type)
        prayer_times = get_prayer_times()
        prayer_map = {'Fajr': 'ফজর', 'Dhuhr': 'জোহর', 'Asr': 'আছর', 'Maghrib': 'মাগরিব', 'Isha': 'এশা'}
        priority = False
        
        if prayer_times:
            for waqt_en, time_str in prayer_times.items():
                if waqt_en in prayer_map:
                    p_hour, p_minute = map(int, time_str.split(':'))
                    prayer_dt = now.replace(hour=p_hour, minute=p_minute, second=0, microsecond=0)
                    if abs((now - prayer_dt).total_seconds()) <= 900: # ১৫ মিনিট রেঞ্জ
                        prompt = f"এখন {prayer_map[waqt_en]} নামাজের সময়। বন্ধুদের নামাজে যাওয়ার জন্য একটা রিমাইন্ডার দাও। খুব ছোট করে।"
                        final_message = ask_ai(prompt, context=f"Last topic was {last_topic}")
                        msg_type = "casual" # নামাজ রিমাইন্ডার বেশিক্ষণ রাখার দরকার নেই
                        priority = True
                        break

        # ৪. কন্টেন্ট জেনারেশন (যদি নামাজ না থাকে)
        if not priority:
            
            # রাত ১২টা - ভোর ৬টা (Casual)
            if 0 <= current_hour < 6:
                prompt = "অনেক রাত হয়েছে। বন্ধুদের ঘুমানোর কথা বলো। টেক নিয়ে কথা বলার দরকার নেই।"
                final_message = ask_ai(prompt)
                msg_type = "casual"

            # দিনের বেলা
            else:
                dice = random.randint(1, 100)
                
                # --- ৪০% ইম্পর্ট্যান্ট টেক পোস্ট (Series/Tutorial) ---
                if dice <= 40:
                    msg_type = "important"
                    
                    # আগের টপিক চেক করে ডিসিশন নিবে
                    prompt = f"""
                    গতবার আমরা কথা বলেছিলাম '{last_topic}' নিয়ে।
                    আজকে ওই টপিকের পরের ধাপ (Next Step) বা রিলেটেড কিছু নিয়ে একটা টিউটোরিয়াল বা টিপস দাও।
                    যদি গতবারের টপিক বোরিং হয়, তাহলে নতুন করে 'Linux' বা 'Automation' নিয়ে শুরু করো।
                    লেখাটা যেন শিখার মতো হয় এবং ৩ দিন চ্যানেলে থাকার যোগ্য হয়।
                    """
                    final_message = ask_ai(prompt, context=last_topic)
                    
                    # টপিক আপডেট করার জন্য AI কে জিজ্ঞেস করা দরকার নেই, আমরা টেক্সট থেকে অনুমান করতে পারি
                    # অথবা সিম্পলি রেখে দিতে পারি। 
                    new_topic = "Tech Tutorial Series" 

                # --- ২০% টেক নিউজ (Casual) ---
                elif dice <= 60:
                    msg_type = "casual"
                    news_title = get_latest_news()
                    prompt = f"এই নিউজটা নিয়ে ২ লাইনে কিছু বলো: '{news_title}'। এটা কি টেক লাভারদের জন্য জরুরি?"
                    final_message = ask_ai(prompt)
                    new_topic = "News Discussion"

                # --- ২০% মোটিভেশন / লাইফ হ্যাকস (Important) ---
                elif dice <= 80:
                    msg_type = "important" # ভালো কথা ৩ দিন থাকতে পারে
                    prompt = "ছাত্রদের হতাশা কাটানোর জন্য বা প্রোডাক্টিভিটি বাড়ানোর জন্য একটা সিরিয়াস কিন্তু ফ্রেন্ডলি উপদেশ দাও।"
                    final_message = ask_ai(prompt)
                    new_topic = "Motivation"

                # --- ২০% আড্ডা / খোঁজ খবর (Casual) ---
                else:
                    msg_type = "casual"
                    prompt = "বন্ধুদের জিজ্ঞেস করো তারা ওপরের টিউটোরিয়ালটা প্র্যাকটিস করেছে কিনা বা দিনকাল কেমন যাচ্ছে।"
                    final_message = ask_ai(prompt, context=last_topic)
                    new_topic = "Chatting"

        # ৫. মেসেজ পাঠানো
        if final_message:
            print(f"Sending ({msg_type}): {final_message[:50]}...")
            sent_msg = bot.send_message(CHANNEL_ID, final_message)
            
            # ৬. ডাটাবেস আপডেট
            new_entry = {
                "id": sent_msg.message_id,
                "type": msg_type,
                "time": now.isoformat()
            }
            
            history["messages"].append(new_entry)
            history["last_topic"] = new_topic
            save_history(history)
            
            # ৭. গিট সিংক (Robust)
            subprocess.run(["git", "config", "--global", "user.email", "bot@github.com"])
            subprocess.run(["git", "config", "--global", "user.name", "TeleBot"])
            subprocess.run(["git", "pull"]) 
            subprocess.run(["git", "add", HISTORY_FILE])
            subprocess.run(["git", "commit", "-m", f"Update history: {new_topic}"])
            subprocess.run(["git", "push"])
            print("Done!")

    except Exception as e:
        print(f"Critical Error: {e}")

if __name__ == "__main__":
    run_task()
