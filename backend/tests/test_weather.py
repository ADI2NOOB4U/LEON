import asyncio

from backend.app.tools import weather
from backend.app.tools.weather import (
    FORECAST_URL,
    GEOCODING_URL,
    current_weather_reply,
    extract_weather_location,
    format_current_weather,
    get_current_weather,
)


def test_weather_location_is_explicit_and_trailing_time_is_removed():
    assert extract_weather_location("What's the weather in New York today?") == "New York"
    assert extract_weather_location("weather for Paris, France now") == "Paris, France"
    assert extract_weather_location("What's the weather?") == ""
    assert extract_weather_location("Tell me a story") is None


def test_weather_without_location_asks_and_never_uses_passive_location(monkeypatch):
    def unexpected_client(*args, **kwargs):
        raise AssertionError("Weather without an explicit location must not call a provider")

    monkeypatch.setattr(weather.httpx, "AsyncClient", unexpected_client)

    reply = asyncio.run(current_weather_reply("What's the weather?"))

    assert reply == "Which city or location should I check? I do not infer your location."


def test_current_weather_uses_open_meteo_geocoding_and_forecast(monkeypatch):
    requests = []

    class Response:
        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self.payload

    class Client:
        def __init__(self, **kwargs):
            self.timeout = kwargs["timeout"]

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_value, traceback):
            return False

        async def get(self, url, *, params):
            requests.append((url, params))
            if url == GEOCODING_URL:
                return Response(
                    {
                        "results": [
                            {
                                "name": "London",
                                "admin1": "England",
                                "country": "United Kingdom",
                                "latitude": 51.5,
                                "longitude": -0.12,
                            }
                        ]
                    }
                )
            assert url == FORECAST_URL
            return Response(
                {
                    "timezone": "Europe/London",
                    "current": {
                        "time": "2026-10-04T12:00",
                        "temperature_2m": 14.2,
                        "relative_humidity_2m": 75,
                        "apparent_temperature": 13.4,
                        "precipitation": 0.1,
                        "weather_code": 3,
                        "wind_speed_10m": 11.0,
                    },
                }
            )

    monkeypatch.setattr(weather.httpx, "AsyncClient", Client)

    result = asyncio.run(get_current_weather("London"))

    assert requests[0] == (
        GEOCODING_URL,
        {"name": "London", "count": 1, "language": "en", "format": "json"},
    )
    assert requests[1][0] == FORECAST_URL
    assert requests[1][1]["latitude"] == 51.5
    assert requests[1][1]["longitude"] == -0.12
    assert result["temperature_c"] == 14.2
    assert result["conditions"] == "overcast"
    assert result["source"] == "Open-Meteo"
    assert "Current weather for London, England, United Kingdom" in format_current_weather(result)
    assert "14.2 degrees C" in format_current_weather(result)
