from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CHESSLAB_", extra="ignore")
    database_url: str = "postgresql+psycopg://chesslab@db/chesslab"
    key_pepper: str = Field(min_length=32)
    signing_key_path: Path
    signing_key_id: str = "ed25519-2026-01"
    public_origin: str = "http://localhost:8080"
    secure_cookies: bool = True
    session_seconds: int = Field(default=28800, ge=300, le=86400)
    grant_seconds: int = Field(default=43200, ge=60, le=43200)
    login_limit: int = Field(default=10, ge=1)
    activation_limit: int = Field(default=20, ge=1)
    validation_limit: int = Field(default=120, ge=1)
    testing: bool = False
    trusted_proxy_cidrs: list[str] = []

    @model_validator(mode="after")
    def check_origin(self):
        from ipaddress import ip_network
        for cidr in self.trusted_proxy_cidrs: ip_network(cidr)
        from urllib.parse import urlsplit
        url = urlsplit(self.public_origin)
        if url.scheme not in ("http", "https") or not url.hostname or url.path not in ("", "/"):
            raise ValueError("Origin publik harus berupa origin HTTP/HTTPS")
        if not self.secure_cookies and url.hostname not in ("localhost", "127.0.0.1", "testserver"):
            raise ValueError("Cookie tanpa TLS hanya diizinkan untuk localhost")
        return self


@lru_cache
def get_settings():
    return Settings()
