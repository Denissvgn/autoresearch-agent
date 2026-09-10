from __future__ import annotations

import base64
import logging
import os
from pathlib import Path

import pytest
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.testclient import TestClient

try:
    from starlette.testclient import WebSocketDenialResponse
except ImportError:  # Starlette <0.37 closes denied sockets instead.
    WebSocketDenialResponse = None

os.environ.setdefault("ANTHROPIC_BASE_URL", "http://anthropic.invalid")
os.environ.setdefault("ANTHROPIC_AUTH_TOKEN", "test-token")

from src.api import auth as auth_module
from src.api import promotion, research, results
from src.api.auth import require_websocket_auth
from src.config import Settings, settings

API_TOKEN = "test-autoresearch-token"


def create_test_app() -> FastAPI:
    app = FastAPI()
    app.state.audit_store = getattr(research, "_store", None)
    for prefix in ("/api/v1", "/api"):
        app.include_router(research.router, prefix=prefix)
        app.include_router(results.router, prefix=prefix)
        app.include_router(promotion.router, prefix=prefix)

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": settings.service_name}

    @app.websocket("/ws/events")
    async def websocket_events(websocket: WebSocket):
        actor = await require_websocket_auth(websocket)
        if actor is None:
            return
        await websocket.accept(subprotocol=actor.websocket_subprotocol)
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            return

    return app


class FakeSessionManager:
    active_count = 0
    _active_pipelines: dict[str, object] = {}

    async def start_session(self, **kwargs):
        return {"id": "res_auth", "status": "running", **kwargs}

    async def start_pipeline(self, **kwargs):
        return {"id": "pipe_auth", "status": "running", **kwargs}

    async def stop_session(self, research_id: str):
        return research_id == "res_auth"

    async def stop_pipeline(self, pipeline_id: str):
        return pipeline_id == "pipe_auth"

    async def pause_session(self, research_id: str):
        return research_id == "res_auth"

    async def resume_session(self, research_id: str):
        return research_id == "res_auth"

    async def continue_session(self, research_id: str, **kwargs):
        return {"id": "res_auth_continued", "resumed_from": research_id, **kwargs}

    async def resume_interrupted_session(self, research_id: str, **kwargs):
        return {"id": "res_auth_runtime_resumed", "resumed_from": research_id, **kwargs}

    async def continue_pipeline(self, pipeline_id: str, **kwargs):
        return {"id": "pipe_auth_continued", "resumed_from": pipeline_id, **kwargs}

    def is_running(self, research_id: str):
        return False


class FakeStore:
    def __init__(self) -> None:
        self.audit_events: list[dict] = []
        self.idempotency_records: dict[tuple[str, str, str], dict] = {}

    async def list_sessions(self, **kwargs):
        return []

    async def count_sessions(self, **kwargs):
        return 0

    async def get_pipeline(self, pipeline_id: str):
        return None

    async def get_session(self, research_id: str):
        if research_id != "res_auth":
            return None
        return {
            "id": "res_auth",
            "instrument": "DOGE_USDT",
            "timeframe": "15m",
            "model_type": "direction",
            "workspace_path": "/tmp/res_auth",
            "status": "completed",
        }

    async def get_iterations(self, research_id: str):
        return []

    async def get_best_iteration(self, research_id: str):
        return None

    async def get_hpo_studies(self, research_id: str):
        return []

    async def get_planned_trials(self, research_id: str):
        return []

    async def list_promotions(self):
        return []

    async def list_pipelines(self, **kwargs):
        return []

    async def delete_session(self, research_id: str):
        return research_id == "res_auth"

    async def record_audit_event(self, **kwargs):
        event = {
            "event_id": f"aud_fake_{len(self.audit_events) + 1}",
            "timestamp": "2026-04-29T00:00:00+00:00",
            **kwargs,
        }
        self.audit_events.append(event)
        return event

    async def begin_idempotency_record(
        self,
        *,
        operation: str,
        parent_id: str,
        key_hash: str,
        request_hash: str,
    ):
        key = (operation, parent_id, key_hash)
        existing = self.idempotency_records.get(key)
        if existing:
            return dict(existing)
        self.idempotency_records[key] = {
            "operation": operation,
            "parent_id": parent_id,
            "key_hash": key_hash,
            "request_hash": request_hash,
            "status": "running",
            "response_json": None,
        }
        return None

    async def complete_idempotency_record(
        self,
        *,
        operation: str,
        parent_id: str,
        key_hash: str,
        child_id: str | None,
        response: dict,
    ):
        import json

        key = (operation, parent_id, key_hash)
        self.idempotency_records[key].update(
            {
                "status": "completed",
                "child_id": child_id,
                "response_json": json.dumps(response, sort_keys=True),
            }
        )

    async def delete_idempotency_record(
        self,
        *,
        operation: str,
        parent_id: str,
        key_hash: str,
    ):
        self.idempotency_records.pop((operation, parent_id, key_hash), None)

    async def list_audit_events(
        self,
        *,
        limit: int = 100,
        action: str | None = None,
        research_id: str | None = None,
        pipeline_id: str | None = None,
    ):
        events = self.audit_events
        if action:
            events = [event for event in events if event.get("action") == action]
        if research_id:
            events = [event for event in events if event.get("research_id") == research_id]
        if pipeline_id:
            events = [event for event in events if event.get("pipeline_id") == pipeline_id]
        return list(reversed(events))[:limit]


