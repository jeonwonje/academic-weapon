"""Configuration management using pydantic-settings."""
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Canvas API Configuration
    canvas_api_token: str
    canvas_api_url: str = "https://canvas.nus.edu.sg"
    
    # Data Storage
    data_dir: Path = Path("./data")
    
    # Sync Configuration
    sync_hour: int = 6
    sync_minute: int = 0
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Ensure data directory exists
        self.data_dir.mkdir(parents=True, exist_ok=True)


# Global settings instance
settings = Settings()
