from conftest import load_fixture
from sv_mcp.formatters.sandbox import format_sandbox, format_sandbox_dataset_state


def test_format_sandbox_happy_path():
    raw = [{"serviceId": 341611, "userId": 12345, "transactionId": 6485927}]
    result = format_sandbox(raw)
    assert len(result) == 1
    s = result[0]
    assert s.serviceId == 341611
    assert s.userId == 12345
    assert s.transactionId == 6485927


def test_format_sandbox_empty_list():
    assert format_sandbox([]) == []


def test_format_sandbox_missing_optional_fields_no_crash():
    raw = [{}]
    result = format_sandbox(raw)
    assert result[0].serviceId is None
    assert result[0].userId is None
    assert result[0].transactionId is None


def test_format_sandbox_dataset_state_happy_path():
    raw = load_fixture("sandbox_dataset_state")
    result = format_sandbox_dataset_state(raw)
    assert len(result) == 1
    models = result[0].models
    assert set(models) == {"orders", "users"}
    assert models["orders"] == raw[0]["models"]["orders"]
    assert models["users"][0] == {"user_id": "u1", "email": "ann@example.com", "active": True}


def test_format_sandbox_dataset_state_empty_list():
    assert format_sandbox_dataset_state([]) == []


def test_format_sandbox_dataset_state_missing_models_no_crash():
    result = format_sandbox_dataset_state([{"trackingId": "uuid-dataset-001", "models": None}])
    assert result[0].models == {}
