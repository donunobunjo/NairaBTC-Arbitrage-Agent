
from fastapi.testclient import TestClient

from app.main import app
from app.paper_trading import ledger


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


def test_portfolio_endpoint():
    with TestClient(app) as client:
        response = client.get("/portfolio")

    assert response.status_code == 200
    assert "initial_balance" in response.json()
    assert "current_balance" in response.json()


def test_scans_endpoint():
    with TestClient(app) as client:
        response = client.get("/scans")

    assert response.status_code == 200
    assert "records" in response.json()
    assert "count" in response.json()


def test_scans_limit_validation():
    with TestClient(app) as client:
        response = client.get("/scans?limit=0")

    assert response.status_code == 422


def test_scan_endpoint_without_real_market_calls():
    # Replace the graph with a predictable result.
    class FakeGraph:
        async def ainvoke(self, state):
            return {
                "quotes": [],
                "results": [],
                "explanations": [],
                "saved_records": 0,
            }

    original_graph = __import__(
        "app.main", fromlist=["agent_graph"]
    ).agent_graph

    try:
        import app.main as main_module
        main_module.agent_graph = FakeGraph()

        with TestClient(app) as client:
            response = client.post("/scan")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["records_saved"] == 0
        assert data["real_trading_enabled"] is False

    finally:
        main_module.agent_graph = original_graph
