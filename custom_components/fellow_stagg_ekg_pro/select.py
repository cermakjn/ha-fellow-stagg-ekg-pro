"""Select platform for Fellow Stagg EKG Pro kettle."""
from __future__ import annotations

import asyncio
import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import FellowStaggDataUpdateCoordinator
from .const import DOMAIN
from .kettle_ble import ClockMode, ScheduleMode

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
  hass: HomeAssistant,
  entry: ConfigEntry,
  async_add_entities: AddEntitiesCallback,
) -> None:
  """Set up Fellow Stagg select entities based on a config entry."""
  coordinator: FellowStaggDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
  async_add_entities([
    FellowStaggClockModeSelect(coordinator),
    FellowStaggUnitsSelect(coordinator),
    FellowStaggScheduleModeSelect(coordinator),
  ])


class FellowStaggClockModeSelect(CoordinatorEntity[FellowStaggDataUpdateCoordinator], SelectEntity):
  """Select entity for Fellow Stagg kettle clock mode."""

  _attr_has_entity_name = True
  _attr_name = "Clock Mode"
  _attr_icon = "mdi:clock-outline"
  _attr_options = ["off", "digital", "analog"]
  _attr_entity_category = EntityCategory.CONFIG

  def __init__(self, coordinator: FellowStaggDataUpdateCoordinator) -> None:
    """Initialize the select entity."""
    super().__init__(coordinator)
    self._attr_unique_id = f"{coordinator._address}_clock_mode_control"
    self._attr_device_info = coordinator.device_info

  @property
  def current_option(self) -> str | None:
    """Return the current clock mode."""
    if self.coordinator.data is None:
      return None
    return self.coordinator.data.get("clock_mode")

  async def async_select_option(self, option: str) -> None:
    """Set the clock mode."""
    _LOGGER.debug("Setting clock mode to %s", option)
    
    mode_map = {
      "off": ClockMode.OFF,
      "digital": ClockMode.DIGITAL,
      "analog": ClockMode.ANALOG,
    }
    mode = mode_map.get(option, ClockMode.OFF)
    
    # Get current clock time to preserve it
    hours = self.coordinator.data.get("clock_hours", 0) if self.coordinator.data else 0
    minutes = self.coordinator.data.get("clock_minutes", 0) if self.coordinator.data else 0
    
    await self.coordinator.kettle.async_set_clock_time(
      self.coordinator.ble_device,
      hours,
      minutes,
      mode
    )
    await asyncio.sleep(0.5)
    await self.coordinator.async_request_refresh()


class FellowStaggUnitsSelect(CoordinatorEntity[FellowStaggDataUpdateCoordinator], SelectEntity):
  """Select entity for Fellow Stagg kettle temperature units."""

  _attr_has_entity_name = True
  _attr_name = "Temperature Units"
  _attr_icon = "mdi:temperature-celsius"
  _attr_options = ["Celsius", "Fahrenheit"]
  _attr_entity_category = EntityCategory.CONFIG

  def __init__(self, coordinator: FellowStaggDataUpdateCoordinator) -> None:
    """Initialize the select entity."""
    super().__init__(coordinator)
    self._attr_unique_id = f"{coordinator._address}_units_control"
    self._attr_device_info = coordinator.device_info

  @property
  def current_option(self) -> str | None:
    """Return the current temperature units."""
    if self.coordinator.data is None:
      return None
    units = self.coordinator.data.get("units")
    if units == "C":
      return "Celsius"
    elif units == "F":
      return "Fahrenheit"
    return None

  async def async_select_option(self, option: str) -> None:
    """Set the temperature units."""
    _LOGGER.debug("Setting temperature units to %s", option)
    
    celsius = option == "Celsius"
    
    await self.coordinator.kettle.async_set_units(
      self.coordinator.ble_device,
      celsius
    )
    await asyncio.sleep(0.5)
    await self.coordinator.async_request_refresh()


class FellowStaggScheduleModeSelect(CoordinatorEntity[FellowStaggDataUpdateCoordinator], SelectEntity):
  """Select entity for Fellow Stagg kettle schedule mode."""

  _attr_has_entity_name = True
  _attr_name = "Schedule Mode"
  _attr_options = ["off", "once", "daily"]

  def __init__(self, coordinator: FellowStaggDataUpdateCoordinator) -> None:
    """Initialize the select entity."""
    super().__init__(coordinator)
    self._attr_unique_id = f"{coordinator._address}_schedule_mode_control"
    self._attr_device_info = coordinator.device_info

  @property
  def icon(self) -> str:
    """Return the icon for the schedule mode."""
    return "mdi:calendar-clock"

  @property
  def current_option(self) -> str | None:
    """Return the current schedule mode."""
    if self.coordinator.data is None:
      return None
    return self.coordinator.data.get("schedule_mode", "off")

  async def async_select_option(self, option: str) -> None:
    """Set the schedule mode."""
    _LOGGER.debug("Setting schedule mode to %s", option)
    
    mode_map = {
      "off": ScheduleMode.OFF,
      "once": ScheduleMode.ONCE,
      "daily": ScheduleMode.DAILY,
    }
    mode = mode_map.get(option, ScheduleMode.OFF)
    
    # Get current schedule settings to preserve them
    if self.coordinator.data:
      hour = self.coordinator.data.get("schedule_hours") or 7
      minute = self.coordinator.data.get("schedule_minutes") or 0
      temp = self.coordinator.data.get("schedule_temperature") or 85.0
    else:
      hour, minute, temp = 7, 0, 85.0
    
    await self.coordinator.kettle.async_set_schedule(
      self.coordinator.ble_device,
      mode,
      hour,
      minute,
      temp
    )
    await asyncio.sleep(0.5)
    await self.coordinator.async_request_refresh()
