from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SERVICE_DIR = REPO_ROOT


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )


def test_env_example_exists_and_contains_only_sanitized_values():
    env_example = SERVICE_DIR / ".env.example"
    text = env_example.read_text(encoding="utf-8")

    required_blank_keys = {
        "ANTHROPIC_BASE_URL",
        "ANTHROPIC_AUTH_TOKEN",
        "ANTHROPIC_MODEL",
        "AUTORESEARCH_API_TOKEN",
    }
    optional_keys = {
        "OPENAI_BASE_URL",
        "OPENAI_API_KEY",
        "AUTORESEARCH_BIND_HOST",
        "AUTORESEARCH_HOST",
        "AUTORESEARCH_PORT",
        "AUTORESEARCH_CORS_ORIGINS",
        "AUTORESEARCH_MAX_ITERATIONS",
        "AUTORESEARCH_MAX_BUDGET_USD",
        "AUTORESEARCH_TIMEOUT_S",
        "AUTORESEARCH_MAX_CONCURRENT",
        "AUTORESEARCH_WS_MAX_CLIENTS",
        "AUTORESEARCH_LOG_LEVEL",
        "AUTORESEARCH_ITERATION_CONTEXT_ENABLED",
        "AUTORESEARCH_ITERATION_CONTEXT_MAX_CHARS",
        "AUTORESEARCH_ITERATION_CONTEXT_RECENT_ATTEMPTS",
        "AUTORESEARCH_IDENTITY_INTROSPECTION_URL",
        "AUTORESEARCH_IDENTITY_INTROSPECTION_TIMEOUT_S",
        "AUTORESEARCH_PROMETHEUS_TOKEN",
        "AUTORESEARCH_MLFLOW_TRACKING_URI",
        "AUTORESEARCH_MLFLOW_EXTERNAL_URL",
        "AUTORESEARCH_PREFLIGHT_ENABLED",
        "AUTORESEARCH_ALLOW_UNREADY_SERVICES",
        "AUTORESEARCH_PREFLIGHT_TIMEOUT_S",
    }

    values = {}
    for line in text.splitlines():
        if not line or line.startswith("#"):
            continue
        key, _, value = line.partition("=")
        values[key] = value

    assert required_blank_keys <= values.keys()
    assert optional_keys <= values.keys()
    assert all(values[key] == "" for key in required_blank_keys)

    forbidden_literals = (
        "sk-ant-",
        "traid_secure_2024",
        "redis_secure_2024",
        "secure_password_2024",
        "demo_secret",
        "myroot",
        "minio_root_password",
        "aws_secret_access_key",
    )
    lowered = text.lower()
    assert all(secret not in lowered for secret in forbidden_literals)


def test_autoresearch_ui_build_inputs_are_tracked_and_outputs_ignored():
    tracked_inputs = (
        "ui/package.json",
        "ui/package-lock.json",
        "ui/src/App.tsx",
    )
    for path in tracked_inputs:
        result = _git("ls-files", "--error-unmatch", path)
        assert result.returncode == 0, result.stderr

    assert _git("check-ignore", "-q", ".env").returncode == 0
    assert _git("check-ignore", "-q", ".env.example").returncode == 1
    assert _git("check-ignore", "-q", "ui/node_modules").returncode == 0
    assert _git("check-ignore", "-q", "ui/dist").returncode == 0


def test_autoresearch_backend_uses_src_layout_and_committed_lockfile():
    assert (SERVICE_DIR / "src" / "main.py").exists()
    assert not (SERVICE_DIR / "server").exists()
    assert (SERVICE_DIR / "poetry.lock").exists()

    result = _git("check-ignore", "-q", "poetry.lock")
    assert result.returncode == 1


def test_autoresearch_dockerfile_matches_standalone_runtime_contract():
    dockerfile = (SERVICE_DIR / "Dockerfile").read_text(encoding="utf-8")

    assert "poetry lock" not in dockerfile
    assert "|| true" not in dockerfile
    assert "2>/dev/null" not in dockerfile
    assert "src/ /app/src/" in dockerfile
    assert 'CMD ["uvicorn", "src.main:app"' in dockerfile
    # Non-root user creation. UID/GID are parameterized via APP_UID/APP_GID
    # build args (defaulting to 1000 to match the host user that owns
    # bind-mounted workspace content, so promotion can write atomic temp
    # and rollback files there).
    assert "ARG APP_UID=" in dockerfile
    assert "ARG APP_GID=" in dockerfile
    assert "groupadd -g ${APP_GID} appuser" in dockerfile
    assert "useradd -u ${APP_UID} -g appuser -m appuser" in dockerfile
    # No vendored platform path dependencies should be copied anymore.
    assert "/app/libs" not in dockerfile
    assert "traid_training_sdk" not in dockerfile
    assert "skills/ /app/skills/" in dockerfile
    assert '"--workers", "1"' in dockerfile


