import time
from Brain.personality import jarvis_speak
import threading
from Alert import Alert
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.platform_loader import PlatformManager

platform_manager = PlatformManager()

def get_battery():
    if platform_manager.system:
        try:
            return platform_manager.system.get_battery_info()
        except Exception:
            return {"percent": 0, "power_plugged": False}
    return {"percent": 0, "power_plugged": False}

def battery_Alert():
    while True:
        time.sleep(3)
        battery = get_battery()
        percentage = int(battery.get("percent", 0))
        if percentage == 0:
            continue
            
        if percentage == 100:
            t1 = threading.Thread(target=Alert,args=("100%charge",))
            t2 = threading.Thread(target=jarvis_speak,args=("Battery fully charged. Please unplug the charger.", "success"))
            t1.start()
            t2.start()
            t1.join()
            t2.join()
        elif percentage <= 20:
            t1 = threading.Thread(target=Alert,args=("Battery Low",))
            t2 = threading.Thread(target=jarvis_speak,args=("Battery level is low.", "warning"))
            t1.start()
            t2.start()
            t1.join()
            t2.join()
        elif percentage <=10:
            t1 = threading.Thread(target=Alert,args=("Battery is too Low",))
            t2 = threading.Thread(target=jarvis_speak,args=("Battery level is critical.", "warning"))
            t1.start()
            t2.start()
            t1.join()
            t2.join()
        elif percentage <= 5:
            t1 = threading.Thread(target=Alert,args=("Battery is going to died",))
            t2 = threading.Thread(target=jarvis_speak,args=("System will shut down soon. Connect power immediately.", "error"))
            t1.start()
            t2.start()
            t1.join()
            t2.join()
        time.sleep(10)

def check_plug():
    print("_____started___")
    battery = get_battery()
    previous_state = battery.get("power_plugged", False)
    while True:
        time.sleep(1)
        battery = get_battery()
        if battery.get("power_plugged", False) != previous_state:
            if battery.get("power_plugged", False):
                t1 = threading.Thread(target=Alert,args=("Charging **STARTED**",))
                t2 = threading.Thread(target=jarvis_speak,args=("Charging started.", "success"))
                t1.start()
                t2.start()
                t1.join()
                t2.join()
            else:
                t1 = threading.Thread(target=Alert,args=("Charging **STOP**",))
                t2 = threading.Thread(target=jarvis_speak,args=("Charging stopped.", "warning"))
                t1.start()
                t2.start()
                t1.join()
                t2.join()
      
            previous_state = battery.get("power_plugged", False)

def check_percentage():
    battery = get_battery()
    percent = int(battery.get("percent", 0))
    if percent > 0:
        t1 = threading.Thread(target=Alert,args=(f"The device is running on {percent}% power",))
        t2 = threading.Thread(target=jarvis_speak,args=(f"Power level is at {percent}%.",))
        t1.start()
        t2.start()
        t1.join()
        t2.join()
    else:
        jarvis_speak("Battery information is currently unavailable.")
