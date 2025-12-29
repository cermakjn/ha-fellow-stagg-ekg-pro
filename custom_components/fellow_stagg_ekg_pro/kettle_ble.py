"""
Fellow Stagg EKG Pro - BLE Client for Home Assistant
Adapted from ekg-pro-ble-lib for the Fellow Stagg EKG Pro kettle.

BLE Protocol Structure (17 bytes):
    - Byte 0: Status flags
        * Bit 3 (0x08): Schedule enabled (0=OFF, 1=ON)
    - Byte 1: Control flags
        * Bit 1 (0x02): Units (0=Fahrenheit, 1=Celsius)
        * Bit 3 (0x08): Pre-boil (0=OFF, 1=ON)
    - Byte 2-3: Altitude (meters, split across bytes with 0x80 offset in byte 3)
    - Byte 4: Target temperature (multiply by 2 for °C)
    - Byte 5: Unknown/status
    - Byte 6: Schedule target temperature (multiply by 2 for °C, 0xc0=disabled)
    - Byte 7: Unknown/status
    - Byte 8: Schedule minutes (0-59)
    - Byte 9: Schedule hours (0-23, 24-hour format)
    - Byte 10: Clock minutes (0-59)
    - Byte 11: Clock hours (0-23, 24-hour format)
    - Byte 12: Clock mode (0=OFF, 1=DIGITAL, 2=ANALOG)
    - Byte 13: Hold time in minutes (0-63, 0=OFF)
    - Byte 14: Chime volume (0=OFF, 1-10=volume level)
    - Byte 15: Languages
    - Byte 16: Counter (increments with each write)
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Optional, Callable, Any
from enum import Enum

from bleak import BleakClient
from bleak_retry_connector import establish_connection
from .const import MAIN_CONFIG_UUID

_LOGGER = logging.getLogger(__name__)


class ClockMode(Enum):
    """Clock display modes"""
    OFF = 0
    DIGITAL = 1
    ANALOG = 2


class Units(Enum):
    """Temperature units"""
    CELSIUS = 0x17
    FAHRENHEIT = 0x15


class ScheduleMode(Enum):
    """Schedule modes"""
    OFF = 0
    ONCE = 1
    DAILY = 2


class Language(Enum):
    """Menu languages"""
    ENGLISH = 0x00
    FRENCH = 0x01
    SPANISH = 0x02
    SIMPLIFIED_CHINESE = 0x03
    TRADITIONAL_CHINESE = 0x04


class KettleBLEClient:
    """BLE client for the Fellow Stagg EKG Pro kettle.
    
    This class provides a Home Assistant compatible interface for controlling
    the Fellow Stagg EKG Pro kettle via BLE.
    """

    def __init__(self, address: str):
        """Initialize the kettle BLE client.
        
        Args:
            address: BLE MAC address or UUID of the kettle
        """
        self.address = address
        self._client: Optional[BleakClient] = None
        self._state_data: Optional[bytearray] = None
        self._counter: int = 0
        self._timeout: float = 20.0
        self._last_command_time: float = 0
        self._notification_callback: Optional[Callable] = None

    async def _ensure_connected(self, ble_device) -> None:
        """Ensure BLE connection is established.
        
        Args:
            ble_device: The BLE device object from Home Assistant
        """
        if self._client is None or not self._client.is_connected:
            _LOGGER.debug("Connecting to kettle at %s", self.address)
            self._client = await establish_connection(
                BleakClient,
                ble_device,
                self.address,
                max_attempts=3,
            )
            
            if self._client.is_connected:
                _LOGGER.debug("Connected to Stagg EKG Pro at %s", self.address)
                # Start listening to notifications
                await self._client.start_notify(
                    MAIN_CONFIG_UUID, 
                    self._handle_notification
                )
            else:
                raise RuntimeError(f"Failed to connect to kettle at {self.address}")

    async def _ensure_debounce(self) -> None:
        """Ensure we don't send commands too frequently."""
        current_time = time.time() * 1000  # Current time in milliseconds
        if current_time - self._last_command_time < 200:  # 200ms debounce
            await asyncio.sleep(0.2)
        self._last_command_time = current_time

    def _handle_notification(self, sender, data: bytearray) -> None:
        """Handle BLE notifications from the kettle.
        
        Note: Notifications are only sent when settings are changed via the kettle's
        menu interface, not during heating or temperature changes.
        """
        self._state_data = bytearray(data)
        self._counter = data[16]
        _LOGGER.debug("Notification received: %s", data.hex())
        
        if self._notification_callback:
            self._notification_callback(self._parse_state())

    async def _refresh_state(self) -> None:
        """Read the current state from the kettle."""
        if not self._client or not self._client.is_connected:
            raise RuntimeError("Not connected to kettle")
        
        data = await self._client.read_gatt_char(MAIN_CONFIG_UUID)
        self._state_data = bytearray(data)
        self._counter = data[16]
        _LOGGER.debug("State refreshed: %s", data.hex())

    async def _write_state(self, new_data: bytearray) -> None:
        """Internal method to write state to kettle."""
        if not self._client or not self._client.is_connected:
            raise RuntimeError("Not connected to kettle")
        
        # Always update clock time to current system time before writing
        now = datetime.now()
        new_data[10] = now.minute
        new_data[11] = now.hour
        
        # Increment counter
        new_data[16] = (self._counter + 1) & 0xFF
        
        await self._ensure_debounce()
        await self._client.write_gatt_char(MAIN_CONFIG_UUID, bytes(new_data))
        _LOGGER.debug("Written: %s (clock synced to %02d:%02d)", 
                     new_data.hex(), now.hour, now.minute)
        
        # Update our state
        self._state_data = new_data
        self._counter = new_data[16]

    def _parse_state(self) -> dict[str, Any]:
        """Parse the internal state data into a dictionary.
        
        Returns:
            Dictionary with current state values:
            - target_temp: float - Target temperature in current units
            - units: str - "F" or "C"
            - hold: bool - Whether hold mode is active
            - hold_time_minutes: int - Hold time in minutes
            - pre_boil_enabled: bool - Whether pre-boil is enabled
            - chime_volume: int - Chime volume level (0-10)
            - chime_enabled: bool - Whether chime is enabled
            - clock_mode: str - Clock display mode (off/digital/analog)
            - clock_time: str - Clock time as HH:MM
            - altitude_meters: int - Altitude compensation
            - language: str - Menu language
            - schedule_enabled: bool - Whether schedule is active
            - schedule_mode: str - Schedule mode (off/once/daily)
            - schedule_time: str - Schedule time as HH:MM
            - schedule_temperature: float - Scheduled target temperature
        """
        if not self._state_data or len(self._state_data) < 17:
            return {}
        
        data = self._state_data
        
        # Parse temperature - stored as Celsius * 2
        target_temp_celsius = data[4] / 2.0
        
        # Parse settings byte 1
        is_celsius = bool(data[1] & 0x02)
        pre_boil_enabled = bool(data[1] & 0x08)
        
        # Convert temperature to current units
        if is_celsius:
            target_temp = target_temp_celsius
            units = "C"
        else:
            # Convert Celsius to Fahrenheit
            target_temp = (target_temp_celsius * 9/5) + 32
            units = "F"
        
        # Parse altitude
        byte2 = data[2]
        byte3 = data[3]
        altitude = ((byte3 & 0x7F) << 8) | byte2
        altitude = round(altitude / 30) * 30
        
        # Parse clock settings
        clock_minutes = data[10]
        clock_hours = data[11]
        clock_mode_val = data[12]
        
        if clock_mode_val == 0:
            clock_mode = "off"
        elif clock_mode_val == 1:
            clock_mode = "digital"
        elif clock_mode_val == 2:
            clock_mode = "analog"
        else:
            clock_mode = "unknown"
        
        # Parse hold time
        hold_time = data[13]
        
        # Parse chime volume
        chime_volume = data[14]
        
        # Parse schedule settings
        schedule_enabled = bool(data[0] & 0x08)
        schedule_minutes = data[8]
        schedule_hours = data[9]
        schedule_temp_raw = data[6]
        
        if schedule_enabled and schedule_temp_raw != 0xc0:
            schedule_temp_celsius = schedule_temp_raw / 2.0
            if is_celsius:
                schedule_temp = schedule_temp_celsius
            else:
                schedule_temp = (schedule_temp_celsius * 9/5) + 32
            # Check bit 3 of byte 16 for mode
            mode_bit = (data[16] >> 3) & 1
            schedule_mode = "once" if mode_bit == 1 else "daily"
        else:
            schedule_temp = None
            schedule_mode = "off"
        
        # Parse language
        languages = {0: "english", 1: "french", 2: "spanish", 3: "simplified_chinese", 4: "traditional_chinese"}
        language = languages.get(data[15], f"unknown_{data[15]}")
        
        return {
            # Basic state
            'target_temp': target_temp,
            'units': units,
            
            # Hold mode
            'hold': hold_time > 0,
            'hold_time_minutes': hold_time,
            
            # Settings
            'pre_boil_enabled': pre_boil_enabled,
            'chime_volume': chime_volume,
            'chime_enabled': chime_volume > 0,
            
            # Clock
            'clock_mode': clock_mode,
            'clock_hours': clock_hours,
            'clock_minutes': clock_minutes,
            'clock_time': f"{clock_hours:02d}:{clock_minutes:02d}",
            
            # Environment
            'altitude_meters': altitude,
            'language': language,
            
            # Schedule
            'schedule_enabled': schedule_enabled,
            'schedule_mode': schedule_mode,
            'schedule_hours': schedule_hours if schedule_enabled else None,
            'schedule_minutes': schedule_minutes if schedule_enabled else None,
            'schedule_time': f"{schedule_hours:02d}:{schedule_minutes:02d}" if schedule_enabled else None,
            'schedule_temperature': schedule_temp,
            
            # Debug
            'raw_data': data.hex(),
            'counter': data[16]
        }

    async def async_poll(self, ble_device) -> dict[str, Any]:
        """Connect to the kettle and return parsed state.
        
        Args:
            ble_device: The BLE device object from Home Assistant
            
        Returns:
            Dictionary with kettle state
        """
        try:
            await self._ensure_connected(ble_device)
            await self._refresh_state()
            state = self._parse_state()
            _LOGGER.debug("Polled state from kettle: %s", state)
            return state

        except Exception as err:
            _LOGGER.error("Error polling kettle: %s", err)
            if self._client and self._client.is_connected:
                try:
                    await self._client.disconnect()
                except Exception:
                    pass
            self._client = None
            return {}

    async def async_set_power(self, ble_device, power_on: bool) -> None:
        """Turn the kettle on or off by setting/clearing hold time.
        
        Note: The EKG Pro doesn't have a simple on/off power control via BLE.
        Instead, we control the hold time to achieve similar behavior.
        Setting hold time > 0 effectively "prepares" the kettle.
        
        Args:
            ble_device: The BLE device object from Home Assistant
            power_on: True to turn on, False to turn off
        """
        try:
            await self._ensure_connected(ble_device)
            
            if not self._state_data:
                await self._refresh_state()
            
            new_data = bytearray(self._state_data)
            
            if power_on:
                # Set a default hold time of 30 minutes if not already set
                if new_data[13] == 0:
                    new_data[13] = 30
            else:
                # Clear hold time to "turn off"
                new_data[13] = 0
            
            await self._write_state(new_data)
            _LOGGER.info("Power %s (hold time: %d min)", 
                        "ON" if power_on else "OFF", new_data[13])
            
        except Exception as err:
            _LOGGER.error("Error setting power state: %s", err)
            if self._client and self._client.is_connected:
                try:
                    await self._client.disconnect()
                except Exception:
                    pass
            self._client = None
            raise

    async def async_set_temperature(self, ble_device, temp: int, fahrenheit: bool = True) -> None:
        """Set target temperature.
        
        Args:
            ble_device: The BLE device object from Home Assistant
            temp: Target temperature in the specified unit
            fahrenheit: True if temp is in Fahrenheit, False for Celsius
        """
        # Convert to Celsius if needed
        if fahrenheit:
            temp_celsius = (temp - 32) * 5 / 9
        else:
            temp_celsius = temp
        
        # Clamp temperature to valid range (0-100°C)
        temp_celsius = max(0, min(100, temp_celsius))
        
        try:
            await self._ensure_connected(ble_device)
            
            if not self._state_data:
                await self._refresh_state()
            
            new_data = bytearray(self._state_data)
            new_data[4] = int(temp_celsius * 2)
            
            await self._write_state(new_data)
            _LOGGER.info("Target temperature set to %.1f°C (%.1f°F)", 
                        temp_celsius, (temp_celsius * 9/5) + 32)
            
        except Exception as err:
            _LOGGER.error("Error setting temperature: %s", err)
            if self._client and self._client.is_connected:
                try:
                    await self._client.disconnect()
                except Exception:
                    pass
            self._client = None
            raise

    async def async_set_hold_time(self, ble_device, minutes: int) -> None:
        """Set hold temperature time.
        
        Args:
            ble_device: The BLE device object from Home Assistant
            minutes: Hold time in minutes (0=OFF, 15-60 in 15-min increments)
        """
        minutes = max(0, min(60, minutes))
        
        try:
            await self._ensure_connected(ble_device)
            
            if not self._state_data:
                await self._refresh_state()
            
            new_data = bytearray(self._state_data)
            new_data[13] = minutes
            
            await self._write_state(new_data)
            
            if minutes == 0:
                _LOGGER.info("Hold mode disabled")
            else:
                _LOGGER.info("Hold time set to %d minutes", minutes)
                
        except Exception as err:
            _LOGGER.error("Error setting hold time: %s", err)
            if self._client and self._client.is_connected:
                try:
                    await self._client.disconnect()
                except Exception:
                    pass
            self._client = None
            raise

    async def async_set_pre_boil(self, ble_device, enabled: bool) -> None:
        """Enable or disable pre-boil feature.
        
        Args:
            ble_device: The BLE device object from Home Assistant
            enabled: True to enable pre-boil, False to disable
        """
        try:
            await self._ensure_connected(ble_device)
            
            if not self._state_data:
                await self._refresh_state()
            
            new_data = bytearray(self._state_data)
            
            if enabled:
                new_data[1] |= 0x08
            else:
                new_data[1] &= ~0x08
            
            await self._write_state(new_data)
            _LOGGER.info("Pre-boil %s", "enabled" if enabled else "disabled")
            
        except Exception as err:
            _LOGGER.error("Error setting pre-boil: %s", err)
            if self._client and self._client.is_connected:
                try:
                    await self._client.disconnect()
                except Exception:
                    pass
            self._client = None
            raise

    async def async_set_chime_volume(self, ble_device, volume: int) -> None:
        """Set the chime volume.
        
        Args:
            ble_device: The BLE device object from Home Assistant
            volume: Volume level 0-10 (0 = off)
        """
        volume = max(0, min(10, volume))
        
        try:
            await self._ensure_connected(ble_device)
            
            if not self._state_data:
                await self._refresh_state()
            
            new_data = bytearray(self._state_data)
            new_data[14] = volume
            
            await self._write_state(new_data)
            
            if volume == 0:
                _LOGGER.info("Chime disabled")
            else:
                _LOGGER.info("Chime volume set to %d", volume)
                
        except Exception as err:
            _LOGGER.error("Error setting chime volume: %s", err)
            if self._client and self._client.is_connected:
                try:
                    await self._client.disconnect()
                except Exception:
                    pass
            self._client = None
            raise

    async def async_set_units(self, ble_device, celsius: bool) -> None:
        """Set temperature units.
        
        Args:
            ble_device: The BLE device object from Home Assistant
            celsius: True for Celsius, False for Fahrenheit
        """
        try:
            await self._ensure_connected(ble_device)
            
            if not self._state_data:
                await self._refresh_state()
            
            new_data = bytearray(self._state_data)
            
            if celsius:
                new_data[1] |= 0x02
            else:
                new_data[1] &= ~0x02
            
            await self._write_state(new_data)
            _LOGGER.info("Units set to %s", "Celsius" if celsius else "Fahrenheit")
            
        except Exception as err:
            _LOGGER.error("Error setting units: %s", err)
            if self._client and self._client.is_connected:
                try:
                    await self._client.disconnect()
                except Exception:
                    pass
            self._client = None
            raise

    async def async_set_clock_time(self, ble_device, hours: int, minutes: int, 
                                   mode: Optional[ClockMode] = None) -> None:
        """Set the clock time and optionally the display mode.
        
        Args:
            ble_device: The BLE device object from Home Assistant
            hours: Hours in 24-hour format (0-23)
            minutes: Minutes (0-59)
            mode: Optional clock mode
        """
        if not (0 <= hours <= 23):
            raise ValueError("Hours must be between 0 and 23")
        if not (0 <= minutes <= 59):
            raise ValueError("Minutes must be between 0 and 59")
        
        try:
            await self._ensure_connected(ble_device)
            
            if not self._state_data:
                await self._refresh_state()
            
            new_data = bytearray(self._state_data)
            new_data[10] = minutes
            new_data[11] = hours
            
            if mode is not None:
                new_data[12] = mode.value
            
            await self._write_state(new_data)
            _LOGGER.info("Clock set to %02d:%02d%s", hours, minutes,
                        f" ({mode.name})" if mode else "")
            
        except Exception as err:
            _LOGGER.error("Error setting clock: %s", err)
            if self._client and self._client.is_connected:
                try:
                    await self._client.disconnect()
                except Exception:
                    pass
            self._client = None
            raise

    async def async_set_altitude(self, ble_device, altitude_meters: int) -> None:
        """Set the altitude compensation level.
        
        Args:
            ble_device: The BLE device object from Home Assistant
            altitude_meters: Altitude in meters (0-3000)
        """
        altitude_meters = max(0, min(3000, altitude_meters))
        quantized = round(altitude_meters / 30) * 30
        
        byte2 = quantized & 0xFF
        byte3 = 0x80 + ((quantized >> 8) & 0x7F)
        
        try:
            await self._ensure_connected(ble_device)
            
            if not self._state_data:
                await self._refresh_state()
            
            new_data = bytearray(self._state_data)
            new_data[2] = byte2
            new_data[3] = byte3
            
            await self._write_state(new_data)
            _LOGGER.info("Altitude set to %dm%s", quantized,
                        f" (rounded from {altitude_meters}m)" if quantized != altitude_meters else "")
            
        except Exception as err:
            _LOGGER.error("Error setting altitude: %s", err)
            if self._client and self._client.is_connected:
                try:
                    await self._client.disconnect()
                except Exception:
                    pass
            self._client = None
            raise

    async def async_set_schedule(self, ble_device, mode: ScheduleMode, 
                                  hour: int = 7, minute: int = 0, 
                                  temp_celsius: float = 85.0) -> None:
        """Set the schedule mode, time, and temperature.
        
        Args:
            ble_device: The BLE device object from Home Assistant
            mode: ScheduleMode.OFF, ONCE, or DAILY
            hour: Hour in 24-hour format (0-23)
            minute: Minute (0-59)
            temp_celsius: Schedule target temperature in Celsius (0-100)
        """
        try:
            await self._ensure_connected(ble_device)
            
            if not self._state_data:
                await self._refresh_state()
            
            if mode == ScheduleMode.OFF:
                # Disable schedule
                new_data = bytearray(self._state_data)
                new_data[0] &= ~0x08      # Clear schedule enable bit
                new_data[6] = 0xc0        # Clear schedule temperature
                new_data[8] = 0x00        # Clear minutes
                new_data[9] = 0x00        # Clear hours
                
                await self._write_state(new_data)
                _LOGGER.info("Schedule disabled")
                return
            
            # Validate inputs
            hour = max(0, min(23, hour))
            minute = max(0, min(59, minute))
            temp_celsius = max(0, min(100, temp_celsius))
            
            # Check if we need two-step process (changing mode)
            current_mode = self._state_data[0] & 0x08
            if current_mode:
                # Disable first
                temp_data = bytearray(self._state_data)
                temp_data[0] &= ~0x08
                temp_data[6] = 0xc0
                await self._write_state(temp_data)
                await asyncio.sleep(0.3)
            
            # Enable schedule with new parameters
            new_data = bytearray(self._state_data)
            new_data[0] |= 0x08                    # Set schedule enable bit
            new_data[6] = int(temp_celsius * 2)   # Schedule temperature
            new_data[8] = minute                   # Schedule minutes
            new_data[9] = hour                     # Schedule hours
            
            # Set mode bit in counter byte
            if mode == ScheduleMode.ONCE:
                new_data[16] = (new_data[16] | 0x08)
            else:  # DAILY
                new_data[16] = (new_data[16] & ~0x08)
            
            await self._write_state(new_data)
            _LOGGER.info("Schedule set to %s at %02d:%02d, %.1f°C", 
                        mode.name, hour, minute, temp_celsius)
            
        except Exception as err:
            _LOGGER.error("Error setting schedule: %s", err)
            if self._client and self._client.is_connected:
                try:
                    await self._client.disconnect()
                except Exception:
                    pass
            self._client = None
            raise

    async def disconnect(self) -> None:
        """Disconnect from the kettle."""
        if self._client and self._client.is_connected:
            try:
                await self._client.stop_notify(MAIN_CONFIG_UUID)
            except Exception:
                pass
            await self._client.disconnect()
            _LOGGER.debug("Disconnected from kettle")
        self._client = None
