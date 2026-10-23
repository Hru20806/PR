"""
Brain/intent_classifier.py
──────────────────────────
SmartIntentClassifier — fast, offline intent detection using regex.

Sits BEFORE the LLM fallback in the priority chain.
Returns the same JSON schema as brain.py:
    {intent, action, message, data}

Speed target: < 5 ms per call (pure Python regex, no I/O).
"""

import re
from typing import Optional

# ═════════════════════════════════════════════════════════════════════
#  STEP 3.1 — INTENT_PATTERNS
#
#  Structure:
#    {
#      "intent_name": [
#          (compiled_regex, action_string, message_template),
#          ...  ← multiple patterns per intent, tried top-to-bottom
#      ]
#    }
#
#  Named capture groups in regex → land directly in result["data"].
#  Message templates use {group_name} placeholders filled at runtime.
# ═════════════════════════════════════════════════════════════════════

INTENT_PATTERNS: dict[str, list[tuple]] = {

    # ── open_app ─────────────────────────────────────────────────────
    # Matches: "open chrome", "launch spotify", "start notepad"
    "open_app": [
        (
            re.compile(
                r"^(?:open|launch|start|run|fire up)\s+(?:the\s+)?(?P<app>[a-z0-9 _\-\.]+?)(?:\s+app(?:lication)?)?$",
                re.I
            ),
            "open_{app}",
            "Opening {app}, sir."
        ),
    ],

    # ── close_app ────────────────────────────────────────────────────
    # Matches: "close chrome", "kill spotify", "exit notepad"
    "close_app": [
        (
            re.compile(
                r"^(?:close|kill|exit|quit|terminate|shut\s+down)\s+(?:the\s+)?(?P<app>[a-z0-9 _\-\.]+?)(?:\s+app(?:lication)?)?$",
                re.I
            ),
            "close_{app}",
            "Closing {app}. Goodbye to that window, sir."
        ),
    ],

    # ── play_music ───────────────────────────────────────────────────
    # Matches: "play believer on spotify", "play shape of you", "play album divide"
    "play_music": [
        # With explicit platform: "play believer on spotify"
        (
            re.compile(
                r"^play\s+(?P<song>.+?)\s+on\s+(?P<platform>spotify|youtube|music|amazon\s+music)$",
                re.I
            ),
            "play_music",
            "Playing {song} on {platform}, right away."
        ),
        # Album: "play album divide"
        (
            re.compile(
                r"^play\s+album\s+(?P<song>.+)$",
                re.I
            ),
            "play_album",
            "Queuing up the album {song}, sir."
        ),
        # Generic: "play believer"
        (
            re.compile(
                r"^play\s+(?P<song>[a-z0-9 _'\-,\.&]+)$",
                re.I
            ),
            "play_music",
            "Playing {song}."
        ),
    ],

    # ── web_search ───────────────────────────────────────────────────
    # Matches: "search for black holes", "google elon musk",
    #          "look up python tutorials", "find me best pizza"
    "web_search": [
        (
            re.compile(
                r"^(?:search(?:\s+for)?|google|look\s+up|find(?:\s+me)?|browse(?:\s+for)?)\s+(?P<query>.+)$",
                re.I
            ),
            "web_search",
            "Searching for {query}."
        ),
        # "what is X" / "who is X" / "how does X work"
        (
            re.compile(
                r"^(?:what|who|where|when|why|how)\s+(?:is|are|was|were|does|do|did|can)\s+(?P<query>.+)\??$",
                re.I
            ),
            "web_search",
            "Let me look that up: {query}."
        ),
    ],

    # ── system_vol ───────────────────────────────────────────────────
    # Matches: "volume up", "increase volume", "mute", "unmute"
    "system_vol": [
        (
            re.compile(
                r"^(?:volume\s+up|increase\s+(?:the\s+)?volume|louder|turn\s+(?:it\s+)?up)$",
                re.I
            ),
            "volume_up",
            "Turning it up, sir."
        ),
        (
            re.compile(
                r"^(?:volume\s+down|decrease\s+(?:the\s+)?volume|quieter|lower\s+(?:the\s+)?volume|turn\s+(?:it\s+)?down)$",
                re.I
            ),
            "volume_down",
            "Dialing it back, sir."
        ),
        (
            re.compile(r"^(?:mute|silence|quiet)$", re.I),
            "mute",
            "Muted. Peace and quiet, sir."
        ),
        (
            re.compile(r"^(?:unmute|restore\s+sound|sound\s+on)$", re.I),
            "unmute",
            "Unmuted. Welcome back to the noise."
        ),
    ],

    # ── weather ──────────────────────────────────────────────────────
    # Matches: "weather in London", "what is the weather", "weather today"
    "weather": [
        (
            re.compile(
                r"^(?:what(?:'s|\s+is)?\s+(?:the\s+)?)?weather(?:\s+in\s+(?P<city>[a-z\s]+?))?(?:\s+(?:today|now|currently|forecast))?$",
                re.I
            ),
            "get_weather",
            "Fetching weather{city_str}."   # city_str built at runtime
        ),
    ],

    # ── notes ────────────────────────────────────────────────────────
    # Matches: "take a note", "start notes", "open notes mode"
    "notes": [
        (
            re.compile(
                r"^(?:take\s+(?:a\s+)?note|start\s+(?:taking\s+)?notes?|open\s+notes?(?:\s+mode)?|notes?\s+mode)$",
                re.I
            ),
            "start_notes",
            "Notes mode activated, sir. I'm listening."
        ),
        (
            re.compile(
                r"^(?:stop\s+(?:taking\s+)?notes?|end\s+notes?\s+mode|notes?\s+off)$",
                re.I
            ),
            "stop_notes",
            "Notes mode deactivated."
        ),
    ],

    # ── reset_memory ─────────────────────────────────────────────────
    # Matches: "forget everything", "reset memory", "clear chat"
    "reset_memory": [
        (
            re.compile(
                r"^(?:forget\s+everything|reset\s+(?:my\s+)?(?:memory|chat|conversation)|clear\s+(?:chat|memory|history|context))$",
                re.I
            ),
            "reset_memory",
            "Memory cleared. Wiped clean, like it never happened."
        ),
    ],

    # ── screenshot ───────────────────────────────────────────────────
    # Matches: "take a screenshot", "capture screen"
    "screenshot": [
        (
            re.compile(
                r"^(?:take\s+(?:a\s+)?screenshot|capture\s+(?:the\s+)?screen|screenshot)$",
                re.I
            ),
            "take_screenshot",
            "Screenshot taken, sir."
        ),
    ],

    # ── system_control ───────────────────────────────────────────────
    # Matches: "shutdown", "restart", "lock screen", "sleep"
    "system_control": [
        (
            re.compile(r"^(?:shut\s*down|power\s+off)(?:\s+(?:the\s+)?(?:computer|pc|system))?$", re.I),
            "system_shutdown",
            "Initiating shutdown sequence. Goodnight, sir."
        ),
        (
            re.compile(r"^(?:restart|reboot)(?:\s+(?:the\s+)?(?:computer|pc|system))?$", re.I),
            "system_restart",
            "Rebooting. Back in a moment."
        ),
        (
            re.compile(r"^(?:lock|lock\s+(?:the\s+)?(?:screen|computer|pc))$", re.I),
            "lock_screen",
            "Locking the screen, sir."
        ),
        (
            re.compile(r"^(?:sleep|hibernate|suspend)(?:\s+mode)?$", re.I),
            "system_sleep",
            "Putting the system to sleep. Sweet dreams."
        ),
    ],
}


