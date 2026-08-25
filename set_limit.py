import sys
sys.path.insert(0, "/root/oxycode-bot")
from dotenv import load_dotenv
load_dotenv("/root/oxycode-bot/.env")
import database
database.set_setting("daily_limit", "20")
print("daily_limit now:", database.get_daily_limit())
