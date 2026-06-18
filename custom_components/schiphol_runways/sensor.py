"""Sensor platform for Schiphol Runway Monitor.

Entities created:
  • 6 × runway sensor        — state: not_in_use / inbound / outbound / inbound_and_outbound
  • 1 × combined peak sensor — state: no_peak / inbound_peak / outbound_peak / inbound_and_outbound_peak
  • 1 × inbound peak boolean — state: true / false
  • 1 × outbound peak boolean— state: true / false
"""
from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.components.sensor import SensorEntity
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
    STATE_NO_PEAK,
    STATE_PEAK_BOTH,
    STATE_PEAK_INBOUND,
    STATE_PEAK_OUTBOUND,
)
from .coordinator import SchipholRunwayCoordinator

# ── Icon maps ─────────────────────────────────────────────────────────────────

_RUNWAY_ICONS = {
    STATE_NOT_IN_USE: "mdi:airplane-off",
    STATE_INBOUND:    "mdi:airplane-landing",
    STATE_OUTBOUND:   "mdi:airplane-takeoff",
    STATE_BOTH:       "mdi:airplane",
}

_PEAK_ICONS = {
    STATE_NO_PEAK:       "mdi:clock-outline",
    STATE_PEAK_INBOUND:  "mdi:airplane-landing",
    STATE_PEAK_OUTBOUND: "mdi:airplane-takeoff",
    STATE_PEAK_BOTH:     "mdi:airplane",
}

# ── Shared device info ────────────────────────────────────────────────────────

def _device_info() -> dict:
    return {
        "identifiers": {(DOMAIN, "schiphol_eham")},
        "name": "Schiphol Airport (EHAM)",
        "manufacturer": "LVNL",
        "model": "Runway Status",
        "configuration_url": "https://www.dutchplanespotters.nl/runways/ams/",
    }


# ── Platform setup ────────────────────────────────────────────────────────────

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: SchipholRunwayCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list = [
        SchipholRunwaySensor(coordinator, designator, meta)
        for designator, meta in RUNWAYS.items()
    ]
    entities.append(SchipholPeakTimeSensor(coordinator))
    async_add_entities(entities)


# ── Runway sensor ─────────────────────────────────────────────────────────────

class SchipholRunwaySensor(CoordinatorEntity[SchipholRunwayCoordinator], SensorEntity):
    """One sensor per Schiphol runway.

    States:
      not_in_use             — runway is not active
      inbound                — runway is used for landings
      outbound               — runway is used for takeoffs
      inbound_and_outbound   — runway is used for both simultaneously

    Attributes:
      runway          — designator string, e.g. "18L/36R"
      name            — Dutch name, e.g. "Aalsmeerbaan"
      landing_heading — active landing heading (e.g. "18L") or null
      takeoff_heading — active takeoff heading (e.g. "36R") or null
      all_active_landing — list of all currently active landing headings at Schiphol
      all_active_takeoff — list of all currently active takeoff headings at Schiphol
      data_source     — attribution string
    """

    _attr_has_entity_name = True

    def __init__(self, coordinator, designator: str, meta: dict) -> None:
        super().__init__(coordinator)
        self._designator  = designator
        self._runway_name = meta["name"]
        self._attr_unique_id   = f"{DOMAIN}_{designator}"
        self._attr_name        = f"{designator} {self._runway_name}"
        self._attr_device_info = _device_info()

    @property
    def _data(self) -> dict[str, Any]:
        if self.coordinator.data:
            return self.coordinator.data.get(self._designator, {})
        return {}

    @property
    def native_value(self) -> str:
        return self._data.get("state", STATE_NOT_IN_USE)

    @property
    def icon(self) -> str:
        return _RUNWAY_ICONS.get(self.native_value, "mdi:airplane-off")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self._data
        attrs: dict[str, Any] = {
            "runway":          self._designator,
            "name":            self._runway_name,
            "landing_heading": data.get("landing_heading"),
            "takeoff_heading": data.get("takeoff_heading"),
            "data_source":     "LVNL via dutchplanespotters.nl",
        }
        if self.coordinator.data:
            attrs["all_active_landing"] = self.coordinator.data.get("_raw_landing", [])
            attrs["all_active_takeoff"] = self.coordinator.data.get("_raw_takeoff", [])
        return attrs

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success and bool(self.coordinator.data)


# ── Combined peak sensor ──────────────────────────────────────────────────────