# ═════════════════════════════════════════════════════════════════════
#  STEP 3.2 — SmartIntentClassifier
# ═════════════════════════════════════════════════════════════════════

class SmartIntentClassifier:
    """
    Pure-Python, offline intent classifier using regex pattern matching.

    No API calls. No model loading. Runs in < 5 ms on any hardware.

    Iterates through INTENT_PATTERNS in definition order.
    First match wins and is returned immediately.

    Return schema (identical to brain.py / JarvisBrain):
        {
            "intent":  str,    # matched intent name or "unknown"
            "action":  str,    # action key with named groups filled in
            "message": str,    # human-readable reply with groups filled in
            "data":    dict    # all named capture groups from the regex
        }
    """

    def __init__(self):
        # Log the number of patterns loaded so we can track growth
        total = sum(len(v) for v in INTENT_PATTERNS.values())
        print(f"[CLASSIFIER] SmartIntentClassifier ready — {total} patterns across {len(INTENT_PATTERNS)} intents.")

    # ── Primary method ────────────────────────────────────────────────
    def classify(self, text: str) -> dict:
        """
        Classify a command string against all INTENT_PATTERNS.

        Args:
            text : raw command string (wake word already stripped)

        Returns:
            Result dict with keys: intent, action, message, data.
            Returns 'unknown' intent if no pattern matches.
        """
        cleaned = text.strip().lower()

        for intent_name, pattern_list in INTENT_PATTERNS.items():
            for (regex, action_template, message_template) in pattern_list:

                match = regex.match(cleaned)
                if not match:
                    continue

                # ── Match found ──────────────────────────────────────

                # Extract all named capture groups (e.g. {app}, {song})
                groups: dict = match.groupdict()

                # Clean up captured values: strip whitespace, title-case for display
                data: dict = {
                    k: v.strip() if v else ""
                    for k, v in groups.items()
                }

                # Fill action template (e.g. "open_{app}" → "open_chrome")
                action = self._fill_template(action_template, data)

                # Fill message template, with special handling for optional groups
                message = self._build_message(message_template, data)

                result = {
                    "intent":  intent_name,
                    "action":  action,
                    "message": message,
                    "data":    data,
                }

                print(f"[CLASSIFIER] ✓ Intent '{intent_name}' matched — action: '{action}' | data: {data}")
                return result

        # ── No match ─────────────────────────────────────────────────
        print(f"[CLASSIFIER] ✗ No pattern matched for: '{text}'")
        return {
            "intent":  "unknown",
            "action":  None,
            "message": "",   # empty = caller falls through to LLM
            "data":    {}
        }

    # ── Convenience predicate ─────────────────────────────────────────
    def is_known(self, text: str) -> bool:
        """
        Quick check: does any pattern match this text?

        Returns:
            True  → at least one intent matched (skip LLM)
            False → no match, must fall through to LLM
        """
        return self.classify(text)["intent"] != "unknown"

    # ── Private helpers ───────────────────────────────────────────────
    @staticmethod
    def _fill_template(template: str, data: dict) -> str:
        """
        Replace {group_name} placeholders in action/message templates.
        Strips spaces and lowercases values for action strings.

        Example: "open_{app}" + {app: "google chrome"} → "open_google_chrome"
        """
        result = template
        for key, value in data.items():
            placeholder = "{" + key + "}"
            if placeholder in result:
                # Action strings: lowercase + underscores
                safe_val = value.strip().lower().replace(" ", "_")
                result = result.replace(placeholder, safe_val)
        return result

    @staticmethod
    def _build_message(template: str, data: dict) -> str:
        """
        Replace {group_name} and special computed placeholders
        (like {city_str}) in the human-readable message template.

        Example: "Playing {song} on {platform}." + {song:'Believer', platform:'Spotify'}
                 → "Playing Believer on Spotify."
        """
        result = template

        # Special computed placeholder: {city_str}
        # e.g. weather intent → "Fetching weather in London." vs "Fetching weather."
        if "{city_str}" in result:
            city = data.get("city", "").strip()
            city_str = f" in {city.title()}" if city else ""
            result = result.replace("{city_str}", city_str)

        # Standard group replacements — title-case for natural speech
        for key, value in data.items():
            placeholder = "{" + key + "}"
            if placeholder in result:
                result = result.replace(placeholder, value.strip().title())

        return result


# ── Module-level singleton (import-and-go) ────────────────────────────
# co_brain.py imports this directly:
#   from Brain.intent_classifier import classifier
classifier = SmartIntentClassifier()
