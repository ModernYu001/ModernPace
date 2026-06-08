"""List the Gemini models your API key can actually use for generateContent.

Run on your own machine (where the key works):
    python list_models.py

Then copy the ids you want into PACE_MODELS in .env.
"""
import os

from dotenv import load_dotenv
from google import genai

load_dotenv()

key = (os.getenv("PACE_API_KEYS", "").split(",")[0] or os.getenv("GOOGLE_API_KEY", "")).strip()
if not key:
    raise SystemExit("No API key found. Set GOOGLE_API_KEY or PACE_API_KEYS in .env")

client = genai.Client(api_key=key)

names = []
for m in client.models.list():
    actions = getattr(m, "supported_actions", None) or getattr(
        m, "supported_generation_methods", None
    ) or []
    if (not actions) or ("generateContent" in actions):
        names.append(m.name.replace("models/", ""))

names = sorted(set(names))
print(f"\n{len(names)} models support generateContent with this key:\n")
for n in names:
    mark = "  <- flash" if "flash" in n.lower() else ""
    print(f"  {n}{mark}")

flash = [n for n in names if "flash" in n.lower() and "tts" not in n.lower() and "image" not in n.lower()]
if flash:
    print("\nSuggested PACE_MODELS line for .env:")
    print("PACE_MODELS=" + ",".join(flash[:4]))
