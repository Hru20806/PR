import webbrowser
try:
    import pyautogui as ui
except ImportError:
    ui = None
import time

def play_music_on_spotify(song_name):
    if not ui:
        print("Cannot play on Spotify: pyautogui not available.")
        return
    webbrowser.open("https://open.spotify.com/")
    time.sleep(6)
    ui.hotkey("ctrl","shift","l")
    time.sleep(1)
    ui.write(song_name)
    time.sleep(3)
    ui.leftClick(805,515)
