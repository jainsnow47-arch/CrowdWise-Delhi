import pytest
from fastapi.testclient import TestClient
from backend.app.main import app, crowding_tier, sum_passenger_counts, alighting_distribution

client = TestClient(app)

def test_health_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

@pytest.mark.parametrize("ratio,expected", [
    (0.50, "seats_available"),
    (0.85, "seats_available"),
    (0.86, "standing_room"),
    (1.35, "standing_room"),
    (1.36, "crowded"),
    (2.00, "crowded"),
])
def test_crowding_tier_thresholds(ratio, expected):
    assert crowding_tier(ratio) == expected

def test_passenger_count_summation():
    # 2 passengers = +2 load, not +1
    counts = [1, 2, 3]
    assert sum_passenger_counts(counts) == 6
    assert sum_passenger_counts([2]) == 2

def test_soft_alighting_conservation():
    dist = alighting_distribution()
    assert len(dist) == 3
    assert pytest.approx(sum(dist), rel=1e-5) == 1.0
    assert dist == [0.15, 0.70, 0.15]
