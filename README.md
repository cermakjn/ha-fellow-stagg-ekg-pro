# Fellow Stagg EKG Pro Home Assistant Integration

A Home Assistant integration for the Fellow Stagg EKG Pro electric kettle. Control and monitor your kettle directly from Home Assistant via Bluetooth.

## Credits

- Original function from [github.com/levi/stagg-ekg-plus-ha](https://github.com/levi/stagg-ekg-plus-ha)
- Kettle BLE protocol from [breiflabb/ekg-pro-ble-lib](https://codeberg.org/breiflabb/ekg-pro-ble-lib)

### Modifications from Original

- Set schedule via service - all schedule parameters must be set at once
- Automatic clock sync on every BLE request
- Improved BLE connection timeout handling (20 seconds)
- Uses `bleak-retry-connector` for reliable Bluetooth connections

## Features

- **Temperature Control**: Set target temperature (40-100°C / 104-212°F)
- **Hold Mode**: Keep water at target temperature for up to 60 minutes
- **Pre-boil Control**: Toggle pre-boil setting
- **Schedule Timer**: Set daily or one-time heating schedules
- **Chime Volume**: Adjust or mute the kettle chime (0-10)
- **Clock Settings**: Configure clock display mode (off/digital/analog)
- **Altitude Compensation**: Set altitude for accurate boiling point
- **Temperature Units**: Switch between Celsius and Fahrenheit
- **Bluetooth Discovery**: Automatic kettle discovery

## Known Limitations

- Cannot turn on the kettle remotely - only schedule heating or adjust temperature when already on
- Clock sync doesn't support seconds - time may drift slightly between syncs
- No real-time current temperature during heating (EKG Pro protocol limitation)

## Installation

### Option 1: HACS (Recommended)

#### Via My Home Assistant Link

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=cermakjn&repository=ha-fellow-stagg-ekg-pro)

#### Via HACS UI

1. Make sure you have [HACS](https://hacs.xyz) installed
2. Add this repository as a custom repository in HACS:
   - Click the menu icon in the top right of HACS
   - Select "Custom repositories"
   - Add `https://github.com/cermakjn/ha-fellow-stagg-ekg-pro` with category "Integration"
3. Click "Download" on the Fellow Stagg EKG Pro integration
4. Restart Home Assistant
5. Go to **Settings → Devices & Services → Add Integration**
6. Search for "Fellow Stagg EKG Pro"
7. Follow the configuration steps

### Option 2: Manual Installation

1. Copy the `custom_components/fellow_stagg_ekg_pro` directory to your Home Assistant's `custom_components` directory
2. Restart Home Assistant
3. Go to **Settings → Devices & Services → Add Integration**
4. Search for "Fellow Stagg EKG Pro"
5. Follow the configuration steps

## Configuration

The integration can be set up in two ways:

1. **Automatic Discovery**: The kettle will be automatically discovered if Bluetooth is enabled
2. **Manual Configuration**: Add the kettle manually by providing its MAC address

## Entities

Once configured, the kettle provides the following entities:

### Water Heater

| Entity | Description |
|--------|-------------|
| Water Heater | Main control - set target temperature and view current state |

### Sensors (Read-only)

| Sensor | Description |
|--------|-------------|
| Target Temperature | Current target temperature setting |
| Temperature Units | Current unit (°C or °F) |
| Hold Mode | Whether hold mode is active |
| Hold Time | Hold duration in minutes |
| Pre-Boil | Pre-boil status |
| Chime | Chime enabled/disabled |
| Chime Volume | Current volume level (0-10) |
| Clock Mode | Display mode (off/digital/analog) |
| Clock Time | Current kettle clock time |
| Altitude | Altitude compensation in meters |
| Schedule | Schedule enabled/disabled |
| Schedule Mode | Schedule type (off/once/daily) |
| Schedule Time | Scheduled activation time |
| Schedule Temperature | Temperature for scheduled heating |
| Language | Kettle menu language |
| Raw Data | Debug sensor (disabled by default) - see [BLE Protocol Notes](#ble-protocol-notes) |

### Number Controls

| Control | Range | Description |
|---------|-------|-------------|
| Target Temperature | 40-100°C / 104-212°F | Set target heating temperature |
| Hold Time | 0-60 min | Duration to maintain temperature |
| Chime Volume | 0-10 | Alert volume (0 = off) |
| Altitude | 0-9999 m | Altitude compensation |

### Select Controls

| Control | Options | Description |
|---------|---------|-------------|
| Clock Mode | Off, Digital, Analog | Clock display style |
| Temperature Units | Celsius, Fahrenheit | Temperature unit preference |
| Schedule Mode | Off, Once, Daily | Schedule type |

### Switch

| Switch | Description |
|--------|-------------|
| Pre-Boil | Toggle pre-boil on/off |

### Buttons

| Button | Description |
|--------|-------------|
| Reload Data | Force refresh kettle state |
| Sync Time | Synchronize kettle clock with Home Assistant |

## Services

### `fellow_stagg_ekg_pro.set_schedule`

Set the kettle's schedule timer settings all at once.

**Parameters:**

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `mode` | Yes | - | Schedule mode: `off`, `once`, or `daily` |
| `hour` | No | 7 | Hour of the day (0-23) |
| `minute` | No | 0 | Minute of the hour (0-59) |
| `temperature` | No | 85 | Target temperature in °C (40-100) |

**Examples:**

```yaml
# Turn off scheduling
service: fellow_stagg_ekg_pro.set_schedule
data:
  mode: "off"
```

```yaml
# Daily schedule at 7:30 AM, 85°C
service: fellow_stagg_ekg_pro.set_schedule
data:
  mode: daily
  hour: 7
  minute: 30
  temperature: 85
```

```yaml
# One-time schedule at 6:00 AM, 92°C
service: fellow_stagg_ekg_pro.set_schedule
data:
  mode: once
  hour: 6
  minute: 0
  temperature: 92
```

### `fellow_stagg_ekg_pro.scan_devices`

Scan for Fellow Stagg EKG Pro kettles via Bluetooth. Useful for discovering kettles before adding them.

**How to use:**

1. Go to **Developer Tools → Services**
2. Select `fellow_stagg_ekg_pro.scan_devices`
3. Enable the **"Return response"** toggle
4. Click **"Call Service"**

**Response fields:**

| Field | Description |
|-------|-------------|
| `fellow_devices` | List of Fellow kettles found (name, address, rssi) |
| `fellow_count` | Number of Fellow devices found |
| `all_ble_devices` | All visible BLE devices (for debugging) |
| `total_ble_count` | Total BLE devices in range |

**Example response:**

```json
{
  "fellow_devices": [
    {
      "name": "Fellow Stagg",
      "address": "AA:BB:CC:DD:EE:FF",
      "rssi": -65
    }
  ],
  "fellow_count": 1,
  "all_ble_devices": [...],
  "total_ble_count": 15
}
```

## Example Automations

### Morning Coffee Schedule

```yaml
automation:
  - alias: "Morning Coffee - Set Schedule"
    trigger:
      - platform: time
        at: "22:00:00"
    action:
      - service: fellow_stagg_ekg_pro.set_schedule
        data:
          mode: daily
          hour: 6
          minute: 30
          temperature: 92
```

### Sync Kettle Time Daily

```yaml
automation:
  - alias: "Sync Kettle Clock"
    trigger:
      - platform: time
        at: "03:00:00"
    action:
      - service: button.press
        target:
          entity_id: button.fellow_stagg_ekg_pro_sync_time
```

## Requirements

- Home Assistant 2024.1.0 or newer
- Bluetooth adapter compatible with Home Assistant
- Fellow Stagg EKG Pro kettle

## BLE Protocol Notes

The EKG Pro uses a different BLE protocol than the EKG+ model. It communicates via a 17-byte configuration characteristic that contains all kettle settings including:

- Target temperature (stored as Celsius × 2)
- Temperature units (Celsius/Fahrenheit)
- Hold time
- Pre-boil setting
- Clock time and display mode
- Chime volume
- Altitude compensation
- Schedule settings

### Protocol Structure (17 bytes)

| Byte | Description |
|------|-------------|
| 0 | Status flags - Bit 3 (0x08): Schedule enabled |
| 1 | Control flags - Bit 1 (0x02): Units (0=°F, 1=°C), Bit 3 (0x08): Pre-boil |
| 2-3 | Altitude in meters (byte 3 has 0x80 offset) |
| 4 | Target temperature (value × 2 = °C) |
| 5 | Unknown/status |
| 6 | Schedule target temperature (value × 2 = °C, 0xC0=disabled) |
| 7 | Unknown/status |
| 8 | Schedule minutes (0-59) |
| 9 | Schedule hours (0-23) |
| 10 | Clock minutes (0-59) |
| 11 | Clock hours (0-23) |
| 12 | Clock mode (0=OFF, 1=DIGITAL, 2=ANALOG) |
| 13 | Hold time in minutes (0-63, 0=OFF) |
| 14 | Chime volume (0=OFF, 1-10) |
| 15 | Language |
| 16 | Counter (increments with each write) |

**Note**: Unlike the EKG+, the EKG Pro's config characteristic doesn't provide real-time current temperature readings during heating. The integration reports the target temperature as an approximation.

## Troubleshooting

If you experience connection issues:
1. Ensure the kettle is within Bluetooth range of your Home Assistant device
2. Check that Bluetooth is enabled and working in Home Assistant
3. Verify the MAC address if manually configured
4. Check the Home Assistant logs for detailed error messages
5. Make sure the kettle isn't connected to another device (e.g., Fellow app)

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License - see LICENSE file for details
