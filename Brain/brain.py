import requests
import json
import time

# ─────────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────────
OLLAMA_URL  = "http://localhost:11434/api/chat"   # /api/chat → multi-turn
MODEL_NAME  = "gemma:2b"
MAX_HISTORY = 10   # Keep last N user+assistant turn pairs (20 messages total)

# ─────────────────────────────────────────────
#  SYSTEM PROMPT
#  Forces strict JSON output and gives Jarvis
#  its Tony-Stark-AI personality.
# ─────────────────────────────────────────────
SYSTEM_PROMPT = """
You are J.A.R.V.I.S — Just A Rather Very Intelligent System.
You assist your creator with wit, precision, and zero tolerance for nonsense.
Think: Friday meets Tony Stark's dry humour. Confident. Sharp. Occasionally smug.

STRICT OUTPUT RULE — you must ALWAYS respond with valid JSON and nothing else.
No markdown. No code fences. No explanations outside the JSON.

Required JSON schema:
{
  "intent":  "<intent_type>",
  "action":  "<system_action or null>",
  "message": "<your natural language reply to the user>",
  "data":    {}
}

Valid intent values:
  - "conversation"   → general chat, no system action needed
  - "open_app"       → user wants to open an application
  - "close_app"      → user wants to close an application
  - "play_music"     → user wants music played
  - "system_control" → brightness, volume, shutdown, etc.
  - "tool_call"      → any other tool/automation command
  - "error"          → something went wrong

Rules:
  - "action" is null when no system action is needed.
  - "data" holds extra fields (e.g. song name, app name, URL).
  - Keep "message" concise, witty, and in character.
  - Never break the JSON schema.

Example — user says "open notepad":
{"intent":"open_app","action":"open_notepad","message":"Notepad, coming right up, sir.","data":{}}

Example — user says "what is the speed of light":
{"intent":"conversation","action":null,"message":"299,792,458 metres per second. Shall I also remind you to look both ways before crossing the street?","data":{}}
"""


# ═════════════════════════════════════════════
#  STEP 2.1 — ConversationMemory
#  Stores a rolling window of chat history.
# ═════════════════════════════════════════════
class ConversationMemory:
    """
    Maintains a sliding window of the last MAX_HISTORY turn-pairs
    so Jarvis can reference earlier parts of the conversation.

    Internal structure:
        _history : list of {"role": "user"|"assistant", "content": str}
    """

    def __init__(self, max_history: int = MAX_HISTORY):
        self.max_history = max_history   # max *pairs* → 2× messages stored
        self._history: list[dict] = []   # raw message list

    # ── Write ────────────────────────────────
    def add(self, role: str, content: str) -> None:
        """
        Append a new message to history.
        Trims the oldest pair when the window overflows.

        Args:
            role    : "user" or "assistant"
            content : message text
        """
        self._history.append({"role": role, "content": content})

        # Each "turn" = 1 user msg + 1 assistant msg → 2 entries per pair
        max_messages = self.max_history * 2
        if len(list(self._history)) > max_messages:
            # Drop oldest pair (first two entries)
            self._history = self._history[2:]

    # ── Read ─────────────────────────────────
    def get_messages(self) -> list[dict]:
        """
        Return [system_prompt_message] + current history.
        This is the exact list Ollama's /api/chat expects.
        """
        system_msg = {"role": "system", "content": SYSTEM_PROMPT.strip()}
        return [system_msg] + self._history

    # ── Reset ────────────────────────────────
    def clear(self) -> None:
        """Wipe conversation history (system prompt survives)."""
        self._history = []

    # ── Introspect ───────────────────────────
    def summary(self) -> str:
        """One-line status string for voice feedback."""
        pairs = len(self._history) // 2
        return (
            f"Memory holds {pairs} turn(s) "
            f"(max {self.max_history}). "
            f"{self.max_history - pairs} slot(s) remaining."
        )


# ═════════════════════════════════════════════
#  STEP 2.2 — _safe_parse
#  Cleans raw LLM output and returns a usable dict.
# ═════════════════════════════════════════════
def _safe_parse(raw: str) -> dict:
    """
    Strip markdown fences, then JSON-parse the LLM response.
    Never raises — always returns a valid dict.

    Args:
        raw : raw string from Ollama response

    Returns:
        Parsed dict on success, or a safe fallback dict on failure.
    """
    try:
        # 1. Strip common markdown code fences the model might emit
        cleaned = raw.strip()
        for fence in ("```json", "```JSON", "```"):
            cleaned = cleaned.replace(fence, "")
        cleaned = cleaned.strip()

        # 2. Locate the JSON object boundaries (handles leading junk text)
        start = cleaned.find("{")
        end   = cleaned.rfind("}") + 1
        if start == -1 or end == 0:
            raise ValueError("No JSON object found in response.")

        json_str: str = cleaned[start:end]
        parsed: dict = json.loads(json_str)

        # 3. Ensure required keys exist; fill missing ones gracefully
        parsed.setdefault("intent",  "conversation")
        parsed.setdefault("action",  None)
        parsed.setdefault("message", parsed.get("response", "Understood."))
        parsed.setdefault("data",    {})

        return parsed

    except Exception as parse_err:
        # Log for debugging but never crash the caller
        print(f"[BRAIN][PARSE WARN] Could not parse JSON: {parse_err}")
        print(f"[BRAIN][RAW] {raw[:200]}")
        return {
            "intent":  "conversation",
            "action":  None,
            "message": raw.strip() or "I had trouble forming a response, sir.",
            "data":    {}
        }


