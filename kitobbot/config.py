import os 
from dotenv import load_dotenv


load_dotenv()


BOT_TOKEN = os.getenv("8844291531:AAE0sW7FNR0BQIqcrSBGTlSYEKSn4LlkAXk",  "YOUR_BOT_TOKEN_HERE")


ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS","8165780688"). split(",")]


CHANNEL_ID = os.getenv("CHANNEL_ID", "@your_channel")
CHANNEL_REQUIRED = False



POINTS = {
    "reding_per_minute" : 1,
    "test_perfect" : 100,
    "test_passed" : 50,
    "certificate" : 150,
    "daily_login" : 10,
    "streak_bonus" : 5,
}



POMODORO = {
    "work_time" : 25,
    "short_break" : 5,
    "long_break" : 15,
    "sessions_before_long" : 4,
}


DATA_DIR = "data"
BOOKS_DIR = f"{DATA_DIR}/books"
AUDIO_DIR = f"{DATA_DIR}/audio"
CERTS_DIR = f"{DATA_DIR}/certificates"


TEST_PASS_SCORE = 7


ITEMS_PER_PAGE = 5