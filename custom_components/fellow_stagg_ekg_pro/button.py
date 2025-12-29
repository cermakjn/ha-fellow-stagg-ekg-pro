"""Button platform for Fellow Stagg EKG Pro kettle."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import FellowStaggDataUpdateCoordinator
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Fellow Stagg buttons based on a config entry."""
    coordinator: FellowStaggDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        FellowStaggReloadButton(coordinator),
        FellowStaggSyncTimeButton(coordinator),
    ])


class FellowStaggReloadButton(CoordinatorEntity[FellowStaggDataUpdateCoordinator], ButtonEntity):
    """Button entity to reload data from Fellow Stagg kettle."""

    _attr_has_entity_name = True
    _attr_name = "Reload Data"
    _attr_icon = "mdi:refresh"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: FellowStaggDataUpdateCoordinator) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator._address}_reload"
        self._attr_device_info = coordinator.device_info

    async def async_press(self) -> None:
        """Handle the button press - reload data from kettle."""
        _LOGGER.debug("Reload button pressed - refreshing data from kettle")
        await self.coordinator.async_request_refresh()


class FellowStaggSyncTimeButton(CoordinatorEntity[FellowStaggDataUpdateCoordinator], ButtonEntity):
    """Button entity to synchronize kettle time with system time."""

    _attr_has_entity_name = True
    _attr_name = "Sync Time"
    _attr_icon = "mdi:wrench-clock-outline"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: FellowStaggDataUpdateCoordinator) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator._address}_sync_time"
        self._attr_device_info = coordinator.device_info

    async def async_press(self) -> None:
        """Handle the button press - sync time to kettle."""
        _LOGGER.debug("Sync time button pressed - synchronizing kettle time")
        
        # First reload data from kettle to get current state
        await self.coordinator.async_request_refresh()
        await asyncio.sleep(0.5)
        
        # Get current system time
        now = datetime.now()
        
        # Set the clock time on the kettle
        await self.coordinator.kettle.async_set_clock_time(
            self.coordinator.ble_device,
            hours=now.hour,
            minutes=now.minute
        )
        
        _LOGGER.info("Kettle time synchronized to %02d:%02d", now.hour, now.minute)
        
        # Refresh to confirm the change
        await asyncio.sleep(0.5)
        await self.coordinator.async_request_refresh()
