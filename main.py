import telebot
import os
import requests
import random
import feedparser
import google.generativeai as genai
from datetime import datetime
import pytz
import subprocess

# --- ১. কনফিগারেশন ---
TELEGRAM_TOKEN = os.environ['MY_BOT_TOKEN']
CHANNEL_ID = os.environ['MY_CHANNEL_ID']
GEMINI_KEY = os.environ.get('GEMINI_API_KEY')
WEATHER_KEY = os.environ.get('WEATHER_API_KEY') # Optional

# --- ২. Gemini এর ব্রেইন সেটআপ (System Prompt) ---
genai.configure(api_key=GEMINI_KEY)

# এখানে আমরা বটের চরিত্র ঠিক করে দিচ্ছি
system_prompt = """
তুমি 'Bangladesh Teaching Hub' চ্যানেলের একজন স্মার্ট মেন্টর। 
তোমার অডিয়েন্স হলো এমন ছাত্ররা যারা টেকনোলজি সম্পর্কে খুব কম জানে (Beginner)।
তোমার কাজ হলো:
১. Linux, AI, Network, Android, Software নিয়ে একদম সহজ বাংলায় (Banglish style) ধারণা দেওয়া। উদাহরণসহ বোঝাবে।
২. মাঝে মাঝে ইসলামিক উক্তি বা মোটিভেশন দেওয়া।
৩. খুব কঠিন টেকনিক্যাল শব্দ ব্যবহার করবে না। করলেও সেটা বুঝিয়ে বলবে।
৪. টোন হবে বন্ধুত্বপূর্ণ এবং উৎসাহজনক। ইমোজি ব্যবহার করবে।
"""

generation_config = {
  "temperature": 1.0, # ক্রিয়েটিভিটি হাই রাখা হলো
  "top_p": 0.95,
  "max_output_tokens": 1024,
}

model = genai.GenerativeModel(
  model_name="gemini-3-flash-preview",
  generation_config=generation_config,
  system_instruction=system_prompt
)

# --- ৩. ভেরিয়েবল এবং টাইমজোন ---
DATA_FILE = "last_id.txt"
bd_timezone = pytz.timezone("Asia/Dhaka")
bot = telebot.TeleBot(TELEGRAM_TOKEN)

# --- ৪. হেল্পার ফাংশন ---

def ask_gemini(prompt):
    """Gemini কে প্রশ্ন করার ফাংশন"""
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"Gemini Error: {e}")
        return None

def get_prayer_times():
    """নামাজের সময় চেক করা"""
    try:
        url = "http://api.aladhan.com/v1/timingsByCity?city=Dhaka&country=Bangladesh&method=1"
        res = requests.get(url).json()
        return res['data']['timings']
    except:
        return None

def get_latest_news():
    """খবর আনা"""
    try:
        # টেকনোলজি নিউজ পেলে ভালো, না পেলে সাধারণ খবর
        feed = feedparser.parse("https://www.prothomalo.com/feed/")
        if feed.entries:
            return feed.entries[0].title, feed.entries[0].link
        return None, None
    except:
        return None, None

def get_weather():
    """আবহাওয়া আনা"""
    if not WEATHER_KEY: return None
    try:
        url = f"http://api.openweathermap.org/data/2.5/weather?q=Dhaka&appid={WEATHER_KEY}&units=metric"
        data = requests.get(url).json()
        return f"Dhaka: {data['main']['temp']}°C, {data['weather'][0]['description']}"
    except:
        return None

# --- ৫. মেইন লজিক (Run Task) ---

