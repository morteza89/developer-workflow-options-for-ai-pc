from fastapi.testclient import TestClient

from app.routes import app


def test_migration_preserves_patch_presence():
    with TestClient(app) as client:
        assert client.patch("/expenses/preview", json={}).json() == {}
        assert client.patch("/expenses/preview", json={"notes": None}).json() == {"notes": None}


def test_migration_preserves_merchant_coercion():
    with TestClient(app) as client:
        result = client.post("/expenses", json={"externalId": "regression", "merchantCode": 17, "amountCents": 12, "category": "personal"})
        assert result.status_code == 201
        assert result.json()["merchantCode"] == "17"