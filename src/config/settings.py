"""Configuration management using Pydantic Settings."""

from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import BaseModel


class AppConfig(BaseSettings):
    """Application configuration."""

    model_config = SettingsConfigDict(extra="ignore")

    env: Literal["development", "production", "testing"] = Field(default="development", alias="APP_ENV")
    debug: bool = Field(default=False, alias="APP_DEBUG")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO", alias="LOG_LEVEL"
    )
    log_format: Literal["json", "console"] = Field(default="json", alias="LOG_FORMAT")


class GoogleCloudConfig(BaseSettings):
    """Google Cloud configuration for Pub/Sub."""

    model_config = SettingsConfigDict(extra="ignore")

    project_id: str = Field(alias="GOOGLE_CLOUD_PROJECT_ID")
    credentials_path: Path | None = Field(default=None, alias="GOOGLE_CLOUD_CREDENTIALS_PATH")

    @field_validator("credentials_path", mode="before")
    @classmethod
    def validate_path(cls, v: str | Path | None) -> Path | None:
        """Convert string to Path."""
        if v is None or v == "":
            return None
        return Path(v) if isinstance(v, str) else v


class GmailConfig(BaseSettings):
    """Gmail API configuration."""

    credentials_path: Path = Field(alias="GMAIL_CREDENTIALS_PATH")
    token_path: Path = Field(alias="GMAIL_TOKEN_PATH")
    inbox_label: str = Field(default="INBOX", alias="GMAIL_INBOX_LABEL")
    processed_label: str = Field(default="Claims/Processed", alias="GMAIL_PROCESSED_LABEL")
    poll_interval_seconds: int = Field(default=30, alias="GMAIL_POLL_INTERVAL")
    max_attachment_size_mb: int = Field(default=25, alias="GMAIL_MAX_ATTACHMENT_SIZE_MB")

    # Pub/Sub configuration (for Gmail watch notifications)
    pubsub_topic_name: str = Field(default="gmail-notifications", alias="GMAIL_PUBSUB_TOPIC")
    pubsub_subscription_name: str = Field(default="gmail-notifications-sub", alias="GMAIL_PUBSUB_SUBSCRIPTION")

    @field_validator("credentials_path", "token_path", mode="before")
    @classmethod
    def validate_path(cls, v: str | Path) -> Path:
        """Convert string to Path."""
        return Path(v) if isinstance(v, str) else v


class NCBConfig(BaseSettings):
    """NCB API configuration."""

    api_base_url: str = Field(alias="NCB_API_BASE_URL")
    api_key: SecretStr = Field(alias="NCB_API_KEY")
    timeout_seconds: int = Field(default=30, alias="NCB_TIMEOUT")
    max_retries: int = Field(default=3, alias="NCB_MAX_RETRIES")
    retry_backoff_base: float = 2.0
    retry_backoff_max: float = 60.0


class SheetsConfig(BaseSettings):
    """Google Sheets configuration."""

    credentials_path: Path = Field(alias="SHEETS_CREDENTIALS_PATH")
    spreadsheet_id: str = Field(alias="SHEETS_SPREADSHEET_ID")

    @field_validator("credentials_path", mode="before")
    @classmethod
    def validate_path(cls, v: str | Path) -> Path:
        """Convert string to Path."""
        return Path(v) if isinstance(v, str) else v


class DriveConfig(BaseSettings):
    """Google Drive configuration."""

    credentials_path: Path = Field(alias="DRIVE_CREDENTIALS_PATH")
    folder_id: str = Field(alias="DRIVE_FOLDER_ID")

    @field_validator("credentials_path", mode="before")
    @classmethod
    def validate_path(cls, v: str | Path) -> Path:
        """Convert string to Path."""
        return Path(v) if isinstance(v, str) else v


class RedisConfig(BaseSettings):
    """Redis configuration."""

    url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    ocr_queue: str = Field(default="claims:ocr_queue", alias="REDIS_OCR_QUEUE")
    submission_queue: str = Field(
        default="claims:submission_queue", alias="REDIS_SUBMISSION_QUEUE"
    )
    exception_queue: str = Field(
        default="claims:exception_queue", alias="REDIS_EXCEPTION_QUEUE"
    )


class OCRConfig(BaseSettings):
    """OCR configuration."""

    model_config = SettingsConfigDict(extra="ignore")

    use_gpu: bool = Field(default=True, alias="OCR_USE_GPU")
    default_language: str = Field(default="en", alias="OCR_DEFAULT_LANGUAGE")
    supported_languages: list[str] = Field(
        default=["en", "ch", "ms", "ta"], alias="OCR_SUPPORTED_LANGUAGES"
    )
    detection_threshold: float = Field(default=0.5, alias="OCR_DETECTION_THRESHOLD")
    recognition_threshold: float = Field(default=0.5, alias="OCR_RECOGNITION_THRESHOLD")
    high_confidence_threshold: float = Field(
        default=0.90, alias="OCR_HIGH_CONFIDENCE_THRESHOLD"
    )
    medium_confidence_threshold: float = Field(
        default=0.75, alias="OCR_MEDIUM_CONFIDENCE_THRESHOLD"
    )
    batch_size: int = Field(default=6, alias="OCR_BATCH_SIZE")
    max_image_size: int = Field(default=4096, alias="OCR_MAX_IMAGE_SIZE")
    qa_sampling_percentage: float = Field(
        default=0.05, alias="OCR_QA_SAMPLING_PERCENTAGE"
    )  # 5% random sampling for QA

    @field_validator("supported_languages", mode="before")
    @classmethod
    def parse_languages(cls, v: str | list[str]) -> list[str]:
        """Parse comma-separated string or list."""
        if isinstance(v, str):
            return [lang.strip() for lang in v.split(",") if lang.strip()]
        return v


