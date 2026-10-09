from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ExpenseCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid", from_attributes=True)

    external_id: str = Field(alias="externalId", min_length=1)
    merchant_code: str = Field(alias="merchantCode")
    amount_cents: int = Field(alias="amountCents", strict=True, gt=0, le=10000000)
    category: Literal["personal", "work"]
    receipt: str | None = None
    notes: str | None = None

    @field_validator("category", mode="before")
    @classmethod
    def normalize_category(cls, value):
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("merchant_code", mode="before")
    @classmethod
    def normalize_merchant(cls, value):
        return str(value) if isinstance(value, int) and not isinstance(value, bool) else value

    @model_validator(mode="after")
    def require_receipt(self):
        if self.category == "work" and self.amount_cents > 10000 and not self.receipt:
            raise ValueError("work expenses above 10000 cents require a receipt")
        return self


class ExpensePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    notes: str | None = None


class ExpenseRead(ExpenseCreate):
    expense_id: int = Field(alias="expenseId")