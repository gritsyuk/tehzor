import os
from dotenv import load_dotenv

load_dotenv() 
API_KEY = os.getenv('API_KEY')
USER_ID = "638d7cdfc0ea064d706506cd"

PROXIES = {
    "http": "http://192.168.141.2:26280",
    "https": "http://192.168.141.2:26280"
    } 

CONSTRUCTION = {
    "beside1_1_1": "64480db0944e713c0cd68d6d",
    "beside1_1_2": "64480e02944e713c0cd6a26d",
    "beside1_2_1": "64480fac944e713c0cd6d465",
    "beside1_2_2": "644813db944e713c0cd6f926",
    "mitino_k18_1": "641f0fe41ba6ce0024682d44",
    "mitino_k18_2": "641f10491ba6ce0024682f15",
    "mitino_k18_3": "641f10cd1ba6ce0024682fe3",
    "mitino_k18_4": "641f16caa3743a0025576bb6",
}