from TextToSpeech.tts_engine import speak

def jarvis_speak(text: str, mood: str = "neutral"):
    """
    Centralized Personality Layer for Jarvis.
    Wraps all speech output to ensure a consistent, professional, Iron-Man-like persona.
    
    Args:
        text (str): The raw message to speak.
        mood (str): Context of the message ('neutral', 'success', 'warning', 'error').
    """
    if not text:
        return

    # 1. Clean and normalize the text
    # Remove excessive whitespace and common redundant phrases if strictly enforcing style
    clean_text = text.strip()
    if not clean_text:
        return
        
    # Ensure capitalization
    clean_text = clean_text[0].upper() + clean_text[1:]

    # 2. Apply Mood Modifiers
    prefix = ""
    suffix = ""

    if mood == "error":
        # Professional error handling
        if not clean_text.lower().startswith("i"):
            prefix = "I am unable to complete that request. "
    elif mood == "warning":
        prefix = "Alert. "
    elif mood == "success":
        # Concise confirmation
        if not clean_text.lower().startswith("done"):
             pass
    
    # 3. Apply Persona (The "Jarvis" signature)
    # Iron Man's Jarvis uses "Sir" frequently but naturally.
    # Avoid adding it if it's already there or if it's a question.
    lower_text = clean_text.lower()
    if "sir" not in lower_text:
        # Don't add 'sir' to short prompts or specific questions usually
        if lower_text.endswith("?") or lower_text.endswith("sir."):
            pass
        else:
            suffix = ", sir"

    # 4. Construct Final Output
    # Handle punctuation for natural pauses
    final_output = f"{prefix}{clean_text}{suffix}"
    
    # Send to the TTS engine
    speak(final_output)
