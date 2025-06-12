import os
from dotenv import load_dotenv

# Load environment variables from a .env file
load_dotenv()

class Settings:
    # Database Configuration
    DATABASE_URL = os.getenv("ASYNC_SQLALCHEMY_DATABASE_URL")

    # JWT Authentication
    SECRET_KEY = os.getenv("SECRET_KEY", "a_very_secret_key")
    ALGORITHM = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))

    # Google OAuth Configuration (for later)
    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
    GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")

    # Google Generative AI Configuration
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

    # Frontend URL
    FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

settings = Settings() 