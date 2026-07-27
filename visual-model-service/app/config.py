from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration (env or `.env` next to the service)."""

    app_host: str = "0.0.0.0"
    app_port: int = 9000

    embeddings_pt_path: str = "/app/models/logos_embedding.pt"
    embeddings_csv_path: str = "/app/models/logos_embedding.csv"
    # Fine-tuned VGG16 weights (safetensors). Empty / missing → ImageNet fallback.
    model_weights_path: str = "/app/models/similarity.safetensors"
    # Precomputed color palettes; empty disables color re-ranking.
    colors_csv_path: str = "/app/models/logos_embedding_colors.csv"
    assets_root: str = "/app/assets"

    palette_size: int = 8
    color_rerank_pool: int = 500
    color_workers: int = 4

    default_top_k: int = 10
    max_top_k: int = 200

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
