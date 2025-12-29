"""Number platform for Fellow Stagg EKG Pro kettle."""
from __future__ import annotations

import asyncio
import logging

from homeassistant.components.number import (
  NumberEntity,
  NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature, UnitOfTime
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
  """Set up Fellow Stagg number entities based on a config entry."""
  coordinator: FellowStaggDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
  async_add_entities([
    FellowStaggTargetTemperature(coordinator),
    FellowStaggHoldTime(coordinator),
    FellowStaggChimeVolume(coordinator),
    FellowStaggAltitude(coordinator),
  ])


class FellowStaggTargetTemperature(CoordinatorEntity[FellowStaggDataUpdateCoordinator], NumberEntity):
  """Number entity for Fellow Stagg kettle target temperature control."""

  _attr_has_entity_name = True
  _attr_name = "Target Temperature"
  _attr_icon = "mdi:thermometer"
  _attr_mode = NumberMode.BOX
  _attr_native_step = 0.5

  def __init__(self, coordinator: FellowStaggDataUpdateCoordinator) -> None:
    """Initialize the number entity."""
    super().__init__(coordinator)
    self._attr_unique_id = f"{coordinator._address}_target_temp_control"
    self._attr_device_info = coordinator.device_info
    
    self._attr_native_min_value = coordinator.min_temp
    self._attr_native_max_value = coordinator.max_temp
    self._attr_native_unit_of_measurement = coordinator.temperature_unit

  @property
  def native_value(self) -> float | None:
    """Return the current target temperature."""
    if self.coordinator.data is None:
      return None
    return self.coordinator.data.get("target_temp")

  async def async_set_native_value(self, value: float) -> None:
    """Set new target temperature."""
    _LOGGER.debug("Setting target temperature to %s", value)
    
    await self.coordinator.kettle.async_set_temperature(
      self.coordinator.ble_device,
      int(value),
      fahrenheit=self.coordinator.temperature_unit == UnitOfTemperature.FAHRENHEIT
    )
    await asyncio.sleep(0.5)
    await self.coordinator.async_request_refresh()


class FellowStaggHoldTime(CoordinatorEntity[FellowStaggDataUpdateCoordinator], NumberEntity):
  """Number entity for Fellow Stagg kettle hold time control."""

  _attr_has_entity_name = True
  _attr_name = "Hold Time"
  _attr_icon = "mdi:timer"
  _attr_mode = NumberMode.BOX
  _attr_native_step = 1
  _attr_native_min_value = 0
  _attr_native_max_value = 60
  _attr_native_unit_of_measurement = UnitOfTime.MINUTES

  def __init__(self, coordinator: FellowStaggDataUpdateCoordinator) -> None:
    """Initialize the number entity."""
    super().__init__(coordinator)
    self._attr_unique_id = f"{coordinator._address}_hold_time_control"
    self._attr_device_info = coordinator.device_info

  @property
  def native_value(self) -> int | None:
    """Return the current hold time."""
    if self.coordinator.data is None:
      return None
    return self.coordinator.data.get("hold_time_minutes")

  async def async_set_native_value(self, value: float) -> None:
    """Set new hold time."""
    _LOGGER.debug("Setting hold time to %s minutes", value)
    
    await self.coordinator.kettle.async_set_hold_time(
      self.coordinator.ble_device,
      int(value)
    )
    await asyncio.sleep(0.5)
    await self.coordinator.async_request_refresh()


class FellowStaggChimeVolume(CoordinatorEntity[FellowStaggDataUpdateCoordinator], NumberEntity):
  """Number entity for Fellow Stagg kettle chime volume control."""

  _attr_has_entity_name = True
  _attr_name = "Chime Volume"
  _attr_icon = "mdi:volume-high"
  _attr_mode = NumberMode.SLIDER
  _attr_native_step = 1
  _attr_native_min_value = 0
  _attr_native_max_value = 10
  _attr_entity_category = EntityCategory.CONFIG

  def __init__(self, coordinator: FellowStaggDataUpdateCoordinator) -> None:
    """Initialize the number entity."""
    super().__init__(coordinator)
    self._attr_unique_id = f"{coordinator._address}_chime_volume_control"
    self._attr_device_info = coordinator.device_info

  @property
  def native_value(self) -> int | None:
    """Return the current chime volume."""
    if self.coordinator.data is None:
      return None
    return self.coordinator.data.get("chime_volume")

  async def async_set_native_value(self, value: float) -> None:
    """Set new chime volume."""
    _LOGGER.debug("Setting chime volume to %s", value)
    
    await self.coordinator.kettle.async_set_chime_volume(
      self.coordinator.ble_device,
      int(value)
    )
    await asyncio.sleep(0.5)
    await self.coordinator.async_request_refresh()


class FellowStaggAltitude(CoordinatorEntity[FellowStaggDataUpdateCoordinator], NumberEntity):
  """Number entity for Fellow Stagg kettle altitude compensation."""

  _attr_has_entity_name = True
  _attr_name = "Altitude"
  _attr_icon = "mdi:elevation-rise"
  _attr_mode = NumberMode.BOX
  _attr_native_step = 30
  _attr_native_min_value = 0
  _attr_native_max_value = 3000
  _attr_native_unit_of_measurement = "m"
  _attr_entity_category = EntityCategory.CONFIG

  def __init__(self, coordinator: FellowStaggDataUpdateCoordinator) -> None:
    """Initialize the number entity."""
    super().__init__(coordinator)
    self._attr_unique_id = f"{coordinator._address}_altitude_control"
    self._attr_device_info = coordinator.device_info

  @property
  def native_value(self) -> int | None:
    """Return the current altitude."""
    if self.coordinator.data is None:
      return None
    return self.coordinator.data.get("altitude_meters")

  async def async_set_native_value(self, value: float) -> None:
    """Set new altitude."""
    _LOGGER.debug("Setting altitude to %s meters", value)
    
    await self.coordinator.kettle.async_set_altitude(
      self.coordinator.ble_device,
      int(value)
    )
    await asyncio.sleep(0.5)
    await self.coordinator.async_request_refresh() 