class SchipholPeakTimeSensor(CoordinatorEntity[SchipholRunwayCoordinator], SensorEntity):
    """Combined peak-time sensor.

    States:
      no_peak                   — no peak period active
      inbound_peak              — arrival peak active
      outbound_peak             — departure peak active
      inbound_and_outbound_peak — both peaks overlap

    Attributes:
      inbound_peak        — bool, true if inbound peak active
      outbound_peak       — bool, true if outbound peak active
      next_inbound_peak   — next inbound peak window "HH:MM - HH:MM" or null
      next_outbound_peak  — next outbound peak window "HH:MM - HH:MM" or null
      all_peaks           — full list of peak windows from the API
      data_source         — attribution string
    """

    _attr_has_entity_name = True

    def __init__(self, coordinator: SchipholRunwayCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id   = f"{DOMAIN}_peak_time"
        self._attr_name        = "Peak Time"
        self._attr_device_info = _device_info()

    @property
    def _peaks(self) -> dict[str, Any]:
        if self.coordinator.data:
            return self.coordinator.data.get("_peaks", {})
        return {}

    @property
    def native_value(self) -> str:
        return self._peaks.get("peak_state", STATE_NO_PEAK)

    @property
    def icon(self) -> str:
        return _PEAK_ICONS.get(self.native_value, "mdi:clock-outline")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        peaks = self._peaks
        return {
            "inbound_peak":       peaks.get("inbound_peak", False),
            "outbound_peak":      peaks.get("outbound_peak", False),
            "next_inbound_peak":  peaks.get("next_inbound_peak"),
            "next_outbound_peak": peaks.get("next_outbound_peak"),
            "all_peaks":          peaks.get("all_peaks", []),
            "data_source":        "LVNL via dutchplanespotters.nl",
        }

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success and bool(self.coordinator.data)


# ── Inbound peak binary sensor ────────────────────────────────────────────────

class SchipholInboundPeakBinarySensor(
    CoordinatorEntity[SchipholRunwayCoordinator], BinarySensorEntity
):
    """Boolean sensor: true when an inbound (landing) peak is active.

    Use this directly in automations:
      trigger:
        platform: state
        entity_id: binary_sensor.schiphol_inbound_peak
        to: "on"

    Attributes:
      next_inbound_peak  — next upcoming inbound peak window "HH:MM - HH:MM" or null
      all_inbound_peaks  — list of all inbound peak windows today
    """

    _attr_has_entity_name = True
    _attr_device_class    = BinarySensorDeviceClass.RUNNING

    def __init__(self, coordinator: SchipholRunwayCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id   = f"{DOMAIN}_inbound_peak"
        self._attr_name        = "Inbound Peak"
        self._attr_device_info = _device_info()

    @property
    def _peaks(self) -> dict[str, Any]:
        if self.coordinator.data:
            return self.coordinator.data.get("_peaks", {})
        return {}

    @property
    def is_on(self) -> bool:
        return self._peaks.get("inbound_peak", False)

    @property
    def icon(self) -> str:
        return "mdi:airplane-landing" if self.is_on else "mdi:clock-outline"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        peaks = self._peaks
        all_peaks = peaks.get("all_peaks", [])
        return {
            "next_inbound_peak": peaks.get("next_inbound_peak"),
            "all_inbound_peaks": [
                p.get("inbound", "") for p in all_peaks if p.get("inbound", "").strip()
            ],
        }

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success and bool(self.coordinator.data)


# ── Outbound peak binary sensor ───────────────────────────────────────────────

class SchipholOutboundPeakBinarySensor(
    CoordinatorEntity[SchipholRunwayCoordinator], BinarySensorEntity
):
    """Boolean sensor: true when an outbound (departure) peak is active.

    Use this directly in automations:
      trigger:
        platform: state
        entity_id: binary_sensor.schiphol_outbound_peak
        to: "on"

    Attributes:
      next_outbound_peak  — next upcoming outbound peak window "HH:MM - HH:MM" or null
      all_outbound_peaks  — list of all outbound peak windows today
    """

    _attr_has_entity_name = True
    _attr_device_class    = BinarySensorDeviceClass.RUNNING

    def __init__(self, coordinator: SchipholRunwayCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id   = f"{DOMAIN}_outbound_peak"
        self._attr_name        = "Outbound Peak"
        self._attr_device_info = _device_info()

    @property
    def _peaks(self) -> dict[str, Any]:
        if self.coordinator.data:
            return self.coordinator.data.get("_peaks", {})
        return {}

    @property
    def is_on(self) -> bool:
        return self._peaks.get("outbound_peak", False)

    @property
    def icon(self) -> str:
        return "mdi:airplane-takeoff" if self.is_on else "mdi:clock-outline"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        peaks = self._peaks
        all_peaks = peaks.get("all_peaks", [])
        return {
            "next_outbound_peak": peaks.get("next_outbound_peak"),
            "all_outbound_peaks": [
                p.get("outbound", "") for p in all_peaks if p.get("outbound", "").strip()
            ],
        }

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success and bool(self.coordinator.data)
