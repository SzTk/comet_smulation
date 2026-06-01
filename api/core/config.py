from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_nested_delimiter="__")

    auth_enabled: bool = False
    google_client_id: str = ""
    allowed_emails: list[str] = []


settings = Settings()
