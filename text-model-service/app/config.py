from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration (env or `.env` next to the service)."""

    app_host: str = "0.0.0.0"
    app_port: int = 9000

    embeddings_pt_path: str = "/app/models/text_embedding.pt"
    embeddings_csv_path: str = "/app/models/text_embedding.csv"
    model_path: str = "/app/models/rubert-tiny2"

    default_top_k: int = 10
    max_top_k: int = 200
    encode_batch_size: int = 64
    max_length: int = 64

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
