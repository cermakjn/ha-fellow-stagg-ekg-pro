"""Support for Fellow Stagg EKG Pro kettles."""
import logging
from datetime import timedelta
from typing import Any

import voluptuous as vol

from homeassistant.components.bluetooth import (
    async_ble_device_from_address,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform, UnitOfTemperature
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
)
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
from .kettle_ble import KettleBLEClient, ScheduleMode

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.SWITCH, Platform.NUMBER, Platform.SELECT, Platform.WATER_HEATER, Platform.BUTTON]
POLLING_INTERVAL = timedelta(seconds=5)  # Poll every 5 seconds (minimum allowed)

# Service constants
SERVICE_SET_SCHEDULE = "set_schedule"
SERVICE_SCAN_DEVICES = "scan_devices"
ATTR_MODE = "mode"
ATTR_HOUR = "hour"
ATTR_MINUTE = "minute"
ATTR_TEMPERATURE = "temperature"

SERVICE_SET_SCHEDULE_SCHEMA = vol.Schema({
    vol.Required(ATTR_MODE): vol.In(["off", "once", "daily"]),
    vol.Optional(ATTR_HOUR, default=7): vol.All(vol.Coerce(int), vol.Range(min=0, max=23)),
    vol.Optional(ATTR_MINUTE, default=0): vol.All(vol.Coerce(int), vol.Range(min=0, max=59)),
    vol.Optional(ATTR_TEMPERATURE, default=85): vol.All(vol.Coerce(float), vol.Range(min=40, max=100)),
})

# Temperature ranges for the kettle
MIN_TEMP_F = 104
MAX_TEMP_F = 212
MIN_TEMP_C = 40
MAX_TEMP_C = 100


