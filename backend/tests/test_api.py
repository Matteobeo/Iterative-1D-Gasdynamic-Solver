from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_simulate_endpoint():
    req = {
        "P0": 500000,
        "T0": 600,
        "P_amb": 101325,
        "gamma": 1.4,
        "R": 287.0,
        "components": [
            {"type": "convergent", "params": {"d_in": 0.1, "d_out": 0.05, "length": 0.2}},
            {"type": "fanno", "params": {"d_h": 0.05, "length": 1.0, "f": 0.005}}
        ]
    }
    
    response = client.post("/api/simulate", json=req)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "data" in data
    assert "mach" in data["data"]
    
    # Check that there is data in the arrays
    assert len(data["data"]["mach"]) > 0
    assert "warnings" in data
