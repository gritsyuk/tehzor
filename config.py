import os
from dotenv import load_dotenv

load_dotenv() 
API_KEY = os.getenv('API_KEY')
USER_ID = "638d7cdfc0ea064d706506cd"

PROXIES = {
    "http": "http://192.168.141.2:26280",
    "https": "http://192.168.141.2:26280"
    } 
