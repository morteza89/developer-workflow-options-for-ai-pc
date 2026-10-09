import ast
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.routing import APIRoute
from pydantic import BaseModel, ValidationError
from pydantic_settings import BaseSettings
from fastapi.testclient import TestClient

from app import schemas, settings
from app.routes import app


def test_native_models_and_attribute_loading():
    for model in (schemas.ExpenseCreate, schemas.ExpensePatch, schemas.ExpenseRead):
        assert issubclass(model, BaseModel)
    assert issubclass(settings.Settings, BaseSettings)
    for amount in (1, 8765):
        record = SimpleNamespace(expense_id=91, external_id="dynamic", merchant_code="m", amount_cents=amount, category="personal", receipt=None, notes="saved")
        result = schemas.ExpenseRead.model_validate(record, from_attributes=True).model_dump(by_alias=True)
        assert result["expenseId"] == 91
        assert result["amountCents"] == amount
        assert result["notes"] == "saved"


def test_positive_settings_limit(monkeypatch):
    monkeypatch.setenv("EXPENSE_MAX_AMOUNT_CENTS", "0")
    with pytest.raises(ValidationError):
        settings.Settings()


def test_routes_keep_model_boundaries_and_load_runtime_attributes(monkeypatch):
    routes = {route.path: route for route in app.routes if isinstance(route, APIRoute)}
    assert routes["/expenses"].dependant.body_params[0].type_ is schemas.ExpenseCreate
    assert routes["/expenses/preview"].dependant.body_params[0].type_ is schemas.ExpensePatch

    original = schemas.ExpenseRead.model_validate.__func__

    def validate_runtime_record(model, record, *args, **kwargs):
        record.external_id = "runtime-loaded"
        return original(model, record, *args, **kwargs)

    monkeypatch.setattr(schemas.ExpenseRead, "model_validate", classmethod(validate_runtime_record))
    with TestClient(app) as client:
        response = client.get("/expenses/7")
    assert response.status_code == 200
    assert response.json()["externalId"] == "runtime-loaded"


def test_no_legacy_api():
    root = Path(schemas.__file__).parent
    forbidden_names = {"validator", "root_validator"}
    forbidden_methods = {"dict", "json", "parse_obj", "parse_raw", "parse_file", "from_orm", "construct", "model_construct"}
    for path in root.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert not (node.module or "").startswith(("pydantic.v1", "pydantic.deprecated"))
                assert not any(alias.name in forbidden_names for alias in node.names)
                if node.module == "pydantic":
                    assert not any(alias.name == "v1" for alias in node.names)
            if isinstance(node, ast.Import):
                assert not any(alias.name.startswith(("pydantic.v1", "pydantic.deprecated")) for alias in node.names)
            if isinstance(node, ast.ClassDef) and node.name in {"ExpenseCreate", "ExpensePatch", "ExpenseRead", "Settings"}:
                assert not any(isinstance(child, ast.ClassDef) and child.name == "Config" for child in node.body)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                assert node.func.attr != "model_construct"
                if isinstance(node.func.value, ast.Name) and node.func.value.id in {"expense", "ExpenseCreate", "ExpensePatch", "ExpenseRead", "Settings"}:
                    assert node.func.attr not in forbidden_methods | forbidden_names