"""Schiphol Runway Monitor — Home Assistant custom integration.

Provides one sensor per Schiphol runway with states:
  not_in_use | inbound | outbound | inbound_and_outbound

Data source: LVNL (Luchtverkeersleiding Nederland)
  https://www.lvnl.nl/omgeving/actueel-baangebruik-schiphol
"""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN
from .coordinator import SchipholRunwayCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Schiphol Runway Monitor from a config entry."""
    scan_interval = entry.options.get("scan_interval", DEFAULT_SCAN_INTERVAL)

    coordinator = SchipholRunwayCoordinator(hass, scan_interval)

    # Do the first refresh — raises ConfigEntryNotReady if it fails
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as exc:
        raise ConfigEntryNotReady(
            f"Unable to fetch Schiphol runway data: {exc}"
        ) from exc

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Re-create coordinator when options change (e.g. scan_interval updated)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update (e.g. user changed poll interval)."""
    await hass.config_entries.async_reload(entry.entry_id)
