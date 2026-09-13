from __future__ import annotations

import subprocess
from pathlib import Path

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
