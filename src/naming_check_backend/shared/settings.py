from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Backend Service"
    app_env: str = "local"
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    visual_model_service_base_url: str = "http://127.0.0.1:9000"
    visual_model_service_timeout_seconds: float = 300.0
    visual_model_service_max_top_k: int = 200

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
