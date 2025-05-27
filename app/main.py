import logging
import uuid
from fastapi import FastAPI, Request, Form, Cookie
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import create_engine, Column, Integer, String, DateTime, func
from sqlalchemy.orm import sessionmaker, declarative_base
import requests

# --- Logging setup ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)
logger = logging.getLogger(__name__)

# --- DB setup ---
engine = create_engine(
    "sqlite:///./weather.db",
    connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class SearchHistory(Base):
    __tablename__ = "search_history"
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, index=True)
    city = Column(String, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

Base.metadata.create_all(bind=engine)

# --- App setup ---
app = FastAPI()
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")
templates.env.globals['zip'] = zip

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"


def get_standardized_city_name(city: str) -> str | None:
    try:
        logger.info(f"Fetching geocoding info for city: {city}")
        resp = requests.get(
            GEOCODING_URL,
            params={"name": city, "count": 1},
            timeout=5
        )
        resp.raise_for_status()
        geo = resp.json().get("results") or []
        if not geo:
            logger.warning(f"Geocoding: city not found: {city}")
            return None
        loc = geo[0]
        standardized = f"{loc['name']}, {loc['country']}"
        logger.info(f"Standardized city name: {standardized}")
        return standardized
    except requests.RequestException as e:
        logger.error(f"Error fetching geocoding data for '{city}': {e}")
        return None


def _fetch_weather(lat: float, lon: float) -> dict | None:
    try:
        logger.info(f"Fetching weather for coordinates: {lat}, {lon}")
        weather_resp = requests.get(
            OPEN_METEO_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "hourly": ",".join([
                    "temperature_2m",
                    "weathercode",
                    "precipitation",
                    "windspeed_10m"
                ])
            },
            timeout=5
        )
        weather_resp.raise_for_status()
        return weather_resp.json()
    except requests.RequestException as e:
        logger.error(f"Error fetching weather data: {e}")
        return None


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request, session_id: str = Cookie(None)):
    logger.info("GET /")
    last_city = None
    if session_id:
        db = SessionLocal()
        entry = (
            db.query(SearchHistory)
            .filter_by(session_id=session_id)
            .order_by(SearchHistory.timestamp.desc())
            .first()
        )
        if entry:
            last_city = entry.city
        db.close()

    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "request": request,
            "weather": None,
            "error": None,
            "city": None,
            "last_city": last_city
        }
    )


@app.post("/weather", response_class=HTMLResponse)
async def post_weather(
    request: Request,
    city: str = Form(...),
    session_id: str = Cookie(None)
):
    logger.info(f"POST /weather with city={city}")
    if not session_id:
        session_id = str(uuid.uuid4())
        logger.info(f"Generated new session_id: {session_id}")

    standardized_city = get_standardized_city_name(city)
    if not standardized_city:
        logger.warning(f"City not found during POST: {city}")
        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "request": request,
                "weather": None,
                "error": "City not found",
                "city": city,
                "last_city": None
            }
        )

    db = SessionLocal()
    try:
        db.add(SearchHistory(session_id=session_id, city=standardized_city))
        db.commit()
        logger.info(f"Saved search history: session={session_id}, city={standardized_city}")
    except Exception as e:
        logger.error(f"DB error on insert: {e}")
        db.rollback()
    finally:
        db.close()

    geo = requests.get(
        GEOCODING_URL,
        params={"name": standardized_city, "count": 1},
        timeout=5
    ).json().get("results") or []
    loc = geo[0]
    weather = _fetch_weather(loc["latitude"], loc["longitude"])
    if weather is None:
        logger.error("Weather fetch returned None")
        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "request": request,
                "weather": None,
                "error": "Failed to fetch weather",
                "city": standardized_city,
                "last_city": standardized_city
            }
        )

    resp = templates.TemplateResponse(
        request,
        "index.html",
        {
            "request": request,
            "weather": weather,
            "error": None,
            "city": standardized_city,
            "last_city": standardized_city
        }
    )
    resp.set_cookie("session_id", session_id, max_age=30 * 24 * 3600)
    return resp


@app.get("/weather", response_class=HTMLResponse)
async def get_weather(
    request: Request,
    city: str,
    session_id: str = Cookie(None)
):
    logger.info(f"GET /weather with city={city}")
    if not session_id:
        session_id = str(uuid.uuid4())
        logger.info(f"Generated new session_id: {session_id}")

    standardized_city = get_standardized_city_name(city)
    if not standardized_city:
        logger.warning(f"City not found during GET: {city}")
        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "request": request,
                "weather": None,
                "error": "City not found",
                "city": city,
                "last_city": None
            }
        )

    db = SessionLocal()
    try:
        db.add(SearchHistory(session_id=session_id, city=standardized_city))
        db.commit()
        logger.info(f"Saved search history: session={session_id}, city={standardized_city}")
    except Exception as e:
        logger.error(f"DB error on insert: {e}")
        db.rollback()
    finally:
        db.close()

    geo = requests.get(
        GEOCODING_URL,
        params={"name": standardized_city, "count": 1},
        timeout=5
    ).json().get("results") or []
    loc = geo[0]
    weather = _fetch_weather(loc["latitude"], loc["longitude"])
    if weather is None:
        logger.error("Weather fetch returned None")
        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "request": request,
                "weather": None,
                "error": "Failed to fetch weather",
                "city": standardized_city,
                "last_city": standardized_city
            }
        )

    resp = templates.TemplateResponse(
        request,
        "index.html",
        {
            "request": request,
            "weather": weather,
            "error": None,
            "city": standardized_city,
            "last_city": standardized_city
        }
    )
    resp.set_cookie("session_id", session_id, max_age=30 * 24 * 3600)
    return resp


@app.get("/history", response_class=HTMLResponse)
async def show_history(request: Request, session_id: str = Cookie(None)):
    logger.info(f"GET /history (session_id={session_id})")
    history = []
    if session_id:
        db = SessionLocal()
        try:
            rows = (
                db.query(SearchHistory.city, func.count(SearchHistory.id).label("count"))
                .filter_by(session_id=session_id)
                .group_by(SearchHistory.city)
                .order_by(func.count(SearchHistory.id).desc())
                .all()
            )
            history = [{"city": city, "count": count} for city, count in rows]
            logger.info(f"Fetched {len(history)} history entries for session {session_id}")
        except Exception as e:
            logger.error(f"DB error on fetching history: {e}")
        finally:
            db.close()

    return templates.TemplateResponse(
        request,
        "history.html",
        {
            "request": request,
            "history": history
        }
    )


@app.get("/api/stats", response_class=JSONResponse)
async def stats():
    logger.info("GET /api/stats")
    db = SessionLocal()
    try:
        rows = (
            db.query(SearchHistory.city, func.count(SearchHistory.id).label("count"))
            .group_by(SearchHistory.city)
            .all()
        )
        result = [{"city": city, "count": count} for city, count in rows]
        logger.info(f"Stats result: {result}")
        return result
    except Exception as e:
        logger.error(f"DB error on stats: {e}")
        return []
    finally:
        db.close()


if __name__ == "__main__":
    import uvicorn
    logger.info("Starting uvicorn server on 0.0.0.0:8000")
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
