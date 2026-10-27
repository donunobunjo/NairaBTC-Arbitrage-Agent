
import os

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.main import app
from app.paper_trading import ledger

load_dotenv()

API_KEY = os.getenv("API_SECRET_KEY")

assert API_KEY, "API_SECRET_KEY must be configured in .env"

AUTH_HEADERS = {"X-API-Key": API_KEY}


def test_root_endpoint():
    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert response.json()["name"] == "NairaBTC Agent"
    assert response.json()["real_trading_enabled"] is False


def test_health_endpoint():
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_portfolio_requires_api_key():
    with TestClient(app) as client:
        response = client.get("/portfolio")

    assert response.status_code == 401


def test_portfolio_with_api_key():
    with TestClient(app) as client:
        response = client.get(
            "/portfolio",
            headers=AUTH_HEADERS,
        )

    assert response.status_code == 200
    data = response.json()
    assert "initial_balance" in data
    assert "current_balance" in data


def test_scans_requires_api_key():
    with TestClient(app) as client:
        response = client.get("/scans")

    assert response.status_code == 401


def test_scans_with_api_key():
    with TestClient(app) as client:
        response = client.get(
            "/scans",
            headers=AUTH_HEADERS,
        )

    assert response.status_code == 200
    data = response.json()
    assert "records" in data
    assert "count" in data


def test_scans_limit_validation():
    with TestClient(app) as client:
        response = client.get(
            "/scans?limit=0",
            headers=AUTH_HEADERS,
        )

    assert response.status_code == 422


def test_scan_requires_api_key():
    with TestClient(app) as client:
        response = client.post("/scan")

    assert response.status_code == 401


def test_scan_endpoint_with_api_key(monkeypatch):
    class FakeGraph:
        async def ainvoke(self, state):
            return {
                "quotes": [],
                "results": [],
                "explanations": [],
                "saved_records": 0,
            }

    import app.main as main_module

    monkeypatch.setattr(main_module, "agent_graph", FakeGraph())

    with TestClient(app) as client:
        response = client.post(
            "/scan",
            headers=AUTH_HEADERS,
        )

    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "completed"
    assert data["records_saved"] == 0
    assert data["real_trading_enabled"] is False


def test_rate_limiter_blocks_excess_requests():
    test_limiter = Limiter(key_func=get_remote_address)
    test_app = FastAPI()

    test_app.state.limiter = test_limiter
    test_app.add_exception_handler(
        RateLimitExceeded,
        _rate_limit_exceeded_handler,
    )

    @test_app.get("/limited")
    @test_limiter.limit("5/minute")
    async def limited_endpoint(request: Request):
        return {"status": "ok"}

    with TestClient(test_app) as client:
        responses = [
            client.get("/limited")
            for _ in range(6)
        ]

    assert all(
        response.status_code == 200
        for response in responses[:5]
    )
    assert responses[5].status_code == 429




def test_production_scan_rate_limit(monkeypatch):
    class FakeGraph:
        async def ainvoke(self, state):
            return {
                "quotes": [],
                "results": [],
                "explanations": [],
                "saved_records": 0,
            }

    import app.main as main_module

    monkeypatch.setattr(main_module, "agent_graph", FakeGraph())

    # Clear prior rate-limit history for this test client.
    limiter = main_module.app.state.limiter
    limiter.reset()

    with TestClient(main_module.app) as client:
        responses = [
            client.post("/scan", headers=AUTH_HEADERS)
            for _ in range(6)
        ]

    assert all(
        response.status_code == 200
        for response in responses[:5]
    )
    assert responses[5].status_code == 429






def test_health_endpoint_returns_503_when_database_fails(monkeypatch):
    import app.main as main_module

    def failing_database_check():
        raise RuntimeError("Simulated database failure")

    monkeypatch.setattr(
        main_module.ledger,
        "get_portfolio",
        failing_database_check,
    )

    with TestClient(main_module.app) as client:
        response = client.get("/health")

    assert response.status_code == 503
    assert response.json()["detail"] == (
        "Service or database is unavailable."
    )


def test_health_endpoint_reports_database_available():
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["database"] == "available"


def test_scan_reports_partial_save_failure(monkeypatch):
    from decimal import Decimal
    from types import SimpleNamespace

    import app.main as main_module

    fake_result = SimpleNamespace(
        buy_exchange="Binance",
        sell_exchange="OKX",
        trade_size_btc=Decimal("0.001"),
        buy_price=Decimal("90000"),
        sell_price=Decimal("90200"),
        gross_profit=Decimal("0.20"),
        net_profit=Decimal("0.10"),
        net_return_pct=Decimal("0.11"),
        eligible=True,
        reason="Net profit exceeds the configured threshold.",
    )

    class FakeGraph:
        async def ainvoke(self, state):
            return {
                "quotes": [object(), object()],
                "results": [fake_result],
                "explanations": ["Estimated profit is positive."],
                "saved_records": 0,
                "save_errors": [
                    "Failed to save Binance -> OKX."
                ],
            }

    monkeypatch.setattr(
        main_module,
        "agent_graph",
        FakeGraph(),
    )

    # Isolate this test from the production endpoint's rate limit.
    main_module.app.state.limiter.reset()

    with TestClient(main_module.app) as client:
        response = client.post(
            "/scan",
            headers=AUTH_HEADERS,
        )

    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "completed_with_warnings"
    assert data["records_saved"] == 0
    assert data["save_errors_count"] == 1
    assert data["save_warnings"]
