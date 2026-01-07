import telebot
import os
import requests
import random
from datetime import datetime
import pytz
import subprocess # গিট কমান্ড চালানোর জন্য

# --- কনফিগারেশন ---
API_TOKEN = os.environ['MY_BOT_TOKEN']
CHANNEL_ID = os.environ['MY_CHANNEL_ID']

# বাংলাদেশ টাইমজোন
bd_timezone = pytz.timezone("Asia/Dhaka")

# মেসেজ লিস্ট
day_messages = [
    "হ্যালো বন্ধুরা, কি খবর?", "পড়াশোনা কেমন চলছে?", "এই অসময়ে অনলাইনে কি করো?",
    "মোবাইল রেখে একটু রেস্ট নাও।", "আজকের দিনটা প্রোডাক্টিভ ছিল তো?",
    "নামাজ পড়তে ভুলো না কিন্তু!", "ওপরের পোস্টে কি রিএক্ট দিয়েছো?"
]

night_messages = [
    "ঘুমিয়ে পড়, অনেক রাত হয়েছে।", "রাত জাগা শরীরের জন্য খারাপ।",
    "Vuuuuuuutttttt! 👻", "থাপ্পড় মারবো, ফোন রাখো!",
    "এখনো জাগনা কেন? কাল স্কুল/কলেজ/অফিস নেই?", "শুভ রাত্রি! ফোন দূরে রাখো।"
]

bot = telebot.TeleBot(API_TOKEN)
DATA_FILE = "last_id.txt"

def get_prayer_times():
    try:
        url = "http://api.aladhan.com/v1/timingsByCity?city=Dhaka&country=Bangladesh&method=1"
        response = requests.get(url).json()
        return response['data']['timings']
    except:
        return None

def run_task():
    try:
        print("--- Bot Started ---")
        
        # ১. আগের মেসেজ ডিলিট করা (যদি ফাইল থাকে)
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r") as f:
                last_msg_id = f.read().strip()
                if last_msg_id:
                    try:
                        print(f"Deleting old message ID: {last_msg_id}")
                        bot.delete_message(CHANNEL_ID, int(last_msg_id))
                    except Exception as e:
                        print(f"Could not delete old message: {e}")
        
        # ২. নতুন মেসেজ তৈরি করা
        now = datetime.now(bd_timezone)
        current_hour = now.hour
        current_time_str = now.strftime("%H:%M")
        
        prayer_times = get_prayer_times()
        message_to_send = ""
        prayer_found = False
        
        prayer_map = {'Fajr': 'ফজর', 'Dhuhr': 'জোহর', 'Asr': 'আছর', 'Maghrib': 'মাগরিব', 'Isha': 'এশা'}

        if prayer_times:
            for waqt_en, time_str in prayer_times.items():
                if waqt_en in prayer_map:
                    p_hour, p_minute = map(int, time_str.split(':'))
                    prayer_dt = now.replace(hour=p_hour, minute=p_minute, second=0, microsecond=0)
                    time_diff = abs((now - prayer_dt).total_seconds())
                    
                    # ৩০ মিনিটের রেঞ্জ (আগে বা পরে)
                    if time_diff <= 1800: 
                        waqt_bn = prayer_map[waqt_en]
                        message_to_send = f"🕌 {waqt_bn} এর ওয়াক্ত চলছে বা কাছাকাছি সময়। নামাজে যান।"
                        prayer_found = True
                        break

        if not prayer_found:
            if 6 <= current_hour < 23:
                message_to_send = random.choice(day_messages)
            else:
                message_to_send = random.choice(night_messages)

        # ৩. নতুন মেসেজ পাঠানো
        print(f"Sending: {message_to_send}")
        msg = bot.send_message(CHANNEL_ID, message_to_send)
        
        # ৪. নতুন ID ফাইলে সেভ করা
        with open(DATA_FILE, "w") as f:
            f.write(str(msg.message_id))
            
        # ৫. গিটহাবে আপডেট পুশ করা (Magic Part)
        print("Saving data to GitHub...")
        subprocess.run(["git", "config", "--global", "user.email", "bot@github.com"])
        subprocess.run(["git", "config", "--global", "user.name", "TeleBot"])
        subprocess.run(["git", "add", DATA_FILE])
        subprocess.run(["git", "commit", "-m", "Update message ID"])
        subprocess.run(["git", "push"])
        print("Done!")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    run_task()
