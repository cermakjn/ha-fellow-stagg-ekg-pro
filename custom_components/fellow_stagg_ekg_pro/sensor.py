"""Support for Fellow Stagg EKG Pro kettle sensors."""
from dataclasses import dataclass
from typing import Any, Callable

from homeassistant import config_entries
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import FellowStaggDataUpdateCoordinator
from .const import DOMAIN


@dataclass
class FellowStaggSensorEntityDescription(SensorEntityDescription):
    """Description of a Fellow Stagg sensor."""


# Define value functions separately to avoid serialization issues
VALUE_FUNCTIONS: dict[str, Callable[[dict[str, Any] | None], Any | None]] = {
    # Basic state
    "target_temp": lambda data: data.get("target_temp") if data else None,
    "units": lambda data: "Celsius" if data and data.get("units") == "C" else "Fahrenheit" if data else None,
    
    # Hold mode
    "hold": lambda data: "Active" if data and data.get("hold") else "Off",
    "hold_time_minutes": lambda data: data.get("hold_time_minutes") if data else None,
    
    # Pre-boil
    "pre_boil_enabled": lambda data: "Enabled" if data and data.get("pre_boil_enabled") else "Disabled",
    
    # Chime
    "chime_volume": lambda data: data.get("chime_volume") if data else None,
    "chime_enabled": lambda data: "Enabled" if data and data.get("chime_enabled") else "Disabled",
    
    # Clock
    "clock_mode": lambda data: data.get("clock_mode", "").title() if data else None,
    "clock_time": lambda data: data.get("clock_time") if data else None,
    
    # Altitude
    "altitude_meters": lambda data: data.get("altitude_meters") if data else None,
    
    # Schedule
    "schedule_enabled": lambda data: "Enabled" if data and data.get("schedule_enabled") else "Disabled",
    "schedule_mode": lambda data: data.get("schedule_mode", "").title() if data else None,
    "schedule_time": lambda data: data.get("schedule_time") if data else None,
    "schedule_temperature": lambda data: data.get("schedule_temperature") if data else None,
    
    # Language
    "language": lambda data: data.get("language", "").replace("_", " ").title() if data else None,
    
    # Debug
    "raw_data": lambda data: data.get("raw_data") if data else None,
}


def get_sensor_descriptions() -> list[FellowStaggSensorEntityDescription]:
    """Get sensor descriptions."""
    return [
        # Basic state sensors
        FellowStaggSensorEntityDescription(
            key="target_temp",
            name="Target Temperature",
            icon="mdi:thermometer-check",
            device_class=SensorDeviceClass.TEMPERATURE,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        ),
        FellowStaggSensorEntityDescription(
            key="units",
            name="Temperature Units",
            icon="mdi:temperature-celsius",
        ),
        
        # Hold mode sensors
        FellowStaggSensorEntityDescription(
            key="hold",
            name="Hold Mode",
            icon="mdi:timer-pause",
        ),
        FellowStaggSensorEntityDescription(
            key="hold_time_minutes",
            name="Hold Time",
            icon="mdi:timer",
            native_unit_of_measurement=UnitOfTime.MINUTES,
        ),
        
        # Pre-boil sensor
        FellowStaggSensorEntityDescription(
            key="pre_boil_enabled",
            name="Pre-Boil",
            icon="mdi:water-boiler",
        ),
        
        # Chime sensors
        FellowStaggSensorEntityDescription(
            key="chime_enabled",
            name="Chime",
            icon="mdi:bell",
        ),
        FellowStaggSensorEntityDescription(
            key="chime_volume",
            name="Chime Volume",
            icon="mdi:volume-high",
        ),
        
        # Clock sensors
        FellowStaggSensorEntityDescription(
            key="clock_mode",
            name="Clock Mode",
            icon="mdi:clock-outline",
        ),
        FellowStaggSensorEntityDescription(
            key="clock_time",
            name="Clock Time",
            icon="mdi:clock",
        ),
        
        # Altitude sensor
        FellowStaggSensorEntityDescription(
            key="altitude_meters",
            name="Altitude",
            icon="mdi:elevation-rise",
            native_unit_of_measurement="m",
        ),
        
        # Schedule sensors
        FellowStaggSensorEntityDescription(
            key="schedule_enabled",
            name="Schedule",
            icon="mdi:calendar-clock",
        ),
        FellowStaggSensorEntityDescription(
            key="schedule_mode",
            name="Schedule Mode",
            icon="mdi:calendar-edit",
        ),
        FellowStaggSensorEntityDescription(
            key="schedule_time",
            name="Schedule Time",
            icon="mdi:calendar-clock-outline",
        ),
        FellowStaggSensorEntityDescription(
            key="schedule_temperature",
            name="Schedule Temperature",
            icon="mdi:thermometer-alert",
            device_class=SensorDeviceClass.TEMPERATURE,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        ),
        
        # Language sensor
        FellowStaggSensorEntityDescription(
            key="language",
            name="Language",
            icon="mdi:translate",
        ),
        
        # Debug sensor
        FellowStaggSensorEntityDescription(
            key="raw_data",
            name="Raw Data",
            icon="mdi:code-json",
            entity_registry_enabled_default=False,  # Disabled by default
        ),
    ]


# Get sensor descriptions once at module load
SENSOR_DESCRIPTIONS = get_sensor_descriptions()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Fellow Stagg sensors."""
    coordinator: FellowStaggDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        FellowStaggSensor(coordinator, description)
        for description in SENSOR_DESCRIPTIONS
    )


class FellowStaggSensor(CoordinatorEntity[FellowStaggDataUpdateCoordinator], SensorEntity):
    """Fellow Stagg sensor."""

    entity_description: FellowStaggSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: FellowStaggDataUpdateCoordinator,
        description: FellowStaggSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator._address}_{description.key}"
        self._attr_device_info = coordinator.device_info

        # Update unit of measurement based on kettle's current units for temperature sensors
        if description.device_class == SensorDeviceClass.TEMPERATURE:
            if coordinator.data:
                is_fahrenheit = coordinator.data.get("units") == "F"
                self._attr_native_unit_of_measurement = (
                    UnitOfTemperature.FAHRENHEIT if is_fahrenheit else UnitOfTemperature.CELSIUS
                )

    @property
    def native_value(self) -> str | float | int | None:
        """Return the state of the sensor."""
        if self.coordinator.data is None:
            return None
        value_func = VALUE_FUNCTIONS.get(self.entity_description.key)
        if value_func:
            return value_func(self.coordinator.data)
        return None
