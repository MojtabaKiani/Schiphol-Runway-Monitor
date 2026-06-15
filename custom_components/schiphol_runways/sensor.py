"""Sensor platform for Schiphol Runway Monitor — one entity per runway."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    RUNWAYS,
    STATE_BOTH,
    STATE_INBOUND,
    STATE_NOT_IN_USE,
    STATE_OUTBOUND,
    STATE_UNAVAILABLE,
)
from .coordinator import SchipholRunwayCoordinator

# Icon mapping per state
_STATE_ICONS = {
    STATE_NOT_IN_USE: "mdi:airplane-off",
    STATE_INBOUND: "mdi:airplane-landing",
    STATE_OUTBOUND: "mdi:airplane-takeoff",
    STATE_BOTH: "mdi:airplane",
    STATE_UNAVAILABLE: "mdi:airplane-alert",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up one sensor per Schiphol runway."""
    coordinator: SchipholRunwayCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        SchipholRunwaySensor(coordinator, designator, meta)
        for designator, meta in RUNWAYS.items()
    ]
    async_add_entities(entities)


class SchipholRunwaySensor(CoordinatorEntity[SchipholRunwayCoordinator], SensorEntity):
    """Sensor representing a single Schiphol runway."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SchipholRunwayCoordinator,
        designator: str,
        meta: dict[str, Any],
    ) -> None:
        super().__init__(coordinator)
        self._designator = designator
        self._runway_name = meta["name"]

        # Unique ID: domain + designator (e.g. "schiphol_runways_18L/36R")
        self._attr_unique_id = f"{DOMAIN}_{designator}"

        # Human-readable name: "18L/36R Aalsmeerbaan"
        self._attr_name = f"{designator} {self._runway_name}"

        # Device info groups all runway sensors under one device
        self._attr_device_info = {
            "identifiers": {(DOMAIN, "schiphol_eham")},
            "name": "Schiphol Airport (EHAM)",
            "manufacturer": "LVNL",
            "model": "Runway Status",
            "configuration_url": "https://www.lvnl.nl/omgeving/actueel-baangebruik-schiphol",
        }

    # ─────────────────────────────────────────────────────────────────────────
    # State
    # ─────────────────────────────────────────────────────────────────────────

    @property
    def _runway_data(self) -> dict[str, Any]:
        if self.coordinator.data:
            return self.coordinator.data.get(self._designator, {})
        return {}

    @property
    def native_value(self) -> str:
        """Return the sensor state."""
        data = self._runway_data
        return data.get("state", STATE_UNAVAILABLE)

    @property
    def icon(self) -> str:
        return _STATE_ICONS.get(self.native_value, "mdi:airplane-alert")

    # ─────────────────────────────────────────────────────────────────────────
    # Extra state attributes
    # ─────────────────────────────────────────────────────────────────────────

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self._runway_data
        attrs: dict[str, Any] = {
            "runway": self._designator,
            "name": self._runway_name,
            "landing_heading": data.get("landing_heading"),
            "takeoff_heading": data.get("takeoff_heading"),
            "data_source": "LVNL (Luchtverkeersleiding Nederland)",
            "data_url": "https://www.lvnl.nl/omgeving/actueel-baangebruik-schiphol",
        }

        # Add all raw active runways for debugging
        if self.coordinator.data:
            attrs["all_active_landing"] = self.coordinator.data.get("_raw_landing", [])
            attrs["all_active_takeoff"] = self.coordinator.data.get("_raw_takeoff", [])

        return attrs

    # ─────────────────────────────────────────────────────────────────────────
    # Availability
    # ─────────────────────────────────────────────────────────────────────────

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success and bool(self.coordinator.data)
