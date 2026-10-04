import json

import pytest

import sv_mcp.main as main
from sv_mcp.config.token import BzmToken, BzmTokenError

SECRET = "s3cr3t-value-never-printed"


@pytest.fixture(autouse=True)
def clean_state(monkeypatch, tmp_path):
    monkeypatch.delenv("API_KEY_ID", raising=False)
    monkeypatch.delenv("API_KEY_SECRET", raising=False)
    monkeypatch.chdir(tmp_path)  # no api-key.json in the working directory
    monkeypatch.setattr(main, "__executable__", str(tmp_path / "bin" / "sv-mcp"))
    monkeypatch.setattr(main, "_reported_key_problems", set())
    BzmToken.from_file.cache_clear()


def _key_file(tmp_path, content: str):
    path = tmp_path / "keys.json"
    path.write_text(content)
    return path


def test_arguments_take_priority_and_name_their_source(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "BLAZEMETER_API_KEY_FILE_PATH", str(_key_file(tmp_path, "{}")))
    token = main.get_token("id", SECRET)
    assert token.source == "--api-key-id/--api-key-secret arguments"


def test_key_file_names_its_source(monkeypatch, tmp_path):
    path = _key_file(tmp_path, json.dumps({"id": "id", "secret": SECRET}))
    monkeypatch.setattr(main, "BLAZEMETER_API_KEY_FILE_PATH", str(path))
    assert main.get_token().source == f"key file {path}"


@pytest.mark.parametrize("content, reason", [
    ("{not json " + SECRET, "invalid JSON at line 1"),
    (json.dumps({"id": "id"}), "Missing field 'secret'"),
    (json.dumps({"id": "id", "secret": 12345}), "Invalid Token secret"),
])
def test_bad_key_file_is_reported_on_stderr_without_values(monkeypatch, tmp_path, capsys, content, reason):
    monkeypatch.setattr(main, "BLAZEMETER_API_KEY_FILE_PATH", str(_key_file(tmp_path, content)))
    assert main.get_token() is None
    err = capsys.readouterr().err
    assert "key file not used" in err
    assert reason in err
    assert SECRET not in err
    assert "12345" not in err


def test_missing_key_file_is_reported(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(main, "BLAZEMETER_API_KEY_FILE_PATH", str(tmp_path / "absent.json"))
    assert main.get_token() is None
    assert "File does not exist" in capsys.readouterr().err


def test_bad_key_file_falls_back_to_environment(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(main, "BLAZEMETER_API_KEY_FILE_PATH", str(tmp_path / "absent.json"))
    monkeypatch.setenv("API_KEY_ID", "id")
    monkeypatch.setenv("API_KEY_SECRET", SECRET)
    token = main.get_token()
    assert token.source == "API_KEY_ID/API_KEY_SECRET environment variables"
    assert SECRET not in capsys.readouterr().err


def test_each_problem_is_reported_once(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(main, "BLAZEMETER_API_KEY_FILE_PATH", str(tmp_path / "absent.json"))
    main.get_token()
    main.get_token()
    assert capsys.readouterr().err.count("key file not used") == 1


def test_token_errors_do_not_echo_values():
    with pytest.raises(BzmTokenError) as excinfo:
        BzmToken("id", 12345)
    assert "12345" not in str(excinfo.value)
