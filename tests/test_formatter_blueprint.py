from conftest import load_fixture
from sv_mcp.formatters.blueprint import (
    format_blueprints, format_blueprint_transactions, format_transaction_summaries,
)


def test_format_blueprints_happy_path():
    result = format_blueprints(load_fixture("blueprint"))
    assert len(result) == 1
    b = result[0]
    assert b.id == 42
    assert b.name == "Orders demo"
    assert b.tags == ["stateful", "demo"]
    assert b.scope == "GLOBAL"
    assert b.hasBlazeData is True
    assert b.transactionCount == 1


def test_format_blueprints_transactions_parsed():
    raw = load_fixture("blueprint")
    result = format_blueprints(raw)
    txns = result[0].transactions
    assert len(txns) == 1
    assert txns[0].id == 501
    assert txns[0].name == "create order"
    assert txns[0].actionsData == raw[0]["transactions"][0]["actionsData"]


def test_format_blueprints_missing_transactions_and_tags():
    result = format_blueprints([{"id": 1, "name": "bp"}])
    assert result[0].transactions == []
    assert result[0].tags == []
    assert result[0].hasBlazeData is None


def test_format_blueprints_empty_list():
    assert format_blueprints([]) == []


def test_format_blueprint_transactions_happy_path():
    raw = load_fixture("blueprint_transactions")
    result = format_blueprint_transactions(raw)
    assert len(result) == 2
    t = result[0]
    assert t.id == 501
    assert t.name == "create order"
    assert t.type == "HTTP"
    assert t.description == "Stores a new order"
    assert t.dsl == raw[0]["dsl"]


def test_format_blueprint_transactions_state_update_preserved_verbatim():
    raw = load_fixture("blueprint_transactions")
    result = format_blueprint_transactions(raw)
    action = result[0].actionsData[0]
    assert action == raw[0]["actionsData"][0]
    assert action["actionType"] == "STATE_UPDATE"
    assert action["definition"] == {"opaqueKey": "opaque value", "opaqueNested": {"items": [1, 2]}}


def test_format_blueprint_transactions_sql_hint():
    result = format_blueprint_transactions(load_fixture("blueprint_transactions"))
    assert result[1].sqlHint == "select * from orders where id = ${request.path.1}"
    assert result[0].sqlHint is None


def test_format_blueprint_transactions_missing_actions():
    result = format_blueprint_transactions(load_fixture("blueprint_transactions"))
    assert result[1].actionsData == []


def test_format_blueprint_transactions_reads_transaction_dto_actions():
    actions = [{"id": 1, "name": "a", "actionType": "STATE_UPDATE", "definition": {"opaqueKey": "v"}}]
    result = format_blueprint_transactions([{"id": 7, "name": "t", "actions": actions}])
    assert result[0].actionsData == actions


def test_format_blueprint_transactions_empty_list():
    assert format_blueprint_transactions([]) == []


def test_format_transaction_summaries_happy_path():
    result = format_transaction_summaries(load_fixture("transaction")["http"])
    assert len(result) == 2
    t = result[0]
    assert t.id == 6485927
    assert t.name == "get test"
    assert t.type == "HTTP"
    assert t.serviceId == 341611


def test_format_transaction_summaries_empty_list():
    assert format_transaction_summaries([]) == []


def test_format_blueprint_transactions_decodes_http_body_matchers():
    """Body matchers come back as plain text, like virtual_services_http_transaction read, so the DSL can be
    passed to create without being base64-encoded twice."""
    raw = [{
        "id": 1, "name": "t", "type": "HTTP",
        "dsl": {"requestDsl": {"body": [
            {"key": "body", "matcherName": "equals_json", "matchingValue": "eyJpZCI6IDF9", "sampleBody": "eyJpZCI6IDF9"},
        ]}},
    }]
    matcher = format_blueprint_transactions(raw)[0].dsl["requestDsl"]["body"][0]
    assert matcher["matchingValue"] == '{"id": 1}'
    assert matcher["sampleBody"] == '{"id": 1}'


def test_format_blueprint_transactions_leaves_messaging_dsl_untouched():
    dsl = {"requestDsl": {"body": [{"key": "body", "matcherName": "equals", "matchingValue": "eyJpZCI6IDF9"}]}}
    raw = [{"id": 1, "name": "t", "type": "MESSAGING", "dsl": dsl}]
    matcher = format_blueprint_transactions(raw)[0].dsl["requestDsl"]["body"][0]
    assert matcher["matchingValue"] == "eyJpZCI6IDF9"
