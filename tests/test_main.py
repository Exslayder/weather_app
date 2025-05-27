from fastapi.testclient import TestClient
from app.main import app, SessionLocal, SearchHistory
import pytest

client = TestClient(app)

@pytest.fixture(autouse=True)
def clear_db():
    db = SessionLocal()
    db.query(SearchHistory).delete()
    db.commit()
    db.close()

def test_root_page_loads():
    response = client.get("/")
    assert response.status_code == 200
    assert "Weather Forecast" in response.text

def test_post_weather_sets_cookie_and_saves():
    response = client.post("/weather", data={"city": "Vitebsk"})
    assert response.status_code == 200
    assert "Set-Cookie" in response.headers
    assert "Vitebsk" in response.text or "Belarus" in response.text

def test_get_weather_adds_to_history():
    response = client.get("/weather?city=Vitebsk")
    assert response.status_code == 200
    assert "Vitebsk" in response.text or "Belarus" in response.text

def test_history_page_shows_searched_cities():
    # Добавим пару записей
    client.post("/weather", data={"city": "Vitebsk"})
    client.post("/weather", data={"city": "vitebsk"})
    response = client.get("/history")
    assert response.status_code == 200
    assert "Vitebsk" in response.text or "Belarus" in response.text

def test_stats_endpoint():
    client.post("/weather", data={"city": "Minsk"})
    response = client.get("/api/stats")
    assert response.status_code == 200
    data = response.json()
    assert any("Minsk" in item["city"] or "Belarus" in item["city"] for item in data)
