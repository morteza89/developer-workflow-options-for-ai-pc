from fastapi.testclient import TestClient

from app.routes import app


def test_service():
    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "ok", "currency": "USD"}
        response = client.post("/expenses", json={"externalId": "one", "merchantCode": 42, "amountCents": 500, "category": " WORK "})
        assert response.status_code == 201
        assert response.json()["merchantCode"] == "42"
        assert response.json()["notes"] is None
        assert client.patch("/expenses/preview", json={}).json() == {}
        assert client.patch("/expenses/preview", json={"notes": None}).json() == {"notes": None}
        assert client.get("/expenses/7").json()["expenseId"] == 7