def run_task():
    try:
        print("--- Bot Started ---")
        
        # A. আগের মেসেজ ডিলিট করা
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r") as f:
                last_msg_id = f.read().strip()
                if last_msg_id:
                    try:
                        bot.delete_message(CHANNEL_ID, int(last_msg_id))
                        print("Deleted old message.")
                    except:
                        pass

        # B. সময় চেক
        now = datetime.now(bd_timezone)
        current_hour = now.hour
        final_message = ""
        priority_task = False

        # C. নামাজের লজিক (Priority 1)
        prayer_times = get_prayer_times()
        prayer_map = {'Fajr': 'ফজর', 'Dhuhr': 'জোহর', 'Asr': 'আছর', 'Maghrib': 'মাগরিব', 'Isha': 'এশা'}
        
        if prayer_times:
            for waqt_en, time_str in prayer_times.items():
                if waqt_en in prayer_map:
                    p_hour, p_minute = map(int, time_str.split(':'))
                    prayer_dt = now.replace(hour=p_hour, minute=p_minute, second=0, microsecond=0)
                    
                    # ১০ মিনিটের রেঞ্জ
                    if abs((now - prayer_dt).total_seconds()) <= 600:
                        waqt_bn = prayer_map[waqt_en]
                        prompt = f"এখন {waqt_bn} নামাজের সময়। ছাত্রদের টেকনোলজি বা দুনিয়াবি কাজ রেখে নামাজে যাওয়ার জন্য সুন্দর করে একটা ইসলামিক রিমাইন্ডার দাও।"
                        final_message = ask_gemini(prompt)
                        priority_task = True
                        break

        # D. জেনারেল লজিক (যদি নামাজ না থাকে)
        if not priority_task:
            
            # রাত ১২টা - ভোর ৬টা: ঘুম
            if 0 <= current_hour < 6:
                prompt = "এখন অনেক রাত। ছাত্রদের বলো পিসি/মোবাইল বন্ধ করে ঘুমাতে। রাত জাগলে ব্রেইনের ক্ষতি হয়, সেটা টেকনিক্যালি এবং মজার ছলে বলো।"
                final_message = ask_gemini(prompt)

            # দিনের বেলা: Tech Mix
            else:
                dice = random.randint(1, 100)
                
                if dice <= 40: 
                    # --- ৪০% চান্স: Tech Lesson (Beginner) ---
                    # আমরা বিষয়গুলো ঘুরিয়ে ফিরিয়ে আনবো
                    topics = ["Linux Distro (Mint/Ubuntu)", "What is IP Address", "RAM vs SSD", "Open Source Software", "VPN use", "Safe Browsing", "Android Rooting basics", "AI Tools"]
                    topic = random.choice(topics)
                    
                    prompt = f"Topic: {topic}। এই বিষয়টি সম্পর্কে এমনভাবে ১-২ লাইনে বোঝাও যেন একজন ক্লাস এইটের ছাত্রও বোঝে। কেন এটা কাজের, সেটা বলো।"
                    final_message = ask_gemini(prompt)

                elif dice <= 60:
                    # --- ২০% চান্স: Software/App Review ---
                    prompt = "ছাত্রদের পড়াশোনা বা প্রোডাক্টিভিটির জন্য একটি ফ্রি অ্যান্ড্রয়েড অ্যাপ বা পিসি সফটওয়্যার সাজেস্ট করো। কেন এটা সেরা তা ১ লাইনে বলো।"
                    final_message = ask_gemini(prompt)

                elif dice <= 80:
                    # --- ২০% চান্স: Islamic / Motivation ---
                    prompt = "ছাত্রদের হতাশা কাটানোর জন্য একটি ছোট ইসলামিক উক্তি বা মোটিভেশনাল কথা বলো।"
                    final_message = ask_gemini(prompt)

                elif dice <= 90:
                    # --- ১০% চান্স: Tech News ---
                    title, link = get_latest_news()
                    if title:
                        prompt = f"নিউজ: '{title}'। এটাকে টেকনোলজির সাথে মিলিয়ে বা সাধারণ জ্ঞানের অংশ হিসেবে ২ লাইনে শেয়ার করো। লিংক: {link}"
                        final_message = ask_gemini(prompt)
                    else:
                        final_message = ask_gemini("আজকের দিনের একটি টেক ফ্যাক্ট (Tech Fact) বলো।")
                
                else:
                    # --- ১০% চান্স: Weather / Chat ---
                    w_data = get_weather()
                    if w_data:
                        prompt = f"আবহাওয়া: {w_data}। আবহাওয়া অনুযায়ী ছাত্রদের একটা পরামর্শ দাও (যেমন ল্যাপটপ গরম হওয়া বা বাইরে যাওয়া নিয়ে)।"
                        final_message = ask_gemini(prompt)
                    else:
                        final_message = ask_gemini("ছাত্রদের জিজ্ঞেস করো তারা লিনাক্স ট্রাই করেছে কিনা বা উইন্ডোজেই পড়ে আছে?")

        # E. মেসেজ পাঠানো ও সেভ করা (Robust Git Push)
        if final_message:
            # Markdown এড়াচ্ছি যাতে ফরম্যাটিং এরর না হয়, তবে জেমিনি সুন্দর টেক্সট দিবে
            print(f"Sending: {final_message[:50]}...")
            sent_msg = bot.send_message(CHANNEL_ID, final_message)
            
            with open(DATA_FILE, "w") as f:
                f.write(str(sent_msg.message_id))
            
            # Git Commands (Pull -> Commit -> Push)
            subprocess.run(["git", "config", "--global", "user.email", "bot@github.com"])
            subprocess.run(["git", "config", "--global", "user.name", "TeleBot"])
            subprocess.run(["git", "pull"]) 
            subprocess.run(["git", "add", DATA_FILE])
            subprocess.run(["git", "commit", "-m", "Update ID"])
            subprocess.run(["git", "push"])
            print("Done!")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    run_task()
