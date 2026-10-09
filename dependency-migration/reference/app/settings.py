from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="EXPENSE_")
    currency: str = "USD"
    max_amount_cents: int = Field(default=10000000, gt=0)