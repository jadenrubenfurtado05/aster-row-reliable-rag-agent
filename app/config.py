import os
from typing import Optional
from dotenv import load_dotenv
from pydantic import BaseModel, Field

# Load environment variables from .env file if available
load_dotenv()

class AppConfig(BaseModel):
    """Application configuration safely loaded from environment variables."""
    llm_provider: str = Field(default_factory=lambda: os.getenv("LLM_PROVIDER", "google"))
    llm_api_key: Optional[str] = Field(default_factory=lambda: os.getenv("LLM_API_KEY"))
    llm_model: str = Field(default_factory=lambda: os.getenv("LLM_MODEL", "gemini-2.5-flash"))
    embedding_model: str = Field(default_factory=lambda: os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2"))

    def get_masked_api_key(self) -> str:
        """Returns a safe, masked representation of the API key for logging."""
        if not self.llm_api_key:
            return "NOT_SET"
        if len(self.llm_api_key) <= 8:
            return "***"
        return f"{self.llm_api_key[:4]}...{self.llm_api_key[-4:]}"

def get_config() -> AppConfig:
    """Factory function to get application configuration."""
    return AppConfig()
