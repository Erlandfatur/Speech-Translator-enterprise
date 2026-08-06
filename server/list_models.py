import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
if not api_key or api_key == "your_api_key_here":
    print("API Key belum diset di .env!")
else:
    try:
        client = genai.Client(api_key=api_key)
        print("Model Gemini yang tersedia untuk API Key Anda:\n")
        models = list(client.models.list())
        for m in models:
            # Show model names that support content generation
            if hasattr(m, "name"):
                print(f"- {m.name}")
    except Exception as e:
        print(f"Error saat mengambil daftar model: {e}")
