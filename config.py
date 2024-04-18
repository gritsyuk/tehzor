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
    "indy_eng_network": "64c77b3346c4793df13332ad",
    "indy_underground": "64c3c22a46c4793df17c59a0",
    "indy_A": "64c0fd7f46c4793df12b14b4",
    "indy_B": "64c0fdb346c4793df12b1a2a",
    "indy_C": "64c0fdfe46c4793df12beead",
    "indy_safety": "64e35797d6f89cdc4ce1249f",
    "signal_uderground": "65fad64beb908e0264317b76",
    "signal_safety": "65fad67feb908e026432e57f",
    "signal_parking": "661e69e7ec7825c89c93a8dd",
    "signal_s1": "661e67755d3aea11afb7af2f",
    "signal_s2": "661e67e8ec7825c89c8fc524",
    "signal_s3": "661e680b55d784a5083b884c",
    "signal_s4": "661e682dec7825c89c905d35",
    "signal_s5": "661e6851ec7825c89c90b59e",
    "signal_s6": "661e68dbec7825c89c91143f",
    "signal_s7": "661e69b055d784a5084c34d2",
}