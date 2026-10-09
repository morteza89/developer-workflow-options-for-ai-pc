from typing import Literal, Optional

from pydantic import BaseModel, Field, conint, root_validator, validator


class ExpenseCreate(BaseModel):
    external_id: str = Field(alias="externalId", min_length=1)
    merchant_code: str = Field(alias="merchantCode")
    amount_cents: conint(strict=True, gt=0, le=10000000) = Field(alias="amountCents")
    category: Literal["personal", "work"]
    receipt: Optional[str]
    notes: Optional[str]

    @validator("category", pre=True)
    def normalize_category(cls, value):
        return value.strip().lower() if isinstance(value, str) else value

    @root_validator
    def require_receipt(cls, values):
        if values.get("category") == "work" and values.get("amount_cents", 0) > 10000 and not values.get("receipt"):
            raise ValueError("work expenses above 10000 cents require a receipt")
        return values

    class Config:
        allow_population_by_field_name = True
        extra = "forbid"
        orm_mode = True


class ExpensePatch(BaseModel):
    notes: Optional[str]

    class Config:
        extra = "forbid"


class ExpenseRead(ExpenseCreate):
    expense_id: int = Field(alias="expenseId")