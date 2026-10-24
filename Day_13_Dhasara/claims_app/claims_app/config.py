"""Settings read from environment variables so no secret lives in source control."""
import os


class Config:
    """Default config: set SECRET_KEY and DATABASE_URL (MySQL) in the environment."""
    SECRET_KEY = os.environ.get("SECRET_KEY", "")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "mysql+pymysql://claims_user:claims_pass@localhost/claims_db")
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