class FakePromoter:
    async def preview(self, research_id: str, **kwargs):
        if research_id == "missing":
            raise ValueError("No promotable iteration found")
        return {"research_id": research_id, "preview": True, **kwargs}

    async def confirm(self, research_id: str, **kwargs):
        if research_id == "missing":
            raise ValueError("No promotable iteration found")
        return {"research_id": research_id, "confirmed": True, **kwargs}

    async def rollback(
        self,
        *,
        model_type: str,
        instrument: str,
        timeframe: str,
        reason: str | None = None,
    ):
        if instrument == "MISSING":
            raise ValueError("No development promotion found")
        return {
            "model_type": model_type,
            "instrument": instrument,
            "timeframe": timeframe,
            "reason": reason,
            "rolled_back": True,
        }


@pytest.fixture(autouse=True)
def configure_api_auth(monkeypatch):
    monkeypatch.setattr(settings, "autoresearch_api_token", API_TOKEN)

    async def fake_inactive_introspection(base_url: str, token: str, timeout: float):
        return {"active": False}

    monkeypatch.setattr(auth_module, "introspect_token", fake_inactive_introspection)
    store = FakeStore()
    research.init(FakeSessionManager(), store)
    results.init(store)
    promotion.init(FakePromoter(), store)
    return store


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_test_app())


def auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {API_TOKEN}"}


def start_payload() -> dict[str, object]:
    return {
        "instrument": "DOGE_USDT",
        "timeframe": "15m",
        "model_type": "direction",
    }


def test_health_is_public_but_api_routes_require_bearer_token(client: TestClient):
    assert client.get("/health").status_code == 200

    checks = [
        ("post", "/api/research/start", {"json": start_payload()}),
        ("post", "/api/research/res_auth/stop", {}),
        ("get", "/api/research/res_auth/results", {}),
        ("post", "/api/research/res_auth/promote/preview", {}),
        ("post", "/api/research/res_auth/promote/confirm", {}),
        (
            "post",
            "/api/research/res_auth/runtime-resume",
            {"json": {"reason": "auth test"}},
        ),
        (
            "post",
            "/api/promotions/direction/DOGE_USDT/15m/rollback",
            {"json": {"reason": "auth test"}},
        ),
    ]

    for method, path, kwargs in checks:
        response = getattr(client, method)(path, **kwargs)
        assert response.status_code == 401, path
        assert response.headers["www-authenticate"] == "Bearer"


def test_authenticated_api_calls_preserve_existing_behavior(client: TestClient):
    assert (
        client.post(
            "/api/research/start",
            json=start_payload(),
            headers=auth_headers(),
        ).status_code
        == 201
    )

    stop = client.post("/api/research/res_auth/stop", headers=auth_headers())
    assert stop.status_code == 200
    assert stop.json()["status"] == "stop_requested"

    results_response = client.get("/api/research/res_auth/results", headers=auth_headers())
    assert results_response.status_code == 200
    assert results_response.json()["iterations"] == []

    preview = client.post("/api/research/res_auth/promote/preview", headers=auth_headers())
    assert preview.status_code == 200
    assert preview.json()["preview"] is True

    confirm = client.post("/api/research/res_auth/promote/confirm", headers=auth_headers())
    assert confirm.status_code == 200
    assert confirm.json()["confirmed"] is True

    runtime_resume = client.post(
        "/api/research/res_auth/runtime-resume",
        json={"reason": "operator reviewed recovery state"},
        headers={**auth_headers(), "Idempotency-Key": "runtime-resume-auth"},
    )
    assert runtime_resume.status_code == 201
    assert runtime_resume.json()["id"] == "res_auth_runtime_resumed"

    rollback = client.post(
        "/api/promotions/direction/DOGE_USDT/15m/rollback",
        json={"reason": "auth test"},
        headers=auth_headers(),
    )
    assert rollback.status_code == 200
    assert rollback.json()["rolled_back"] is True


