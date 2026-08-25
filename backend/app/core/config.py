from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    app_name: str = "canal-vegetation-api"
    api_prefix: str = "/api/v1"
    cors_origins: str = "*"

    data_dir: Path = Field(default=Path("./data"), validation_alias=AliasChoices("DATA_DIR", "DATA_ROOT"))
    output_dir: Path = Field(default=Path("./outputs"), validation_alias=AliasChoices("OUTPUT_DIR"))
    model_dir: Path = Field(
        default=Path("./app/models/model_weights"),
        validation_alias=AliasChoices("MODEL_DIR", "MODEL_ROOT"),
    )
    upload_dir: Path = Field(default=Path("./data/uploads"), validation_alias=AliasChoices("UPLOAD_DIR", "UPLOAD_ROOT"))
    project_root: Path = Field(
        default=Path("./data/projects"),
        validation_alias=AliasChoices("PROJECT_ROOT", "PREDICTION_ROOT"),
    )

    database_url: str = "sqlite:///./data/jobs.db"
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/0"
    use_celery: bool = False

    storage_backend: str = "local"
    s3_bucket: str = ""
    s3_prefix: str = "canal-jobs"
    s3_region: str = "us-east-1"
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""

    canal_model_name: str = "best_binary_unet_v5.pth"
    canal_model_fallback: str = "best_binary_unet_v5_lines.pth"
    model_v5_path: str = ""
    model_v5_lines_path: str = ""
    fic_model_name: str = "best_fic_unet.pth"
    canal_encoder: str = "resnet50"
    fic_encoder: str = "resnet34"

    patch_size: int = Field(default=512, validation_alias=AliasChoices("PATCH_SIZE"))
    tile_size: int = Field(default=512, validation_alias=AliasChoices("TILE_SIZE"))
    tile_step: int = Field(default=384, validation_alias=AliasChoices("TILE_STEP", "STEP"))
    downscale_factor: int = Field(default=8, validation_alias=AliasChoices("DOWNSCALE_FACTOR", "DOWNSAMPLE"))
    analysis_downscale: int = 4
    reach_len_px: int = 100

    canal_threshold: float = Field(default=0.4, validation_alias=AliasChoices("CANAL_THRESHOLD", "THRESHOLD"))
    fic_threshold: float = 0.2
    valid_alpha: int = 255
    min_valid_frac: float = 0.3

    min_component_area_px: int = 50
    min_canal_aspect: float = 2.0
    min_skel_ratio: float = 0.008
    min_canal_mean_width_m: float = 1.6
    min_canal_max_width_m: float = 2.2
    max_canal_width_m: float = 28.0

    fic_min_component_area: int = 20
    corridor_shapefile: str = ""
    corridor_buffer_m: float = Field(
        default=35.0, validation_alias=AliasChoices("CORRIDOR_BUFFER_M", "CORRIDOR_WIDTH_M")
    )
    alignment_reach_m: float = 50.0

    silt_low_max: float = 0.20
    silt_mod_max: float = 0.50
    silt_veg_max: float = 2.00

    imagenet_mean: tuple[float, float, float] = (0.485, 0.456, 0.406)
    imagenet_std: tuple[float, float, float] = (0.229, 0.224, 0.225)

    log_level: str = "INFO"

    def ensure_dirs(self) -> None:
        for path in (self.data_dir, self.output_dir, self.upload_dir, self.model_dir, self.project_root):
            path.mkdir(parents=True, exist_ok=True)
        Path("./data").mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_dirs()
    return settings
