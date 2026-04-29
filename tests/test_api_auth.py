from __future__ import annotations

import base64
import os
from pathlib import Path

import pytest
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.testclient import TestClient
from starlette.testclient import WebSocketDenialResponse

os.environ.setdefault("ANTHROPIC_BASE_URL", "http://anthropic.invalid")
os.environ.setdefault("ANTHROPIC_AUTH_TOKEN", "test-token")

from server.api import promotion, research, results
from server.api.auth import require_websocket_auth
from server.config import Settings, settings

API_TOKEN = "test-autoresearch-token"


def create_test_app() -> FastAPI:
    app = FastAPI()
    app.include_router(research.router)
    app.include_router(results.router)
    app.include_router(promotion.router)

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

    async def continue_pipeline(self, pipeline_id: str, **kwargs):
        return {"id": "pipe_auth_continued", "resumed_from": pipeline_id, **kwargs}

    def is_running(self, research_id: str):
        return False


class FakeStore:
    async def list_sessions(self, **kwargs):
        return []

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

    async def list_promotions(self):
        return []

    async def list_pipelines(self, **kwargs):
        return []

    async def delete_session(self, research_id: str):
        return research_id == "res_auth"


class FakePromoter:
    async def preview(self, research_id: str):
        return {"research_id": research_id, "preview": True}

    async def confirm(self, research_id: str):
        return {"research_id": research_id, "confirmed": True}

    async def rollback(
        self,
        *,
        model_type: str,
        instrument: str,
        timeframe: str,
        reason: str | None = None,
    ):
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
    store = FakeStore()
    research.init(FakeSessionManager(), store)
    results.init(store)
    promotion.init(FakePromoter(), store)


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

    rollback = client.post(
        "/api/promotions/direction/DOGE_USDT/15m/rollback",
        json={"reason": "auth test"},
        headers=auth_headers(),
    )
    assert rollback.status_code == 200
    assert rollback.json()["rolled_back"] is True


def test_websocket_requires_authentication(client: TestClient):
    with pytest.raises(WebSocketDenialResponse) as exc:
        with client.websocket_connect("/ws/events"):
            pass

    assert exc.value.status_code == 401
    assert exc.value.headers["www-authenticate"] == "Bearer"


def test_websocket_accepts_authorization_header(client: TestClient):
    with client.websocket_connect("/ws/events", headers=auth_headers()):
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


def test_compose_binds_autoresearch_port_to_loopback_by_default():
    repo_root = Path(__file__).resolve().parents[3]
    compose_text = (repo_root / "compose" / "autoresearch.yml").read_text(encoding="utf-8")

    assert "${AUTORESEARCH_BIND_HOST:-127.0.0.1}:${AUTORESEARCH_PORT:-8030}:8000" in compose_text
    assert '"8030:8000"' not in compose_text
