"""Water heater platform for Fellow Stagg EKG Pro kettle."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.components.water_heater import (
  WaterHeaterEntity,
  WaterHeaterEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
  ATTR_TEMPERATURE,
  UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import FellowStaggDataUpdateCoordinator
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
  hass: HomeAssistant,
  entry: ConfigEntry,
  async_add_entities: AddEntitiesCallback,
) -> None:
  """Set up Fellow Stagg water heater based on a config entry."""
  coordinator: FellowStaggDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
  async_add_entities([FellowStaggWaterHeater(coordinator)])


class FellowStaggWaterHeater(CoordinatorEntity[FellowStaggDataUpdateCoordinator], WaterHeaterEntity):
  """Water heater entity for Fellow Stagg EKG Pro kettle."""

  _attr_has_entity_name = True
  _attr_name = "Water Heater"
  _attr_supported_features = WaterHeaterEntityFeature.TARGET_TEMPERATURE
  _attr_operation_list = ["off", "hold"]

  def __init__(self, coordinator: FellowStaggDataUpdateCoordinator) -> None:
    """Initialize the water heater."""
    super().__init__(coordinator)
    self._attr_unique_id = f"{coordinator._address}_water_heater"
    self._attr_device_info = coordinator.device_info
    
    self._attr_min_temp = coordinator.min_temp
    self._attr_max_temp = coordinator.max_temp
    self._attr_temperature_unit = coordinator.temperature_unit

  @property
  def current_temperature(self) -> float | None:
    """Return the target temperature (EKG Pro doesn't report current temp)."""
    if self.coordinator.data is None:
      return None
    return self.coordinator.data.get("target_temp")

  @property
  def target_temperature(self) -> float | None:
    """Return the target temperature."""
    if self.coordinator.data is None:
      return None
    return self.coordinator.data.get("target_temp")

  @property
  def current_operation(self) -> str | None:
    """Return current operation based on hold mode."""
    if self.coordinator.data is None:
      return None
    return "hold" if self.coordinator.data.get("hold") else "off"

  async def async_set_temperature(self, **kwargs: Any) -> None:
    """Set new target temperature."""
    temperature = kwargs.get(ATTR_TEMPERATURE)
    if temperature is None:
      return

    _LOGGER.debug("Setting water heater target temperature to %s", temperature)
    
    await self.coordinator.kettle.async_set_temperature(
      self.coordinator.ble_device,
      int(temperature),
      fahrenheit=self.coordinator.temperature_unit == UnitOfTemperature.FAHRENHEIT
    )
    await asyncio.sleep(0.5)
    await self.coordinator.async_request_refresh() 