class FellowStaggDataUpdateCoordinator(DataUpdateCoordinator):
  """Class to manage fetching Fellow Stagg data."""

  def __init__(self, hass: HomeAssistant, address: str) -> None:
    """Initialize the coordinator."""
    super().__init__(
      hass,
      _LOGGER,
      name=f"Fellow Stagg EKG Pro {address}",
      update_interval=POLLING_INTERVAL,
    )
    self.kettle = KettleBLEClient(address)
    self.ble_device = None
    self._address = address

    self.device_info = DeviceInfo(
      identifiers={(DOMAIN, address)},
      name=f"Fellow Stagg EKG Pro {address}",
      manufacturer="Fellow",
      model="Stagg EKG Pro",
    )

  @property
  def temperature_unit(self) -> str:
    """Get the current temperature unit."""
    return UnitOfTemperature.FAHRENHEIT if self.data and self.data.get("units") == "F" else UnitOfTemperature.CELSIUS

  @property
  def min_temp(self) -> float:
    """Get the minimum temperature based on current units."""
    return MIN_TEMP_F if self.temperature_unit == UnitOfTemperature.FAHRENHEIT else MIN_TEMP_C

  @property
  def max_temp(self) -> float:
    """Get the maximum temperature based on current units."""
    return MAX_TEMP_F if self.temperature_unit == UnitOfTemperature.FAHRENHEIT else MAX_TEMP_C

  async def _async_update_data(self) -> dict[str, Any] | None:
    """Fetch data from the kettle."""
    _LOGGER.debug("Starting poll for Fellow Stagg kettle %s", self._address)
    
    self.ble_device = async_ble_device_from_address(self.hass, self._address, True)
    if not self.ble_device:
      _LOGGER.debug("No connectable device found")
      return None
        
    try:
      _LOGGER.debug("Attempting to poll kettle data...")
      data = await self.kettle.async_poll(self.ble_device)
      _LOGGER.debug(
        "Successfully polled data from kettle %s: %s",
        self._address,
        data,
      )
      
      # Log any changes in data compared to previous state
      if self.data is not None:
        changes = {
          k: (self.data.get(k), v) 
          for k, v in data.items() 
          if k in self.data and self.data.get(k) != v
        }
        if changes:
          _LOGGER.debug("Data changes detected: %s", changes)
      
      return data
    except Exception as e:
      _LOGGER.error(
        "Error polling Fellow Stagg kettle %s: %s",
        self._address,
        str(e),
      )
      return None


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
  """Set up the Fellow Stagg integration."""
  return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
  """Set up Fellow Stagg integration from a config entry."""
  address = entry.unique_id
  if address is None:
    _LOGGER.error("No unique ID provided in config entry")
    return False

  _LOGGER.debug("Setting up Fellow Stagg integration for device: %s", address)
  coordinator = FellowStaggDataUpdateCoordinator(hass, address)

  # Do first update
  await coordinator.async_config_entry_first_refresh()

  hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

  # Register the set_schedule service
  async def async_handle_set_schedule(call: ServiceCall) -> None:
    """Handle the set_schedule service call."""
    mode_str = call.data[ATTR_MODE]
    hour = call.data[ATTR_HOUR]
    minute = call.data[ATTR_MINUTE]
    temperature = call.data[ATTR_TEMPERATURE]
    
    mode_map = {"off": ScheduleMode.OFF, "once": ScheduleMode.ONCE, "daily": ScheduleMode.DAILY}
    mode = mode_map[mode_str]
    
    _LOGGER.debug(
      "Setting schedule: mode=%s, hour=%s, minute=%s, temp=%s",
      mode_str, hour, minute, temperature
    )
    
    # Apply to all coordinators (in case of multiple kettles)
    for coord in hass.data[DOMAIN].values():
      if isinstance(coord, FellowStaggDataUpdateCoordinator):
        await coord.kettle.async_set_schedule(
          coord.ble_device,
          mode,
          hour,
          minute,
          temperature
        )
        await coord.async_request_refresh()
  
  # Only register service once (first entry)
  if not hass.services.has_service(DOMAIN, SERVICE_SET_SCHEDULE):
    hass.services.async_register(
      DOMAIN,
      SERVICE_SET_SCHEDULE,
      async_handle_set_schedule,
      schema=SERVICE_SET_SCHEDULE_SCHEMA,
    )

  # Register scan_devices service
  async def async_handle_scan_devices(call: ServiceCall) -> dict:
    """Handle the scan_devices service call."""
    _LOGGER.info("Scanning for Fellow Stagg EKG Pro kettles...")
    
    # Get all discovered BLE devices
    discovered = async_discovered_service_info(hass, connectable=True)
    
    fellow_devices = []
    all_ble_devices = []
    
    for service_info in discovered:
      name = service_info.name or ""
      device_info = {
        "name": name,
        "address": service_info.address,
        "rssi": service_info.rssi,
      }
      all_ble_devices.append(device_info)
      
      # Fellow Stagg kettles typically have "Stagg" or "Fellow" in their name
      if "stagg" in name.lower() or "fellow" in name.lower() or "ekg" in name.lower():
        fellow_devices.append(device_info)
        _LOGGER.info("Found Fellow device: %s (%s) RSSI: %s", name, service_info.address, service_info.rssi)
    
    if fellow_devices:
      _LOGGER.info("Scan complete. Found %d Fellow Stagg device(s)", len(fellow_devices))
    else:
      _LOGGER.info("Scan complete. No Fellow Stagg devices found. Make sure the kettle is on and in range.")
    
    return {
      "fellow_devices": fellow_devices,
      "fellow_count": len(fellow_devices),
      "all_ble_devices": all_ble_devices,
      "total_ble_count": len(all_ble_devices),
    }

  if not hass.services.has_service(DOMAIN, SERVICE_SCAN_DEVICES):
    hass.services.async_register(
      DOMAIN,
      SERVICE_SCAN_DEVICES,
      async_handle_scan_devices,
      supports_response=SupportsResponse.OPTIONAL,
    )

  await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
  
  _LOGGER.debug("Setup complete for Fellow Stagg device: %s", address)
  return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
  """Unload a config entry."""
  _LOGGER.debug("Unloading Fellow Stagg integration for entry: %s", entry.entry_id)
  if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
    hass.data[DOMAIN].pop(entry.entry_id)
  return unload_ok


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
  """Migrate old entry."""
  return True
