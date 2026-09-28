import os
import re
import urllib.parse
from typing import List, Union, Any, Optional
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "SIH26074 Weather Downscaling"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    API_V1_STR: str = "/api/v1"
    
    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = 8000
    
    # PostgreSQL Database URL loaded from .env or environment
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/sih26074_db"

    # AI Advisory Provider Settings (Phase 5.4)
    AI_ADVISORY_PROVIDER: str = "mock"  # "mock", "ollama", "gemini", "openai"
    AI_ADVISORY_MODEL: str = "mock-agricultural-advisor-v1"
    AI_ADVISORY_API_KEY: Optional[str] = None
    AI_ADVISORY_ENDPOINT: Optional[str] = None
    AI_ADVISORY_TIMEOUT_SECONDS: float = 15.0
    AI_ADVISORY_MAX_RETRIES: int = 2
    AI_ADVISORY_TEMPERATURE: float = 0.2

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def assemble_database_url(cls, v: Any) -> str:
        url_env = (
            os.getenv("DATABASE_URL")
            or os.getenv("SYNC_DATABASE_URL")
            or os.getenv("SUPABASE_DB_URL")
            or os.getenv("SUPABASE_DATABASE_URL")
            or v
        )
        if isinstance(url_env, str) and url_env.strip():
            return url_env.strip()
        return "postgresql://postgres:postgres@localhost:5432/sih26074_db"
    
    # Allowed CORS Origins
    CORS_ORIGINS: Union[List[str], str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]

    @field_validator("SERVER_PORT", mode="before")
    @classmethod
    def assemble_server_port(cls, v: Any) -> int:
        port_env = os.getenv("PORT")
        if port_env:
            try:
                return int(port_env)
            except ValueError:
                pass
        if v is not None:
            try:
                return int(v)
            except ValueError:
                pass
        return 8000

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return v
        elif isinstance(v, str):
            return [v]
        return ["*"]

    @property
    def sync_database_url(self) -> str:
        """
        Sanitize and format DATABASE_URL for SQLAlchemy + psycopg2:
        1. Checks SYNC_DATABASE_URL / DATABASE_URL.
        2. Strips whitespace and enclosing quotes.
        3. Normalizes legacy postgres:// to postgresql://.
        4. Strips unsupported params like ?pgbouncer=true.
        5. Safely URL-encodes special characters in passwords (e.g. '@').
        """
        raw_url = (
            os.getenv("SYNC_DATABASE_URL")
            or os.getenv("DATABASE_URL")
            or os.getenv("SUPABASE_DB_URL")
            or os.getenv("SUPABASE_DATABASE_URL")
            or self.DATABASE_URL
        )
        if not raw_url or not isinstance(raw_url, str):
            return "postgresql://postgres:postgres@localhost:5432/sih26074_db"

        url = raw_url.strip()
        if (url.startswith('"') and url.endswith('"')) or (url.startswith("'") and url.endswith("'")):
            url = url[1:-1].strip()

        if not url:
            return "postgresql://postgres:postgres@localhost:5432/sih26074_db"

        # Normalize legacy or cloud default postgres:// to postgresql://
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://"):]
        
        # Remove pgbouncer query flag if present (psycopg2 does not accept pgbouncer as a libpq parameter)
        url = url.replace("?pgbouncer=true", "").replace("&pgbouncer=true", "")
        
        # Safely parse and encode credentials if password has special characters like '@'
        match = re.match(r"^(postgresql(?:\+\w+)?://)([^:]+):(.*)@([^@:]+(?::\d+)?(?:/.*)?)$", url)
        if match:
            prefix, user, password, host_and_path = match.groups()
            unquoted_pw = urllib.parse.unquote(password)
            encoded_pw = urllib.parse.quote_plus(unquoted_pw)
            url = f"{prefix}{user}:{encoded_pw}@{host_and_path}"
            
        return url

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )


settings = Settings()
