from Brain.personality import jarvis_speak
from os import getcwd
import threading

# New Safe Tools
from Tools.permissions import check_safety
from Tools.app_launcher import open_app
from Tools.browser_tools import open_website, search_google as tool_search_google
from Tools.system_control import close_window, type_text, press_key, take_screenshot

# Existing Automations (Preserving complex music/battery logic)
from Automation.Play_Music_YT import play_music_on_youtube
from Automation.playmusic_Sfy import play_music_on_spotify
from Automation.Battery import check_percentage
from Automation.tab_automation import perform_browser_action
from Automation.Youtube_play_back import perform_media_action
from Automation.scrool_system import perform_scroll_action

import os

def clear_file():
    with open(os.path.join(getcwd(), "input.txt"), "w") as file:
        file.truncate(0)

def Open_Brain(text):
    text = text.lower()
    if "website" in text or "open website named" in text:
        target = text.replace("open", "").replace("website named", "").replace("website", "").strip()
        open_website(target)
    else:
        target = text.replace("open", "").replace("app", "").strip()
        
        # New pattern: Action first, then speak result
        success, message = open_app(target)
        
        # Determine mood based on success
        mood = "success" if success else "warning"
        
        # Speak the result
        jarvis_speak(message, mood=mood)

def Auto_main_brain(text):
    try:
        # 1. Permission Check
        is_safe, reason = check_safety(text)
        if not is_safe:
            jarvis_speak(reason, mood="warning")
            return

        formatted_text = text.lower()

        # 2. Intent Routing
        if formatted_text.startswith("open"):
            Open_Brain(formatted_text)
            
        elif "close window" in formatted_text or "close app" in formatted_text:
            close_window()
            
        elif "screenshot" in formatted_text:
            take_screenshot()

        # Music Handlers (Existing logic preserved)
        elif "play music on youtube" in formatted_text:
            jarvis_speak("Which song shall I play?", mood="neutral")
            clear_file()
            previous_text = ""
            while True:
                with open("input.txt","r") as file:
                    current_text = file.read().lower()
                if current_text != previous_text:
                    previous_text = current_text
                    if previous_text.endswith("song"):
                        play_music_on_youtube(previous_text)
                        break

        elif "play music on spotify" in formatted_text:
            jarvis_speak("Which track would you like?", mood="neutral")
            clear_file()
            previous_text = ""
            while True:
                with open("input.txt", "r") as file:
                    current_text = file.read().lower()
                if current_text != previous_text:
                    previous_text = current_text
                    if previous_text.endswith("song"):
                        play_music_on_spotify(previous_text)
                        break

        elif "check battery" in formatted_text:
            check_percentage()

        # Search Handlers
        elif "search google for" in formatted_text:
            query = formatted_text.replace("search google for", "").strip()
            tool_search_google(query)
            
        elif "type" in formatted_text and "enter" not in formatted_text: # Simple typing
            content = formatted_text.replace("type", "").strip()
            type_text(content)
            
        elif "press" in formatted_text:
            key = formatted_text.replace("press", "").strip()
            press_key(key)

        # Fallback to existing browser/media/scroll actions
        else:
            perform_browser_action(formatted_text)
            perform_media_action(formatted_text)
            perform_scroll_action(formatted_text)

    except Exception as e:
        print(f"Error in Auto_main_brain: {e}")
        jarvis_speak("I encountered a system error while processing that request.", mood="error")