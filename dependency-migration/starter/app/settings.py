from pydantic import BaseSettings, Field


class Settings(BaseSettings):
    currency: str = "USD"
    max_amount_cents: int = Field(default=10000000, gt=0)

    class Config:
        env_prefix = "EXPENSE_"