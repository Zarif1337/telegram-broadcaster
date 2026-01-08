import telebot
import os
import requests
import random
import feedparser  # খবর পড়ার জন্য
from datetime import datetime
import pytz
import subprocess

# --- কনফিগারেশন ---
API_TOKEN = os.environ['MY_BOT_TOKEN']
CHANNEL_ID = os.environ['MY_CHANNEL_ID']

# বাংলাদেশ টাইমজোন
bd_timezone = pytz.timezone("Asia/Dhaka")
DATA_FILE = "last_id.txt"

bot = telebot.TeleBot(API_TOKEN)

# --- কন্টেন্ট সেকশন ---

# ১. সাধারণ মেসেজ (Day/Night)
day_messages = [
    "হ্যালো বন্ধুরা, কি খবর?", "পড়াশোনা কেমন চলছে?", 
    "মোবাইল রেখে একটু রেস্ট নাও।", "আজকের দিনটা প্রোডাক্টিভ ছিল তো?",
    "নতুন কিছু শিখেছো আজ?"
]
night_messages = [
    "ঘুমিয়ে পড়, অনেক রাত হয়েছে।", "রাত জাগা শরীরের জন্য খারাপ।",
    "Vuuuuuuutttttt! 👻", "থাপ্পড় মারবো, ফোন রাখো!",
    "এখনো জাগনা কেন?", "শুভ রাত্রি! ফোন দূরে রাখো।"
]

# ২. শিক্ষামূলক: ইংরেজি শব্দভাণ্ডার (Vocabulary)
vocab_list = [
    "Word: **Ambitious** (উচ্চাকাঙ্ক্ষী)\nMeaning: Having a strong desire to succeed.\nExample: He is very ambitious.",
    "Word: **Benevolent** (পরোপকারী)\nMeaning: Well meaning and kindly.\nExample: A benevolent smile.",
    "Word: **Candid** (মন খোলা / স্পষ্টবাদী)\nMeaning: Truthful and straightforward.\nExample: To be candid, I don't like it.",
    "Word: **Diligent** (পরিশ্রমী)\nMeaning: Showing care in one's work.\nExample: A diligent student.",
    "Word: **Enormous** (বিশাল)\nMeaning: Very large in size.\nExample: An enormous amount of money."
]

# --- ফাংশন সেকশন ---

def get_prayer_times():
    """নামাজের সময় আনে"""
    try:
        url = "http://api.aladhan.com/v1/timingsByCity?city=Dhaka&country=Bangladesh&method=1"
        response = requests.get(url).json()
        return response['data']['timings']
    except:
        return None

def get_latest_news():
    """প্রথম আলোর সর্বশেষ খবর নিয়ে আসবে"""
    try:
        # প্রথম আলোর RSS Feed (Technology বা Bangladesh সেকশন)
        feed_url = "https://www.prothomalo.com/feed/" 
        feed = feedparser.parse(feed_url)
        
        if feed.entries:
            # সবচেয়ে লেটেস্ট খবরটি নিবে
            latest_news = feed.entries[0]
            title = latest_news.title
            link = latest_news.link
            return f"📰 **সদ্য সংবাদ:**\n{title}\n\nবিস্তারিত: {link}"
        return None
    except Exception as e:
        print(f"News Error: {e}")
        return None

def run_task():
    try:
        print("--- Bot Started ---")
        
        # ১. আগের মেসেজ ডিলিট করা
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r") as f:
                last_msg_id = f.read().strip()
                if last_msg_id:
                    try:
                        bot.delete_message(CHANNEL_ID, int(last_msg_id))
                    except:
                        pass # ডিলিট না হলে সমস্যা নেই
        
        # ২. সময় চেক করা
        now = datetime.now(bd_timezone)
        current_hour = now.hour
        
        prayer_times = get_prayer_times()
        message_to_send = ""
        priority_found = False # নামাজ পেলে অন্য কিছু পাঠাবো না
        
        # ৩. নামাজের লজিক
        prayer_map = {'Fajr': 'ফজর', 'Dhuhr': 'জোহর', 'Asr': 'আছর', 'Maghrib': 'মাগরিব', 'Isha': 'এশা'}
        if prayer_times:
            for waqt_en, time_str in prayer_times.items():
                if waqt_en in prayer_map:
                    p_hour, p_minute = map(int, time_str.split(':'))
                    prayer_dt = now.replace(hour=p_hour, minute=p_minute, second=0, microsecond=0)
                    time_diff = abs((now - prayer_dt).total_seconds())
                    
                    if time_diff <= 900: # ১৫ মিনিটের রেঞ্জ (আগে/পরে)
                        waqt_bn = prayer_map[waqt_en]
                        message_to_send = f"🕌 {waqt_bn} এর ওয়াক্ত চলছে। নামাজে যান।"
                        priority_found = True
                        break

        # ৪. যদি নামাজ না থাকে, তবে নিউজ, পড়ালেখা বা সাধারণ মেসেজ সিলেক্ট করা
        if not priority_found:
            # লটারি করা হবে কি পাঠাবো (Random Logic)
            # ১ থেকে ১০ এর মধ্যে সংখ্যা নিব
            dice = random.randint(1, 10)
            
            if 6 <= current_hour < 23: # দিনের বেলা
                if dice <= 3: 
                    # ৩০% চান্স: নিউজ পাঠাবে
                    news = get_latest_news()
                    if news:
                        message_to_send = news
                    else:
                        message_to_send = random.choice(day_messages)
                elif dice <= 6:
                    # ৩০% চান্স: পড়ালেখার শব্দ (Vocab) পাঠাবে
                    message_to_send = f"📚 **Word of the moment:**\n\n{random.choice(vocab_list)}"
                else:
                    # ৪০% চান্স: সাধারণ আড্ডা
                    message_to_send = random.choice(day_messages)
            else:
                # রাতের বেলা শুধু ঘুমের মেসেজ
                message_to_send = random.choice(night_messages)

        # ৫. মেসেজ পাঠানো
        print(f"Sending: {message_to_send}")
        # Markdown সাপোর্ট অন করা হলো যাতে বোল্ড টেক্সট সুন্দর দেখায়
        msg = bot.send_message(CHANNEL_ID, message_to_send, parse_mode="Markdown")
        
        # ৬. ডাটা সেভ এবং গিট পুশ
        with open(DATA_FILE, "w") as f:
            f.write(str(msg.message_id))
            
        subprocess.run(["git", "config", "--global", "user.email", "bot@github.com"])
        subprocess.run(["git", "config", "--global", "user.name", "TeleBot"])
        subprocess.run(["git", "add", DATA_FILE])
        subprocess.run(["git", "commit", "-m", "Update ID"])
        subprocess.run(["git", "push"])
        print("Done!")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    run_task()
