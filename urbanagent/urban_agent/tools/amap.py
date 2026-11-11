# -*- coding: utf-8 -*-
"""AMap (高德) backed tools: geocoding, POI retrieval, routing, IP location, weather.

These correspond to the GIS / POI / Transportation tools used throughout the
UrbanEval experiments (maps_geo, maps_regeo, maps_text_search,
maps_around_search, maps_search_detail, maps_direction_*, maps_distance,
maps_ip_location, maps_weather).  Requires the ``AMAP_KEY`` env var.
"""
from typing import Any, Dict

import requests

from ..config import config
from .base import ToolExecutionError, ToolRegistry, tool

_BASE = "https://restapi.amap.com"


def _get(path: str, **params: Any) -> Dict[str, Any]:
    if not config.amap_key:
        raise ToolExecutionError("AMAP_KEY is not configured")
    params["key"] = config.amap_key
    try:
        resp = requests.get(_BASE + path, params=params, timeout=config.tool_timeout)
        data = resp.json()
    except Exception as err:
        raise ToolExecutionError("amap request failed: %s" % err)
    # AMap wraps failures inside a 200 response: status=0 / infocode!=10000.
    # Surfacing this as an explicit error is exactly the "error inside a
    # success shell" case that the closed-loop retry + synthesis verification
    # are designed to catch.
    if str(data.get("status")) != "1":
        raise ToolExecutionError("amap error: %s" % data.get("info", "unknown"))
    return data


_LOC = {"type": "string", "description": "coordinate 'lon,lat', e.g. '116.481,39.990'"}


def register(reg: ToolRegistry) -> None:
    @tool(reg, "maps_geo", "Geocoding (mainland China ONLY): convert a structured address into 'lon,lat' coordinates. Cannot geocode overseas/US addresses — for those it errors or returns a wrong coarse match; do not use it there.",
          {"type": "object",
           "properties": {"address": {"type": "string", "description": "structured address"},
                          "city": {"type": "string", "description": "city name (optional)"}},
           "required": ["address"]}, domain="gis")
    def maps_geo(address: str, city: str = "") -> Any:
        data = _get("/v3/geocode/geo", address=address, city=city)
        if not data.get("geocodes"):
            raise ToolExecutionError("no geocode result for %r" % address)
        return data["geocodes"][:3]

    @tool(reg, "maps_regeo", "Reverse geocoding (mainland China ONLY): convert 'lon,lat' coordinates into a detailed address. Coordinates outside mainland China return no useful address.",
          {"type": "object", "properties": {"location": _LOC}, "required": ["location"]},
          domain="gis")
    def maps_regeo(location: str) -> Any:
        data = _get("/v3/geocode/regeo", location=location, extensions="base")
        return data.get("regeocode", {})

    @tool(reg, "maps_text_search", "Keyword POI search inside a Chinese city (shops, hotels, hospitals...); mainland China ONLY, does not cover overseas/US places.",
          {"type": "object",
           "properties": {"keywords": {"type": "string"},
                          "city": {"type": "string"},
                          "types": {"type": "string", "description": "POI type filter (optional)"}},
           "required": ["keywords"]}, domain="poi")
    def maps_text_search(keywords: str, city: str = "", types: str = "") -> Any:
        data = _get("/v3/place/text", keywords=keywords, city=city, types=types,
                    offset=10, page=1, extensions="all")
        return data.get("pois", [])[:10]

    @tool(reg, "maps_around_search", "POI search around a center coordinate within a radius; mainland China ONLY, does not cover overseas/US locations.",
          {"type": "object",
           "properties": {"location": _LOC,
                          "keywords": {"type": "string"},
                          "radius": {"type": "integer", "description": "radius in meters, <=50000"}},
           "required": ["location", "keywords"]}, domain="poi")
    def maps_around_search(location: str, keywords: str, radius: int = 3000) -> Any:
        data = _get("/v3/place/around", location=location, keywords=keywords,
                    radius=radius, offset=10, page=1, extensions="all")
        return data.get("pois", [])[:10]

    @tool(reg, "maps_search_detail", "Fetch details (rating, opening hours, price) of a POI by its id.",
          {"type": "object", "properties": {"poi_id": {"type": "string"}}, "required": ["poi_id"]},
          domain="poi")
    def maps_search_detail(poi_id: str) -> Any:
        data = _get("/v3/place/detail", id=poi_id, extensions="all")
        if not data.get("pois"):
            raise ToolExecutionError("no detail for poi id %r" % poi_id)
        return data["pois"][0]

    for mode, path, desc in (
            ("walking", "/v3/direction/walking", "walking route"),
            ("bicycling", "/v4/direction/bicycling", "cycling route"),
            ("driving", "/v3/direction/driving", "driving route"),
            ("transit", "/v3/direction/transit/integrated", "public transit route")):
        def _mk(path: str = path, mode: str = mode):
            def route(origin: str, destination: str, city: str = "") -> Any:
                params: Dict[str, Any] = {"origin": origin, "destination": destination}
                if mode == "transit":
                    params["city"] = city or ""
                data = _get(path, **params)
                if mode == "bicycling":  # v4 wraps differently
                    return (data.get("data") or {})
                return data.get("route", {})
            return route
        tool(reg, "maps_direction_" + mode,
             "Plan a %s between two 'lon,lat' coordinates and return distance/duration/steps." % desc,
             {"type": "object",
              "properties": {"origin": _LOC, "destination": _LOC,
                             "city": {"type": "string", "description": "required for transit"}},
              "required": ["origin", "destination"]}, domain="transportation")(_mk())

    @tool(reg, "maps_distance", "Measure straight-line/driving/walking distance between coordinates.",
          {"type": "object",
           "properties": {"origins": _LOC, "destination": _LOC,
                          "type": {"type": "string", "enum": ["0", "1", "3"],
                                   "description": "0 straight line, 1 driving, 3 walking"}},
           "required": ["origins", "destination"]}, domain="transportation")
    def maps_distance(origins: str, destination: str, type: str = "1") -> Any:
        data = _get("/v3/distance", origins=origins, destination=destination, type=type)
        return data.get("results", [])

    @tool(reg, "maps_ip_location", "Locate the city of an IPv4 address (mainland China).",
          {"type": "object", "properties": {"ip": {"type": "string"}}, "required": ["ip"]},
          domain="gis")
    def maps_ip_location(ip: str) -> Any:
        data = _get("/v3/ip", ip=ip)
        return {k: data.get(k) for k in ("province", "city", "adcode", "rectangle")}

    @tool(reg, "maps_weather", "Current weather or 3-day forecast of a Chinese city (by adcode/name).",
          {"type": "object",
           "properties": {"city": {"type": "string", "description": "city name or adcode"},
                          "extensions": {"type": "string", "enum": ["base", "all"],
                                         "description": "base=live weather, all=forecast"}},
           "required": ["city"]}, domain="environment")
    def maps_weather(city: str, extensions: str = "base") -> Any:
        data = _get("/v3/weather/weatherInfo", city=city, extensions=extensions)
        return data.get("lives") or data.get("forecasts") or []
