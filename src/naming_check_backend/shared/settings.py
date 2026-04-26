from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Backend Service"
    app_env: str = "local"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    visualmodel_enabled: bool = False
    visualmodel_similarity_module_path: str = "../VisualModel/src/similarity.py"
    visualmodel_embeddings_path: str = "../VisualModel/models/logos_embedding.pt"
    visualmodel_assets_root: str = "../VisualModel/data/logos"
    visualmodel_top_k: int = 10
    visualmodel_score_threshold: float = 0.0
    visualmodel_source: str = "visual_model"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
