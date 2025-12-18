import time
import re

def get_current_time_millis():
    return int(time.time() * 1000)

def extract_temperature(data):
    colon_pos = data.find(':')
    return data[colon_pos + 1:].strip() if colon_pos != -1 else None

def extract_rftemperature(data):
    match = re.search(r"RFTEMPERATURE:\s*(\d+\.\d+)", data)
    return f"RFTEMPERATURE: {match.group(1)}" if match else "RFTEMPERATURE data not found"