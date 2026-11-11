# -*- coding: utf-8 -*-
"""Carbon-emission tools (energy domain): local deterministic calculators.

Emission factors follow commonly used public sources (IEA / EPA / UK BEIS
grid averages; ICCT per-km vehicle factors).  Being local computations they
never fail on network, which also makes them useful for offline smoke tests.
"""
from typing import Any, Dict, Optional

from .base import ToolExecutionError, ToolRegistry, tool

# kg CO2 per kWh (grid average)
GRID_FACTORS: Dict[str, float] = {
    "china": 0.581, "us": 0.386, "usa": 0.386, "united states": 0.386,
    "california": 0.220, "washington": 0.099, "uk": 0.207, "united kingdom": 0.207,
    "france": 0.056, "germany": 0.380, "japan": 0.457, "canada": 0.130,
    "spain": 0.170, "switzerland": 0.028, "world": 0.436,
}

# kg CO2 per km
VEHICLE_FACTORS: Dict[str, float] = {
    "compact_gasoline": 0.143, "midsize_gasoline": 0.192, "suv_gasoline": 0.235,
    "small_suv_gasoline": 0.205, "hybrid": 0.105, "hybrid_suv": 0.135,
    "ev": 0.053, "diesel": 0.171,
}

# kg CO2 per passenger-km
FLIGHT_FACTORS: Dict[str, float] = {"economy": 0.151, "business": 0.302, "first": 0.604}


def register(reg: ToolRegistry) -> None:
    @tool(reg, "carbon_electricity",
          "Compute CO2 emissions (kg) of electricity consumption given kWh and a "
          "country/region grid (e.g. 'china', 'california', 'france').",
          {"type": "object",
           "properties": {"kwh": {"type": "number"},
                          "region": {"type": "string"},
                          "custom_factor": {"type": "number",
                                            "description": "override kgCO2/kWh (optional)"}},
           "required": ["kwh", "region"]}, domain="energy")
    def carbon_electricity(kwh: float, region: str, custom_factor: Optional[float] = None) -> Any:
        factor = custom_factor if custom_factor is not None else GRID_FACTORS.get(region.strip().lower())
        if factor is None:
            raise ToolExecutionError(
                "unknown grid region %r; known: %s (or pass custom_factor)"
                % (region, ", ".join(sorted(GRID_FACTORS))))
        return {"kwh": kwh, "region": region, "factor_kg_per_kwh": factor,
                "emissions_kg": round(kwh * factor, 3)}

    @tool(reg, "carbon_vehicle",
          "Compute CO2 emissions (kg) of a car trip given distance_km and vehicle type.",
          {"type": "object",
           "properties": {"distance_km": {"type": "number"},
                          "vehicle_type": {"type": "string",
                                           "enum": sorted(VEHICLE_FACTORS)}},
           "required": ["distance_km", "vehicle_type"]}, domain="energy")
    def carbon_vehicle(distance_km: float, vehicle_type: str) -> Any:
        factor = VEHICLE_FACTORS.get(vehicle_type)
        if factor is None:
            raise ToolExecutionError("unknown vehicle type %r" % vehicle_type)
        return {"distance_km": distance_km, "vehicle_type": vehicle_type,
                "factor_kg_per_km": factor, "emissions_kg": round(distance_km * factor, 3)}

    @tool(reg, "carbon_flight",
          "Compute CO2 emissions (kg) of a flight given distance_km, passengers and cabin class.",
          {"type": "object",
           "properties": {"distance_km": {"type": "number"},
                          "passengers": {"type": "integer"},
                          "cabin": {"type": "string", "enum": sorted(FLIGHT_FACTORS)}},
           "required": ["distance_km"]}, domain="energy")
    def carbon_flight(distance_km: float, passengers: int = 1, cabin: str = "economy") -> Any:
        factor = FLIGHT_FACTORS.get(cabin, FLIGHT_FACTORS["economy"])
        return {"distance_km": distance_km, "passengers": passengers, "cabin": cabin,
                "factor_kg_per_pkm": factor,
                "emissions_kg": round(distance_km * passengers * factor, 3)}

    @tool(reg, "emission_factor_lookup",
          "Look up the grid electricity emission factor (kgCO2/kWh) of a country/region.",
          {"type": "object", "properties": {"region": {"type": "string"}},
           "required": ["region"]}, domain="energy")
    def emission_factor_lookup(region: str) -> Any:
        factor = GRID_FACTORS.get(region.strip().lower())
        if factor is None:
            raise ToolExecutionError(
                "unknown region %r; known: %s" % (region, ", ".join(sorted(GRID_FACTORS))))
        return {"region": region, "factor_kg_per_kwh": factor}
