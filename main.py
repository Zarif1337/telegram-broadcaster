import os
import random
import requests
import telebot
from datetime import datetime
import pytz

# --- Setup ---
TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHANNEL_ID = "@Zarifbots" 
bot = telebot.TeleBot(TOKEN)

def get_namaz_times():
    # Grabs today's prayer times for Rajshahi, Bangladesh
    url = "http://api.aladhan.com/v1/timingsByCity?city=Rajshahi&country=Bangladesh&method=1"
    response = requests.get(url).json()
    return response['data']['timings']

def clean_up_last_message():
    # Reads the last message ID and deletes it to keep the main content clean
    try:
        with open("last_id.txt", "r") as file:
            last_id = file.read().strip()
            if last_id:
                bot.delete_message(CHANNEL_ID, int(last_id))
    except Exception:
        pass # If there's no file or no message exists yet, silently skip

def save_new_message_id(message_id):
    # Saves the new message ID so it can be deleted on the next run
    with open("last_id.txt", "w") as file:
        file.write(str(message_id))

def main():
    # Set timezone to Bangladesh
    bd_tz = pytz.timezone('Asia/Dhaka')
    now = datetime.now(bd_tz)
    
    timings = get_namaz_times()
    upcoming_namaz = None
    
    # Loop through the main prayers to see if any are happening in the next 60 minutes
    for prayer in ['Fajr', 'Dhuhr', 'Asr', 'Maghrib', 'Isha']:
        prayer_time_str = timings[prayer]
        prayer_time = datetime.strptime(prayer_time_str, "%H:%M").time()
        prayer_dt = datetime.combine(now.date(), prayer_time)
        prayer_dt = bd_tz.localize(prayer_dt)
        
        minutes_difference = (prayer_dt - now).total_seconds() / 60
        
        if 0 <= minutes_difference <= 60:
            upcoming_namaz = prayer
            break
            
    # Decide what short message to broadcast (Max 3 sentences)
    if upcoming_namaz:
        text = f"Time for {upcoming_namaz} Namaz is near. Get ready! 🕌"
    else:
        chitchat_lines = [
            "Who's active right now? Drop a react! 🔥",
            "Hope everyone is having a great day! 👇",
            "Just checking in. Keep up the good work! 🚀"
        ]
        text = random.choice(chitchat_lines)

    # Step 1: Delete the old message
    clean_up_last_message()
    
    # Step 2: Send the new short message
    sent_message = bot.send_message(CHANNEL_ID, text)
    
    # Step 3: Save the new message ID for next time
    save_new_message_id(sent_message.message_id)

if __name__ == "__main__":
    main()
