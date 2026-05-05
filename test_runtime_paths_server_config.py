import json

from gear_xls.runtime_paths import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    get_schedule_url,
    get_server_base_url,
    get_server_health_url,
    load_server_config,
)


def _write_server_config(root, payload):
    config_dir = root / "gear_xls" / "config"
    config_dir.mkdir(parents=True)
    (config_dir / "server.json").write_text(
        json.dumps(payload),
        encoding="utf-8",
    )


def test_server_config_defaults_to_public_5000(tmp_path):
    assert load_server_config(str(tmp_path)) == {
        "host": DEFAULT_HOST,
        "port": DEFAULT_PORT,
    }
    assert get_server_base_url(str(tmp_path)) == "http://127.0.0.1:5000"


def test_server_config_reads_per_project_port(tmp_path):
    _write_server_config(tmp_path, {"host": "127.0.0.1", "port": 5001})

    assert load_server_config(str(tmp_path)) == {"host": "127.0.0.1", "port": 5001}
    assert get_schedule_url(str(tmp_path)) == "http://127.0.0.1:5001/schedule"
    assert get_server_health_url(str(tmp_path)) == "http://127.0.0.1:5001/health"


def test_server_config_env_override_is_explicit(tmp_path, monkeypatch):
    _write_server_config(tmp_path, {"host": "0.0.0.0", "port": 5000})
    monkeypatch.setenv("HOST", "127.0.0.1")
    monkeypatch.setenv("PORT", "5002")

    assert load_server_config(str(tmp_path)) == {"host": "0.0.0.0", "port": 5000}
    assert load_server_config(str(tmp_path), include_env=True) == {
        "host": "127.0.0.1",
        "port": 5002,
    }