class AdminConfig(BaseSettings):
    """Admin dashboard configuration."""

    model_config = SettingsConfigDict(extra="ignore")

    api_key: SecretStr = Field(alias="ADMIN_API_KEY")
    port: int = Field(default=8080, alias="ADMIN_PORT")
    cors_origins: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:8080"],
        alias="ADMIN_CORS_ORIGINS",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_origins(cls, v: str | list[str]) -> list[str]:
        """Parse comma-separated string or list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v


class AlertsConfig(BaseSettings):
    """Alerts configuration."""

    model_config = SettingsConfigDict(extra="ignore")

    enabled: bool = Field(default=True, alias="ALERTS_ENABLED")
    smtp_host: str = Field(default="smtp.gmail.com", alias="SMTP_HOST")
    smtp_port: int = Field(default=587, alias="SMTP_PORT")
    smtp_username: str = Field(default="", alias="SMTP_USERNAME")
    smtp_password: SecretStr = Field(default="", alias="SMTP_PASSWORD")
    smtp_from_email: str = Field(default="", alias="SMTP_FROM_EMAIL")
    alert_recipients: list[str] = Field(default=[], alias="ALERT_RECIPIENTS")

    @field_validator("alert_recipients", mode="before")
    @classmethod
    def parse_recipients(cls, v: str | list[str]) -> list[str]:
        """Parse comma-separated string or list."""
        if isinstance(v, str):
            return [email.strip() for email in v.split(",") if email.strip()]
        return v


class StorageConfig(BaseSettings):
    """Storage configuration."""

    temp_storage_path: Path = Field(
        default=Path("/app/data/temp"), alias="TEMP_STORAGE_PATH"
    )
    temp_file_max_age_hours: int = Field(default=24, alias="TEMP_FILE_MAX_AGE_HOURS")

    @field_validator("temp_storage_path", mode="before")
    @classmethod
    def validate_path(cls, v: str | Path) -> Path:
        """Convert string to Path."""
        return Path(v) if isinstance(v, str) else v


class EmailParsingConfig(BaseModel):
    """Configuration for email subject/body parsing."""

    # Enable/disable email parsing
    enable_subject_parsing: bool = Field(
        default=True,
        description="Parse claim data from email subjects"
    )
    enable_body_parsing: bool = Field(
        default=True,
        description="Parse claim data from email bodies"
    )

    # Confidence thresholds
    min_field_confidence: float = Field(
        default=0.70,
        ge=0.0,
        le=1.0,
        description="Minimum confidence to accept extracted field"
    )

    # Text extraction limits
    max_body_length: int = Field(
        default=10000,
        description="Maximum email body length to process (characters)"
    )

    # Pattern matching
    use_fuzzy_matching: bool = Field(
        default=True,
        description="Enable fuzzy string matching for names/providers"
    )
    fuzzy_threshold: float = Field(
        default=0.85,
        ge=0.0,
        le=1.0,
        description="Fuzzy match threshold (0.0-1.0)"
    )

    model_config = SettingsConfigDict(env_prefix="EMAIL_PARSING_")


class DataFusionConfig(BaseModel):
    """Configuration for email+OCR data fusion."""

    # Enable/disable fusion
    enable_fusion: bool = Field(
        default=True,
        description="Merge email and OCR extractions"
    )

    # Confidence boosting
    exact_match_boost: float = Field(
        default=0.10,
        ge=0.0,
        le=0.20,
        description="Confidence boost for exact email/OCR agreement"
    )
    fuzzy_match_boost: float = Field(
        default=0.05,
        ge=0.0,
        le=0.10,
        description="Confidence boost for fuzzy email/OCR agreement"
    )

    # Field preferences
    prefer_ocr_fields: list[str] = Field(
        default_factory=lambda: [
            "provider_name", "total_amount", "service_date",
            "receipt_number", "gst_sst_amount", "provider_address"
        ],
        description="Fields to prefer OCR extraction"
    )
    prefer_email_fields: list[str] = Field(
        default_factory=lambda: [
            "member_id", "member_name", "policy_number"
        ],
        description="Fields to prefer email extraction"
    )

    # Conflict resolution
    log_conflicts: bool = Field(
        default=True,
        description="Log conflicts to sheets/logs"
    )

    model_config = SettingsConfigDict(env_prefix="FUSION_")


class Settings(BaseSettings):
    """Master settings combining all configuration sections."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app: AppConfig = Field(default_factory=AppConfig)
    google_cloud: GoogleCloudConfig = Field(default_factory=GoogleCloudConfig)
    gmail: GmailConfig = Field(default_factory=GmailConfig)
    ncb: NCBConfig = Field(default_factory=NCBConfig)
    sheets: SheetsConfig = Field(default_factory=SheetsConfig)
    drive: DriveConfig = Field(default_factory=DriveConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)
    ocr: OCRConfig = Field(default_factory=OCRConfig)
    admin: AdminConfig = Field(default_factory=AdminConfig)
    alerts: AlertsConfig = Field(default_factory=AlertsConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)

    # Phase 3: Email extraction
    email_parsing: EmailParsingConfig = Field(default_factory=EmailParsingConfig)
    data_fusion: DataFusionConfig = Field(default_factory=DataFusionConfig)


# Global settings instance
settings = Settings()
