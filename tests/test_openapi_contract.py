from __future__ import annotations

from src import main as main_module


def _schema() -> dict:
    return main_module.app.openapi()


def test_openapi_prefers_api_v1_and_hides_legacy_api_prefix() -> None:
    paths = _schema()["paths"]

    assert "/api/v1/research/start" in paths
    assert "/api/v1/research/{research_id}/promote/confirm" in paths
    assert "/api/research/start" not in paths
    assert not any(
        path.startswith("/api/") and not path.startswith("/api/v1/")
        for path in paths
    )


def test_openapi_documents_auth_and_idempotency_headers() -> None:
    schema = _schema()
    security_schemes = schema["components"]["securitySchemes"]
    assert security_schemes["HTTPBearer"]["scheme"] == "bearer"

    start_operation = schema["paths"]["/api/v1/research/start"]["post"]
    assert start_operation["security"] == [{"HTTPBearer": []}]

    continue_operation = schema["paths"]["/api/v1/research/{research_id}/continue"]["post"]
    header_params = {
        param["name"]: param
        for param in continue_operation["parameters"]
        if param["in"] == "header"
    }
    assert "Idempotency-Key" in header_params
    idempotency_schema = header_params["Idempotency-Key"]["schema"]
    assert idempotency_schema.get("type") == "string" or any(
        option.get("type") == "string"
        for option in idempotency_schema.get("anyOf", [])
    )


def test_openapi_documents_promotion_approval_schema() -> None:
    schema = _schema()
    promotion_request = schema["components"]["schemas"]["PromotionScopeRequest"]
    approval_ref = promotion_request["properties"]["approval"]["anyOf"][0]["$ref"]
    assert approval_ref.endswith("/PromotionApproval")

    approval_schema = schema["components"]["schemas"]["PromotionApproval"]
    for field in ("approver", "reason", "method", "signature", "approved"):
        assert field in approval_schema["properties"]


def test_openapi_documents_health_info_and_excludes_metrics() -> None:
    paths = _schema()["paths"]

    assert "/health" in paths
    assert "/health/ready" in paths
    assert "/monitoring/health" in paths
    assert "/info" in paths
    assert "/metrics" not in paths
