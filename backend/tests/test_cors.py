from main import app
from fastapi.testclient import TestClient


def test_cors_allows_vite_fallback_port_5174():
    client = TestClient(app)

    response = client.options(
        "/admin/clinicians",
        headers={
            "Origin": "http://127.0.0.1:5174",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5174"