def test_autoresearch_deployment_documents_single_instance_constraint():
    readme = (SERVICE_DIR / "README.md").read_text(encoding="utf-8")

    assert "single-instance SQLite" in readme


def test_readme_uses_tracked_env_template_without_token_samples():
    readme = (SERVICE_DIR / "README.md").read_text(encoding="utf-8")

    assert "cp .env.example .env" in readme
    assert "`.env` is intentionally ignored by git" in readme
    assert "sk-ant-" not in readme
    assert "traid_secure_2024" not in readme
    assert "package-lock.json" in readme
    assert "ui/node_modules/" in readme
    assert "ui/dist/" in readme


def test_settings_initializes_in_demo_mode_without_credentials(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_BASE_URL", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    from src.config import Settings

    s = Settings(demo_mode=True)
    assert s.demo_mode is True
    assert s.anthropic_base_url == ""
    assert s.anthropic_auth_token is None


DEFAULT_POSTGRES_DSN = "postgresql://autoresearch:autoresearch@postgres:5432/autoresearch"


def test_compose_uses_unset_only_database_default_and_loopback_binding():
    compose = yaml.safe_load((REPO_ROOT / "docker-compose.yml").read_text())
    service = compose["services"]["autoresearch"]
    assert service["environment"]["AUTORESEARCH_DATABASE_URL"] == (
        "${AUTORESEARCH_DATABASE_URL-" + DEFAULT_POSTGRES_DSN + "}"
    )
    assert service["ports"] == [
        "${AUTORESEARCH_BIND_HOST:-127.0.0.1}:${AUTORESEARCH_PORT:-8030}:8000"
    ]
    assert "ports" not in compose["services"]["postgres"]


@pytest.mark.parametrize(
    ("dotenv_dsn", "shell_dsn", "expected"),
    [
        (None, None, DEFAULT_POSTGRES_DSN),
        ("", None, ""),
        ("postgresql://custom/db", None, "postgresql://custom/db"),
        ("postgresql://custom/db", "", ""),
        ("", "postgresql://shell/db", "postgresql://shell/db"),
    ],
)
def test_compose_resolves_database_overrides(tmp_path, dotenv_dsn, shell_dsn, expected):
    """Render with Compose itself (no daemon, containers or network required)."""
    if shutil.which("docker") is None:
        pytest.skip("Docker Compose is not installed")
    version = subprocess.run(["docker", "compose", "version"], capture_output=True)
    if version.returncode:
        pytest.skip("Docker Compose plugin is not installed")
    compose_file = tmp_path / "compose.yml"
    shutil.copyfile(REPO_ROOT / "docker-compose.yml", compose_file)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "" if dotenv_dsn is None else f"AUTORESEARCH_DATABASE_URL={dotenv_dsn}\n"
    )
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("AUTORESEARCH_", "COMPOSE_"))
    }
    if shell_dsn is not None:
        env["AUTORESEARCH_DATABASE_URL"] = shell_dsn
    result = subprocess.run(
        [
            "docker", "compose", "--env-file", str(env_file),
            "-f", str(compose_file), "config", "--format", "json",
        ],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    service = json.loads(result.stdout)["services"]["autoresearch"]
    assert service["environment"]["AUTORESEARCH_DATABASE_URL"] == expected
    assert service["ports"][0]["host_ip"] == "127.0.0.1"
    assert str(service["ports"][0]["published"]) == "8030"


def test_explicit_empty_database_url_selects_sqlite(monkeypatch):
    from src.config import Settings
    from src.core.postgres_state_store import is_postgres_dsn

    monkeypatch.setenv("AUTORESEARCH_DATABASE_URL", "")
    settings = Settings(demo_mode=True, _env_file=None)
    assert settings.database_url == ""
    assert not is_postgres_dsn(settings.database_url)

