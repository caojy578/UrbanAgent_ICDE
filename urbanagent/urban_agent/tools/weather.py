# -*- coding: utf-8 -*-
"""Open-Meteo backed global weather tools (no API key required).

Complements maps_weather (China only) with worldwide hourly forecast and
historical archive — used by complex-retrieval queries such as
"check the 09:00 weather at San Francisco Mission District".
"""
from typing import Any, Dict

import requests

from ..config import config
from .base import ToolExecutionError, ToolRegistry, tool


def _get(url: str, **params: Any) -> Dict[str, Any]:
    try:
        resp = requests.get(url, params=params, timeout=config.tool_timeout)
        data = resp.json()
    except Exception as err:
        raise ToolExecutionError("open-meteo request failed: %s" % err)
    if isinstance(data, dict) and data.get("error"):
        raise ToolExecutionError("open-meteo error: %s" % data.get("reason"))
    return data


def register(reg: ToolRegistry) -> None:
    @tool(reg, "weather_forecast",
          "Global weather forecast (up to 16 days, hourly resolution) for a lat/lon point. "
          "Returns hourly temperature, precipitation, wind speed and weather code.",
          {"type": "object",
           "properties": {"latitude": {"type": "number"},
                          "longitude": {"type": "number"},
                          "days": {"type": "integer", "description": "forecast days, 1-16"}},
           "required": ["latitude", "longitude"]}, domain="environment")
    def weather_forecast(latitude: float, longitude: float, days: int = 3) -> Any:
        return _get("https://api.open-meteo.com/v1/forecast",
                    latitude=latitude, longitude=longitude, forecast_days=min(max(days, 1), 16),
                    hourly="temperature_2m,precipitation_probability,precipitation,wind_speed_10m,weather_code",
                    daily="temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max",
                    current_weather=True, timezone="auto")

    @tool(reg, "weather_history",
          "Historical weather archive for a lat/lon point and a past date range (YYYY-MM-DD).",
          {"type": "object",
           "properties": {"latitude": {"type": "number"},
                          "longitude": {"type": "number"},
                          "start_date": {"type": "string"},
                          "end_date": {"type": "string"}},
           "required": ["latitude", "longitude", "start_date", "end_date"]},
          domain="environment")
    def weather_history(latitude: float, longitude: float, start_date: str, end_date: str) -> Any:
        return _get("https://archive-api.open-meteo.com/v1/archive",
                    latitude=latitude, longitude=longitude,
                    start_date=start_date, end_date=end_date,
                    daily="temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max",
                    timezone="auto")

    @tool(reg, "geocode_global",
          "Global place-name geocoding (worldwide, returns lat/lon candidates). "
          "Use for places outside mainland China.",
          {"type": "object",
           "properties": {"name": {"type": "string", "description": "place name"},
                          "count": {"type": "integer"}},
           "required": ["name"]}, domain="gis")
    def geocode_global(name: str, count: int = 3) -> Any:
        data = _get("https://geocoding-api.open-meteo.com/v1/search",
                    name=name, count=min(max(count, 1), 10), language="en", format="json")
        results = data.get("results")
        if not results:
            raise ToolExecutionError("no geocoding result for %r" % name)
        return results
