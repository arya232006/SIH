import os
from dotenv import load_dotenv

# Load .env if present
load_dotenv()


def _key(name: str) -> str:
    """
    Reads an API key, treating the .env.example placeholders as unset.

    Left as-is, 'your_gemini_api_key_here' is a truthy string: the app reports
    the provider as configured, sends every request to a live endpoint with an
    invalid key, and silently falls back on the failure -- which looks exactly
    like a working system that has nothing to say.
    """
    value = os.getenv(name, "").strip()
    if not value or value.startswith("your_") or value.endswith("_here"):
        return ""
    return value


class Settings:
    PROJECT_NAME: str = "MediKiosk AI Clinical History Platform"
    API_V1_STR: str = "/api"
    
    # LLM Settings
    # Supported: "gemini", "groq", "openrouter", "huggingface", "mock"
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "gemini").lower()
    
    GEMINI_API_KEY: str = _key("GEMINI_API_KEY")
    GROQ_API_KEY: str = _key("GROQ_API_KEY")
    OPENROUTER_API_KEY: str = _key("OPENROUTER_API_KEY")
    HF_API_KEY: str = _key("HF_API_KEY")
    
    # Model Names
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    OPENROUTER_MODEL: str = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct:free")
    
    # Staff Secret for admin actions
    ADMIN_SECRET: str = os.getenv("ADMIN_SECRET", "medikiosk_admin_secret_2026")
    
    # CORS Origins
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://localhost:8000",
        "*"
    ]

settings = Settings()

