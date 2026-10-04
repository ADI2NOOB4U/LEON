from __future__ import annotations

import re
from typing import Any

import httpx

from backend.app.config.settings import settings
from backend.app.core.capabilities import is_weather_request


GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
CURRENT_WEATHER_FIELDS = (
    "temperature_2m,relative_humidity_2m,apparent_temperature,"
    "precipitation,weather_code,wind_speed_10m"
)
WEATHER_CODES = {
    0: "clear sky",
    1: "mainly clear",
    2: "partly cloudy",
    3: "overcast",
    45: "fog",
    48: "rime fog",
    51: "light drizzle",
    53: "moderate drizzle",
    55: "dense drizzle",
    56: "light freezing drizzle",
    57: "dense freezing drizzle",
    61: "slight rain",
    63: "moderate rain",
    65: "heavy rain",
    66: "light freezing rain",
    67: "heavy freezing rain",
    71: "slight snow",
    73: "moderate snow",
    75: "heavy snow",
    77: "snow grains",
    80: "slight rain showers",
    81: "moderate rain showers",
    82: "violent rain showers",
    85: "slight snow showers",
    86: "heavy snow showers",
    90: "thunderstorm",
    95: "thunderstorm",
    96: "thunderstorm with slight hail",
    99: "thunderstorm with heavy hail",
}
LOCATION_PATTERN = re.compile(r"\b(?:in|for|at)\s+(.+?)\s*[?.!,]*$", re.I)
TRAILING_TIME_PATTERN = re.compile(
    r"\s+(?:today|tomorrow|currently|right now|now)$",
    re.I,
)


class WeatherServiceError(RuntimeError):
    pass


def extract_weather_location(message: str) -> str | None:
    if not is_weather_request(message):
        return None
    match = LOCATION_PATTERN.search(message.strip())
    if not match:
        return ""
    location = TRAILING_TIME_PATTERN.sub("", match.group(1).strip())
    location = location.strip(" \t\r\n.,!?")
    if not location:
        return ""
    if len(location) > 100 or not re.fullmatch(r"[\w .,'-]+", location, re.UNICODE):
        raise WeatherServiceError(
            "Please provide a city or location using letters, numbers, spaces, "
            "commas, apostrophes, or hyphens."
        )
    return location


async def _get_json(
    client: httpx.AsyncClient,
    url: str,
    params: dict[str, str | int | float],
) -> dict[str, Any]:
    try:
        response = await client.get(url, params=params)
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise WeatherServiceError(
            f"The weather service returned HTTP {exc.response.status_code}."
        ) from exc
    except httpx.RequestError as exc:
        raise WeatherServiceError(
            f"The weather service could not be reached ({type(exc).__name__})."
        ) from exc
    try:
        payload = response.json()
    except (ValueError, TypeError) as exc:
        raise WeatherServiceError("The weather service returned invalid data.") from exc
    if not isinstance(payload, dict):
        raise WeatherServiceError("The weather service returned invalid data.")
    return payload


async def get_current_weather(location: str) -> dict[str, Any]:
    normalized_location = location.strip()
    if not normalized_location:
        raise ValueError("A city or location is required.")
    if len(normalized_location) > 100 or not re.fullmatch(
        r"[\w .,'-]+",
        normalized_location,
        re.UNICODE,
    ):
        raise ValueError("The city or location contains unsupported characters.")

    async with httpx.AsyncClient(timeout=settings.web_request_timeout) as client:
        geocoding = await _get_json(
            client,
            GEOCODING_URL,
            {"name": normalized_location, "count": 1, "language": "en", "format": "json"},
        )
        results = geocoding.get("results")
        if not isinstance(results, list) or not results:
            raise WeatherServiceError(
                f"No matching location was found for '{normalized_location}'."
            )
        place = results[0]
        if not isinstance(place, dict):
            raise WeatherServiceError("The weather service returned invalid location data.")
        try:
            latitude = float(place["latitude"])
            longitude = float(place["longitude"])
            name = str(place["name"])
        except (KeyError, TypeError, ValueError) as exc:
            raise WeatherServiceError(
                "The weather service returned incomplete location data."
            ) from exc

        forecast = await _get_json(
            client,
            FORECAST_URL,
            {
                "latitude": latitude,
                "longitude": longitude,
                "current": CURRENT_WEATHER_FIELDS,
                "timezone": "auto",
            },
        )

    current = forecast.get("current")
    if not isinstance(current, dict):
        raise WeatherServiceError("The weather service returned no current conditions.")
    try:
        code = int(current["weather_code"])
        return {
            "location": name,
            "admin1": str(place.get("admin1") or ""),
            "country": str(place.get("country") or ""),
            "timezone": str(forecast.get("timezone") or ""),
            "time": str(current["time"]),
            "temperature_c": float(current["temperature_2m"]),
            "feels_like_c": float(current["apparent_temperature"]),
            "humidity_percent": int(current["relative_humidity_2m"]),
            "precipitation_mm": float(current["precipitation"]),
            "wind_speed_kmh": float(current["wind_speed_10m"]),
            "conditions": WEATHER_CODES.get(code, "conditions unavailable"),
            "source": "Open-Meteo",
            "source_url": "https://open-meteo.com/",
        }
    except (KeyError, TypeError, ValueError) as exc:
        raise WeatherServiceError(
            "The weather service returned incomplete current conditions."
        ) from exc


def format_current_weather(result: dict[str, Any]) -> str:
    place = ", ".join(
        part
        for part in (result["location"], result["admin1"], result["country"])
        if part
    )
    return (
        f"Current weather for {place}: {result['conditions']}, "
        f"{result['temperature_c']:g} degrees C (feels like "
        f"{result['feels_like_c']:g} degrees C), humidity "
        f"{result['humidity_percent']}%, wind "
        f"{result['wind_speed_kmh']:g} km/h. "
        f"Source: {result['source']} ({result['source_url']})."
    )


async def current_weather_reply(message: str) -> str | None:
    try:
        location = extract_weather_location(message)
    except WeatherServiceError as exc:
        return str(exc)
    if location is None:
        return None
    if not location:
        return "Which city or location should I check? I do not infer your location."
    try:
        return format_current_weather(await get_current_weather(location))
    except WeatherServiceError as exc:
        return str(exc)
