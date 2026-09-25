import os
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.environ["GROQ_API_KEY"]
GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
NEONIZE_PATH = os.environ.get("NEONIZE_PATH", "./session.db")
DB_PATH = os.environ.get("DB_PATH", "./database.db")
