from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Backend Service"
    app_env: str = "local"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"
    visualmodel_enabled: bool = False
    visualmodel_similarity_module_path: str = "../VisualModel/src/similarity.py"
    visualmodel_embeddings_path: str = "../VisualModel/models/logos_embedding.pt"
    visualmodel_assets_root: str = "../VisualModel/data/logos"
    visualmodel_top_k: int = 10
    visualmodel_score_threshold: float = 0.0
    visualmodel_source: str = "visual_model"

    visual_model_service_base_url: str = "http://127.0.0.1:9000"
    visual_model_service_timeout_seconds: float = 300.0
    visual_model_service_max_top_k: int = 200
    text_model_service_base_url: str = "http://127.0.0.1:9100"
    text_model_service_timeout_seconds: float = 120.0
    text_model_service_max_top_k: int = 200
    # Defaults allow local manual UI (browser origin != API host). Override or clear via env.
    cors_allow_origins: str = (
        "http://127.0.0.1:5173,http://localhost:5173,"
        "http://127.0.0.1:8080,http://localhost:8080,"
        "http://127.0.0.1:5500,http://localhost:5500,"
        "http://127.0.0.1:3000,http://localhost:3000"
    )
    cors_allow_methods: str = "GET,POST,PUT,PATCH,DELETE,OPTIONS"
    cors_allow_headers: str = "*"
    cors_allow_credentials: bool = False

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
