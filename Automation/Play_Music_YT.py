try:
    import pywhatkit as pw
except ImportError:
    pw = None

def play_music_on_youtube(Song_name):
    if pw:
        pw.playonyt(Song_name)
    else:
        print(f"Cannot play {Song_name}: pywhatkit not installed.")
