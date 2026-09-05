from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
	DATABASE_URL: str
	CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"
	ENVIRONMENT: str = "development"
	LOG_LEVEL: str = "INFO"

	model_config = SettingsConfigDict(
		env_file=".env",
		env_file_encoding="utf-8",
		case_sensitive=True,
	)

	@property
	def cors_origins(self) -> list[str]:
		return [
			origin.strip()
			for origin in self.CORS_ORIGINS.split(",")
			if origin.strip()
		]

@lru_cache
def get_settings() -> Settings:
	return Settings()

settings = get_settings()
