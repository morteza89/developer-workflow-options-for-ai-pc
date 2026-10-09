from types import SimpleNamespace

from fastapi import FastAPI, HTTPException

from app.schemas import ExpenseCreate, ExpensePatch, ExpenseRead
from app.settings import Settings

app = FastAPI()


@app.get("/health")
def health():
    return {"status": "ok", "currency": Settings().currency}


@app.post("/expenses", status_code=201)
def create_expense(expense: ExpenseCreate):
    if expense.amount_cents > Settings().max_amount_cents:
        raise HTTPException(status_code=422, detail="amount exceeds configured limit")
    return expense.model_dump(by_alias=True)


@app.patch("/expenses/preview")
def patch_expense(expense: ExpensePatch):
    return expense.model_dump(exclude_unset=True)


@app.get("/expenses/{expense_id}")
def read_expense(expense_id: int):
    if expense_id != 7:
        raise HTTPException(status_code=404, detail="expense not found")
    record = SimpleNamespace(expense_id=7, external_id="seed-7", merchant_code="42", amount_cents=12500, category="work", receipt="R-7", notes=None)
    return ExpenseRead.model_validate(record).model_dump(by_alias=True)