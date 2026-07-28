from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration (env or `.env` next to the service)."""

    app_host: str = "0.0.0.0"
    app_port: int = 9000

    embeddings_pt_path: str = "/app/models/embeddings.pt"
    aliases_parquet_path: str = "/app/models/aliases.parquet"
    class_mask_path: str = "/app/models/class_mask.npy"
    manifest_path: str | None = "/app/models/manifest.json"
    model_path: str = "/app/models/LaBSE"

    default_top_k: int = 10
    max_top_k: int = 200
    encode_batch_size: int = 64
    max_length: int = 128
    mmap_embeddings: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