def test_api_v1_and_legacy_api_prefixes_are_both_protected(client: TestClient):
    for prefix in ("/api/v1", "/api"):
        missing_auth = client.get(f"{prefix}/research")
        assert missing_auth.status_code == 401

        response = client.get(f"{prefix}/research", headers=auth_headers())
        assert response.status_code == 200
        assert response.json()["items"] == []


def test_continue_requires_and_replays_idempotency_key(client: TestClient):
    missing = client.post(
        "/api/research/res_auth/continue",
        headers=auth_headers(),
    )
    assert missing.status_code == 400

    headers = {**auth_headers(), "Idempotency-Key": "continue-key"}
    first = client.post(
        "/api/research/res_auth/continue",
        json={"max_iterations": 7},
        headers=headers,
    )
    replay = client.post(
        "/api/research/res_auth/continue",
        json={"max_iterations": 7},
        headers=headers,
    )
    conflict = client.post(
        "/api/research/res_auth/continue",
        json={"max_iterations": 8},
        headers=headers,
    )

    assert first.status_code == 201
    assert replay.status_code == 201
    assert replay.json() == first.json()
    assert conflict.status_code == 409


def test_state_changing_research_requests_write_audit_events(
    client: TestClient,
    configure_api_auth: FakeStore,
):
    start = client.post(
        "/api/research/start",
        json=start_payload(),
        headers=auth_headers(),
    )
    assert start.status_code == 201
    assert len(configure_api_auth.audit_events) == 1
    event = configure_api_auth.audit_events[-1]
    assert event["action"] == "research.start"
    assert event["outcome"] == "success"
    assert event["research_id"] == "res_auth"
    assert event["actor_id"].startswith("token_sha256:")
    assert API_TOKEN not in str(event)

    missing = client.post("/api/research/missing/stop", headers=auth_headers())
    assert missing.status_code == 404
    assert len(configure_api_auth.audit_events) == 2
    event = configure_api_auth.audit_events[-1]
    assert event["action"] == "research.stop"
    assert event["outcome"] == "failure"
    assert event["research_id"] == "missing"
    assert "not found" in event["error_message"].lower()


def test_recent_audit_events_endpoint_returns_filtered_events(
    client: TestClient,
    configure_api_auth: FakeStore,
):
    client.post(
        "/api/research/start",
        json=start_payload(),
        headers=auth_headers(),
    )
    client.post("/api/research/missing/stop", headers=auth_headers())

    response = client.get(
        "/api/audit-events",
        params={"action": "research.stop", "research_id": "missing"},
        headers=auth_headers(),
    )

    assert response.status_code == 200
    events = response.json()
    assert len(events) == 1
    assert events[0]["action"] == "research.stop"
    assert events[0]["outcome"] == "failure"
    assert events[0]["research_id"] == "missing"
    assert len(configure_api_auth.audit_events) == 2


def test_promotion_and_rollback_failures_write_audit_events(
    client: TestClient,
    configure_api_auth: FakeStore,
):
    confirm = client.post(
        "/api/research/missing/promote/confirm",
        headers=auth_headers(),
    )
    assert confirm.status_code == 400

    rollback = client.post(
        "/api/promotions/direction/MISSING/15m/rollback",
        json={"reason": "audit failure"},
        headers=auth_headers(),
    )
    assert rollback.status_code == 400

    events = configure_api_auth.audit_events
    assert [(event["action"], event["outcome"]) for event in events] == [
        ("promotion.confirm", "failure"),
        ("promotion.rollback", "failure"),
    ]
    assert all(API_TOKEN not in str(event) for event in events)


