"""Switch platform for Fellow Stagg EKG Pro kettle."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
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
  """Set up Fellow Stagg switches based on a config entry."""
  coordinator: FellowStaggDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
  async_add_entities([
    FellowStaggPreBoilSwitch(coordinator),
  ])


class FellowStaggPreBoilSwitch(CoordinatorEntity[FellowStaggDataUpdateCoordinator], SwitchEntity):
  """Switch entity for Fellow Stagg kettle pre-boil control."""

  _attr_has_entity_name = True
  _attr_name = "Pre-Boil"
  _attr_icon = "mdi:water-boiler"
  _attr_entity_category = EntityCategory.CONFIG

  def __init__(self, coordinator: FellowStaggDataUpdateCoordinator) -> None:
    """Initialize the switch."""
    super().__init__(coordinator)
    self._attr_unique_id = f"{coordinator._address}_pre_boil"
    self._attr_device_info = coordinator.device_info

  @property
  def is_on(self) -> bool | None:
    """Return true if pre-boil is enabled."""
    if self.coordinator.data is None:
      return None
    return self.coordinator.data.get("pre_boil_enabled")

  async def async_turn_on(self, **kwargs: Any) -> None:
    """Enable pre-boil."""
    _LOGGER.debug("Enabling pre-boil")
    await self.coordinator.kettle.async_set_pre_boil(self.coordinator.ble_device, True)
    await asyncio.sleep(0.5)
    await self.coordinator.async_request_refresh()

  async def async_turn_off(self, **kwargs: Any) -> None:
    """Disable pre-boil."""
    _LOGGER.debug("Disabling pre-boil")
    await self.coordinator.kettle.async_set_pre_boil(self.coordinator.ble_device, False)
    await asyncio.sleep(0.5)
    await self.coordinator.async_request_refresh() 