# ═════════════════════════════════════════════
#  STEP 2.3 — JarvisBrain
#  The main LLM interface. Drop-in upgrade over
#  the old Main_Brain() function.
# ═════════════════════════════════════════════
class JarvisBrain:
    """
    Multi-turn conversational brain powered by Ollama /api/chat.

    Public API (plug-in compatible with co_brain.py):
        think(user_input) → dict
        reset_memory()    → dict
        recall_last()     → str | None
        status()          → str
    """

    def __init__(self):
        self.memory = ConversationMemory()
        print("[BRAIN] JarvisBrain online. Multi-turn memory active.")

    # ── Core: send message, get structured reply ──
    def think(self, user_input: str) -> dict:
        """
        Main entry point. Sends user_input to Ollama with full
        conversation history, parses the response, updates memory.

        Args:
            user_input : the cleaned command string from co_brain

        Returns:
            Parsed JSON dict: {intent, action, message, data}
        """
        if not user_input.strip():
            return self._error_response("Empty input received.")

        # 1. Add this turn's user message to rolling memory
        self.memory.add("user", user_input)

        # 2. Build the full message list (system + history)
        messages = self.memory.get_messages()

        # 3. POST to Ollama /api/chat
        payload = {
            "model":    MODEL_NAME,
            "messages": messages,
            "stream":   False,
            "options": {
                "temperature": 0.7,
                "top_p":       0.9,
                "num_predict": 256
            }
        }

        try:
            t0 = time.time()
            response = requests.post(OLLAMA_URL, json=payload, timeout=30)
            elapsed  = time.time() - t0
            print(f"[BRAIN] Ollama responded in {elapsed:.2f}s")

            # 4. HTTP-level error check
            if response.status_code != 200:
                print(f"[BRAIN][HTTP ERROR] Status {response.status_code}: {response.text}")
                return self._error_response("Ollama returned a bad status code.")

            # 5. Extract assistant message text from response
            result     = response.json()
            raw_reply  = result.get("message", {}).get("content", "").strip()

            # 6. Parse the raw text into a structured dict
            parsed = _safe_parse(raw_reply)

            # 7. Store the assistant's reply text in memory for context
            assistant_msg = str(parsed.get("message") or raw_reply)
            self.memory.add("assistant", assistant_msg)

            return parsed

        # ── Graceful error handling ───────────────
        except requests.exceptions.ConnectionError:
            print("[BRAIN][ERROR] Ollama is offline or unreachable.")
            return self._error_response(
                "I can't reach my own brain right now, sir. "
                "Make sure Ollama is running on port 11434."
            )

        except requests.exceptions.Timeout:
            print("[BRAIN][ERROR] Ollama request timed out (>30s).")
            return self._error_response(
                "My neural response timed out. "
                "Perhaps the model is overloaded, sir."
            )

        except Exception as e:
            print(f"[BRAIN][ERROR] Unexpected: {e}")
            return self._error_response(f"Something unexpected happened: {e}")

    # ── Memory management ─────────────────────
    def reset_memory(self) -> dict:
        """
        Wipe all conversation history.
        Returns a response dict confirming the reset.
        """
        self.memory.clear()
        print("[BRAIN] Memory wiped.")
        return {
            "intent":  "conversation",
            "action":  None,
            "message": "Memory wiped clean, sir. We start fresh.",
            "data":    {}
        }

    def recall_last(self) -> str | None:
        """
        Scan history backwards for the most recent user message.

        Returns:
            The last user message string, or None if history is empty.
        """
        messages = self.memory.get_messages()
        for msg in reversed(messages):
            if msg.get("role") == "user":
                return msg.get("content")
        return None

    # ── Status ───────────────────────────────
    def status(self) -> str:
        """Return a one-line memory summary for voice feedback."""
        return self.memory.summary()

    # ── Internal helpers ─────────────────────
    @staticmethod
    def _error_response(msg: str) -> dict:
        """
        Build a standardised error response dict.
        Used internally whenever an exception is caught.
        """
        return {
            "intent":  "error",
            "action":  None,
            "message": msg,
            "data":    {}
        }


# ─────────────────────────────────────────────
#  BACKWARD-COMPAT SHIM
#  co_brain.py currently calls Main_Brain(text).
#  This shim keeps the old import working until
#  you do Step 2.4 and swap to JarvisBrain.
# ─────────────────────────────────────────────
_legacy_brain = JarvisBrain()

def Main_Brain(text: str) -> str:
    """
    Legacy wrapper around JarvisBrain.think().
    Returns just the 'message' string so existing
    co_brain.py code doesn't break.
    """
    result = _legacy_brain.think(text)
    return result.get("message", "I encountered an error, sir.")