import pytest
from fastapi.testclient import TestClient

from app.routes import app


@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv("EXPENSE_CURRENCY", raising=False)
    monkeypatch.delenv("EXPENSE_MAX_AMOUNT_CENTS", raising=False)
    with TestClient(app) as session:
        yield session


def payload(**changes):
    return {"externalId": "inv-1", "merchantCode": "shop", "amountCents": 500, "category": "personal", **changes}


def test_startup_settings(client, monkeypatch):
    assert client.get("/health").status_code == 200
    assert client.get("/health").json() == {"status": "ok", "currency": "USD"}
    monkeypatch.setenv("EXPENSE_CURRENCY", "EUR")
    assert client.get("/health").json() == {"status": "ok", "currency": "EUR"}
    monkeypatch.setenv("EXPENSE_MAX_AMOUNT_CENTS", "600")
    assert client.post("/expenses", json=payload(amountCents=601)).status_code == 422
    assert client.post("/expenses", json=payload(amountCents=600)).status_code == 201


@pytest.mark.parametrize("notes", [None, "reviewed", ""])
def test_alias_json_values(client, notes):
    response = client.post("/expenses", json=payload(notes=notes, merchantCode=42, category=" WORK "))
    assert response.status_code == 201
    assert response.json() == payload(notes=notes, merchantCode="42", category="work", receipt=None)
    assert type(response.json()["amountCents"]) is int


def test_field_names_and_omitted_notes(client):
    response = client.post("/expenses", json={"external_id": "internal", "merchant_code": "m", "amount_cents": 1, "category": "personal"})
    assert response.status_code == 201
    assert response.json() == payload(externalId="internal", merchantCode="m", amountCents=1, notes=None, receipt=None)


@pytest.mark.parametrize("changes", [{"amountCents": 0}, {"amountCents": -1}, {"amountCents": 10000001}, {"amountCents": "500"}, {"amountCents": 5.2}, {"amountCents": 5.0}, {"amountCents": 500.0}, {"amountCents": True}, {"category": "travel"}, {"externalId": ""}, {"notes": []}, {"unexpected": 1}])
def test_invalid_inputs(client, changes):
    assert client.post("/expenses", json=payload(**changes)).status_code == 422


@pytest.mark.parametrize("category,normalized", [(" PERSONAL ", "personal"), ("Personal", "personal"), ("\tpersonal\n", "personal"), ("Work", "work"), ("work ", "work"), (" WORK", "work")])
def test_category_normalization(client, category, normalized):
    response = client.post("/expenses", json=payload(category=category))
    assert response.status_code == 201
    assert response.json() == payload(category=normalized, receipt=None, notes=None)


@pytest.mark.parametrize("field", ["externalId", "merchantCode", "amountCents", "category"])
def test_required_fields(client, field):
    body = payload()
    del body[field]
    assert client.post("/expenses", json=body).status_code == 422


@pytest.mark.parametrize("category,amount,receipt,status", [("work", 10000, None, 201), ("work", 10001, None, 422), (" WORK ", 10001, "", 422), ("work", 10001, "R1", 201), ("work", 10001, " ", 201), ("personal", 10001, None, 201), ("personal", 10000000, None, 201)])
def test_receipt_semantics(client, category, amount, receipt, status):
    response = client.post("/expenses", json=payload(category=category, amountCents=amount, receipt=receipt))
    assert response.status_code == status
    if status == 201:
        assert response.json() == payload(category=category.strip().lower(), amountCents=amount, receipt=receipt, notes=None)


@pytest.mark.parametrize("merchant", [0, -1, 123456])
def test_integer_merchant_codes(client, merchant):
    response = client.post("/expenses", json=payload(merchantCode=merchant))
    assert response.status_code == 201
    assert response.json()["merchantCode"] == str(merchant)


@pytest.mark.parametrize("body", [{}, {"notes": None}, {"notes": "changed"}, {"notes": ""}])
def test_patch_presence(client, body):
    response = client.patch("/expenses/preview", json=body)
    assert response.status_code == 200
    assert response.json() == body


def test_patch_unknown_field(client):
    assert client.patch("/expenses/preview", json={"amountCents": 1}).status_code == 422


def test_object_serialization(client):
    response = client.get("/expenses/7")
    assert response.status_code == 200
    body = response.json()
    assert body == {"expenseId": 7, "externalId": "seed-7", "merchantCode": "42", "amountCents": 12500, "category": "work", "receipt": "R-7", "notes": None}
    assert type(body["expenseId"]) is int
    assert type(body["amountCents"]) is int
    assert type(body["merchantCode"]) is str
    assert client.get("/expenses/8").status_code == 404