from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Buddhi AI Studio Backend"
    cors_origins: list[str] = ["http://localhost:3000"]


settings = Settings()