def test_rejected_api_auth_records_audit_fingerprint_not_token(
    client: TestClient,
    configure_api_auth: FakeStore,
):
    response = client.post(
        "/api/research/start",
        json=start_payload(),
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert response.status_code == 401

    assert len(configure_api_auth.audit_events) == 1
    event = configure_api_auth.audit_events[0]
    assert event["action"] == "auth.reject"
    assert event["outcome"] == "failure"
    assert event["actor_id"].startswith("token_sha256:")
    assert "wrong-token" not in str(event)


def test_rejected_api_auth_warns_when_audit_store_missing(caplog):
    app = FastAPI()
    app.include_router(research.router, prefix="/api")
    local_client = TestClient(app)

    with caplog.at_level(logging.WARNING):
        response = local_client.get(
            "/api/research",
            headers={"Authorization": "Bearer wrong-token"},
        )

    assert response.status_code == 401
    assert "could not be audited" in caplog.text
    assert "wrong-token" not in caplog.text


def test_identity_jwt_admin_token_is_accepted(
    client: TestClient,
    configure_api_auth: FakeStore,
    monkeypatch,
):
    monkeypatch.setattr(
        settings, "identity_introspection_url", "http://idp.invalid/introspect"
    )

    async def fake_introspect_token(endpoint_url: str, token: str, timeout: float):
        assert endpoint_url == settings.identity_introspection_url
        assert token == "jwt-admin-token"
        assert timeout == settings.identity_introspection_timeout_s
        return {
            "active": True,
            "sub": "user-123",
            "username": "ml-admin",
            "roles": ["ml_admin"],
            "is_admin": False,
        }

    monkeypatch.setattr(auth_module, "introspect_token", fake_introspect_token)

    response = client.post(
        "/api/research/start",
        json=start_payload(),
        headers={"Authorization": "Bearer jwt-admin-token"},
    )

    assert response.status_code == 201
    event = configure_api_auth.audit_events[-1]
    assert event["actor_id"] == "identity:user-123"
    assert event["request_metadata"]["auth_mechanism"] == "bearer:identity-jwt"


def test_identity_jwt_without_admin_role_is_rejected(
    client: TestClient,
    configure_api_auth: FakeStore,
    monkeypatch,
):
    monkeypatch.setattr(
        settings, "identity_introspection_url", "http://idp.invalid/introspect"
    )

    async def fake_introspect_token(endpoint_url: str, token: str, timeout: float):
        return {
            "active": True,
            "sub": "user-456",
            "username": "viewer",
            "roles": ["viewer"],
            "is_admin": False,
        }

    monkeypatch.setattr(auth_module, "introspect_token", fake_introspect_token)

    response = client.post(
        "/api/research/start",
        json=start_payload(),
        headers={"Authorization": "Bearer jwt-viewer-token"},
    )

    assert response.status_code == 403
    assert len(configure_api_auth.audit_events) == 1
    event = configure_api_auth.audit_events[0]
    assert event["action"] == "auth.reject"
    assert event["outcome"] == "failure"
    assert event["request_metadata"]["status_code"] == 403


def test_websocket_requires_authentication(client: TestClient):
    with pytest.raises(Exception) as exc:
        with client.websocket_connect("/ws/events"):
            pass

    if WebSocketDenialResponse is not None and isinstance(exc.value, WebSocketDenialResponse):
        assert exc.value.status_code == 401
        assert exc.value.headers["www-authenticate"] == "Bearer"
    else:
        assert isinstance(exc.value, WebSocketDisconnect)
        assert exc.value.code == 1008


def test_websocket_accepts_authorization_header(client: TestClient):
    with client.websocket_connect("/ws/events", headers=auth_headers()):
        pass


def test_websocket_accepts_identity_jwt_header(client: TestClient, monkeypatch):
    monkeypatch.setattr(
        settings, "identity_introspection_url", "http://idp.invalid/introspect"
    )

    async def fake_introspect_token(endpoint_url: str, token: str, timeout: float):
        return {
            "active": True,
            "sub": "user-ws",
            "username": "ws-admin",
            "roles": ["admin"],
        }

    monkeypatch.setattr(auth_module, "introspect_token", fake_introspect_token)

    with client.websocket_connect(
        "/ws/events",
        headers={"Authorization": "Bearer jwt-websocket-token"},
    ):
        pass


def test_websocket_accepts_browser_subprotocol_token(client: TestClient):
    encoded = base64.urlsafe_b64encode(API_TOKEN.encode("utf-8")).decode("ascii").rstrip("=")
    protocol = f"autoresearch.token.{encoded}"

    with client.websocket_connect("/ws/events", subprotocols=[protocol]) as websocket:
        assert websocket.accepted_subprotocol == protocol


def test_default_cors_origins_are_local_not_wildcard(monkeypatch):
    for key in ("AUTORESEARCH_CORS_ORIGINS", "CORS_ORIGINS_RAW", "CORS_ORIGINS"):
        monkeypatch.delenv(key, raising=False)

    cfg = Settings(
        anthropic_base_url="http://anthropic.invalid",
        anthropic_auth_token="test-token",
    )

    assert "*" not in cfg.cors_origins
    assert "http://localhost:8030" in cfg.cors_origins
    assert "http://localhost:5173" in cfg.cors_origins


def test_settings_accept_canonical_autoresearch_aliases(monkeypatch):
    env_values = {
        "AUTORESEARCH_WORKSPACE_ROOT": "/custom/workspace",
        "AUTORESEARCH_HOST_CONFIGS_PATH": "/custom/configs",
        "AUTORESEARCH_MAX_ITERATIONS": "7",
        "AUTORESEARCH_MAX_BUDGET_USD": "3.25",
        "AUTORESEARCH_TIMEOUT_S": "42",
        "AUTORESEARCH_DEFAULT_QUICK_MODE": "false",
        "AUTORESEARCH_MAX_CONCURRENT": "4",
        "AUTORESEARCH_LOG_LEVEL": "DEBUG",
        "AUTORESEARCH_IDENTITY_SERVICE_URL": "http://identity:8000",
    }
    for key, value in env_values.items():
        monkeypatch.setenv(key, value)

    cfg = Settings(
        anthropic_base_url="http://anthropic.invalid",
        anthropic_auth_token="test-token",
    )

    assert cfg.workspace_root == "/custom/workspace"
    assert cfg.host_configs_path == "/custom/configs"
    assert cfg.max_iterations == 7
    assert cfg.max_budget_usd == 3.25
    assert cfg.experiment_timeout_s == 42
    assert cfg.default_quick_mode is False
    assert cfg.max_concurrent_sessions == 4
    assert cfg.log_level == "DEBUG"
    assert cfg.identity_introspection_url == "http://identity:8000"


def test_settings_keep_bare_env_fallbacks(monkeypatch):
    for key in ("AUTORESEARCH_MAX_ITERATIONS", "AUTORESEARCH_WORKSPACE_ROOT"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("MAX_ITERATIONS", "11")
    monkeypatch.setenv("WORKSPACE_ROOT", "/legacy/workspace")

    cfg = Settings(
        anthropic_base_url="http://anthropic.invalid",
        anthropic_auth_token="test-token",
    )

    assert cfg.max_iterations == 11
    assert cfg.workspace_root == "/legacy/workspace"


def test_identity_introspection_defaults_to_disabled(monkeypatch):
    for key in (
        "AUTORESEARCH_IDENTITY_INTROSPECTION_URL",
        "AUTORESEARCH_IDENTITY_SERVICE_URL",
        "IDENTITY_SERVICE_URL",
    ):
        monkeypatch.delenv(key, raising=False)

    cfg = Settings(
        anthropic_base_url="http://anthropic.invalid",
        anthropic_auth_token="test-token",
    )

    assert cfg.identity_introspection_url == ""


def test_sensitive_settings_do_not_leak_in_repr():
    cfg = Settings(
        anthropic_base_url="http://anthropic.invalid",
        anthropic_auth_token="super-secret-anthropic",
        autoresearch_api_token="super-secret-api",
        autoresearch_prometheus_token="super-secret-prometheus",
        _env_file=None,
    )

    rendered = repr(cfg)
    assert "super-secret-anthropic" not in rendered
    assert "super-secret-api" not in rendered
    assert "super-secret-prometheus" not in rendered


def test_compose_binds_autoresearch_port_to_loopback_by_default():
    repo_root = Path(__file__).resolve().parents[1]
    compose_path = repo_root / "compose" / "autoresearch.yml"
    if not compose_path.exists():
        pytest.skip("platform compose file not present in this checkout")
    compose_text = compose_path.read_text(encoding="utf-8")

    assert "${AUTORESEARCH_BIND_HOST:-127.0.0.1}:${AUTORESEARCH_PORT:-8030}:8000" in compose_text
    assert "VDMC_SERVICE_URL: http://vdmc-indicator:8000" in compose_text
    assert '"8030:8000"' not in compose_text
