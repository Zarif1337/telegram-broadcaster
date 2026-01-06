import telebot
import time
import os

# We get the passwords from GitHub's safe "Secrets" locker
# (I will show you how to set this up in Step 3)
API_TOKEN = os.environ['MY_BOT_TOKEN']
CHANNEL_ID = os.environ['MY_CHANNEL_ID']

bot = telebot.TeleBot(API_TOKEN)

def run_task():
    try:
        # 1. Send Message
        print("Sending message...")
        msg = bot.send_message(CHANNEL_ID, "Hello! This is an automated broadcast.")
        
        # 2. Wait 5 Minutes (keep the script alive)
        print("Waiting 5 minutes...")
        time.sleep(300) 
        
        # 3. Delete Message
        print("Deleting message...")
        bot.delete_message(CHANNEL_ID, msg.message_id)
        print("Done!")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    run_task()
