# -*- coding: utf-8 -*-
"""USGS earthquake tools (public-safety domain, no API key required)."""
from typing import Any, Dict, Optional

import requests

from ..config import config
from .base import ToolExecutionError, ToolRegistry, tool

_BASE = "https://earthquake.usgs.gov/fdsnws/event/1"


def _get(method: str, **params: Any) -> Dict[str, Any]:
    params.setdefault("format", "geojson")
    try:
        resp = requests.get("%s/%s" % (_BASE, method), params=params,
                            timeout=config.tool_timeout)
        if resp.status_code != 200:
            raise ToolExecutionError("usgs http %s: %s" % (resp.status_code, resp.text[:200]))
        return resp.json()
    except ToolExecutionError:
        raise
    except Exception as err:
        raise ToolExecutionError("usgs request failed: %s" % err)


_COMMON = {
    "starttime": {"type": "string", "description": "ISO date/time, e.g. 2026-06-25"},
    "endtime": {"type": "string", "description": "ISO date/time (optional, default now)"},
    "minmagnitude": {"type": "number"},
    "latitude": {"type": "number", "description": "center latitude for radius search (optional)"},
    "longitude": {"type": "number", "description": "center longitude for radius search (optional)"},
    "maxradiuskm": {"type": "number", "description": "search radius in km (optional)"},
}


def _clean(params: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in params.items() if v is not None and v != ""}


def register(reg: ToolRegistry) -> None:
    @tool(reg, "earthquake_query",
          "Query recent earthquakes (magnitude, time, place, depth, coordinates) from USGS. "
          "Filter by time window, minimum magnitude and an optional lat/lon radius.",
          {"type": "object", "properties": dict(_COMMON), "required": ["starttime"]},
          domain="public_safety")
    def earthquake_query(starttime: str, endtime: Optional[str] = None,
                         minmagnitude: Optional[float] = None,
                         latitude: Optional[float] = None, longitude: Optional[float] = None,
                         maxradiuskm: Optional[float] = None) -> Any:
        data = _get("query", **_clean(dict(
            starttime=starttime, endtime=endtime, minmagnitude=minmagnitude,
            latitude=latitude, longitude=longitude, maxradiuskm=maxradiuskm,
            orderby="time", limit=50)))
        return [{
            "magnitude": f["properties"].get("mag"),
            "place": f["properties"].get("place"),
            "time_ms": f["properties"].get("time"),
            "depth_km": (f["geometry"]["coordinates"][2]
                         if f.get("geometry") and len(f["geometry"].get("coordinates", [])) > 2 else None),
            "coordinates": f["geometry"]["coordinates"][:2] if f.get("geometry") else None,
            "id": f.get("id"),
        } for f in data.get("features", [])]

    @tool(reg, "earthquake_count",
          "Count earthquakes matching the given time window / magnitude / radius filters (USGS).",
          {"type": "object", "properties": dict(_COMMON), "required": ["starttime"]},
          domain="public_safety")
    def earthquake_count(starttime: str, endtime: Optional[str] = None,
                         minmagnitude: Optional[float] = None,
                         latitude: Optional[float] = None, longitude: Optional[float] = None,
                         maxradiuskm: Optional[float] = None) -> Any:
        return _get("count", **_clean(dict(
            starttime=starttime, endtime=endtime, minmagnitude=minmagnitude,
            latitude=latitude, longitude=longitude, maxradiuskm=maxradiuskm)))

    @tool(reg, "earthquake_detail", "Fetch full details of one earthquake by its USGS event id.",
          {"type": "object", "properties": {"event_id": {"type": "string"}},
           "required": ["event_id"]}, domain="public_safety")
    def earthquake_detail(event_id: str) -> Any:
        data = _get("query", eventid=event_id)
        feats = data.get("features") or ([data] if data.get("properties") else [])
        if not feats:
            raise ToolExecutionError("no earthquake with id %r" % event_id)
        return feats[0]["properties"]
