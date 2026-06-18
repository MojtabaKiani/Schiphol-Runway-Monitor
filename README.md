# Schiphol Runway Monitor

[![HACS Custom][hacs-badge]][hacs-url]
[![GitHub Release][release-badge]][release-url]
[![License: MIT][license-badge]][license-url]

A Home Assistant custom integration that monitors **live runway usage at Amsterdam Airport Schiphol (EHAM)**. It creates one sensor per runway, a combined peak-time sensor, and two boolean sensors for inbound/outbound peaks — all updated every 5 minutes from LVNL (Luchtverkeersleiding Nederland) data.

> 💡 Want a visual runway map on your dashboard? Pair this with the companion **[Schiphol Runway Card](https://github.com/your-repo/schiphol-runway-card)** (installed separately via HACS Frontend).

---

## Features

- **6 runway sensors** — one per Schiphol runway, each with four states: `not_in_use`, `inbound`, `outbound`, `inbound_and_outbound`
- **Directional detail** — each sensor exposes which heading is landing and which is departing
- **Peak time sensors** — a combined state sensor plus two `binary_sensor` entities for inbound and outbound peaks individually
- **No API key required** — uses publicly available LVNL data via dutchplanespotters.nl
- **UI configuration** — add it from Settings → Devices & Services, configure the poll interval
- **Fully local automations** — clean, well-named entities designed for simple automations

---

## Data Source

Data is sourced from **[dutchplanespotters.nl](https://www.dutchplanespotters.nl/runways/ams/)**, which aggregates real-time runway usage from LVNL (the Dutch air traffic control authority). LVNL updates runway assignments roughly every 5 minutes.

The integration queries the JSON endpoint `https://www.dutchplanespotters.nl/api/runways/ams`, finds the time slot matching the current moment, and reports which runways are landing (`landingRunways`) and departing (`departingRunways`).

> ⚠️ **Note:** The data reflects *actual current* runway usage. There is no publicly available source for *future* runway assignments — runway selection depends on real-time wind and traffic conditions.

---

## Entities

> Entity IDs below assume the device name `Schiphol Airport (EHAM)`, so Home Assistant prefixes them with `schiphol_airport_eham_`. Your exact IDs may differ slightly; check **Developer Tools → States**.

### Runway Sensors

One sensor per runway:

| Entity ID | Runway | Name |
|-----------|--------|------|
| `sensor.schiphol_airport_eham_06_24_kaagbaan` | 06/24 | Kaagbaan |
| `sensor.schiphol_airport_eham_09_27_oostbaan` | 09/27 | Oostbaan |
| `sensor.schiphol_airport_eham_18c_36c_zwanenburgbaan` | 18C/36C | Zwanenburgbaan |
| `sensor.schiphol_airport_eham_18l_36r_aalsmeerbaan` | 18L/36R | Aalsmeerbaan |
| `sensor.schiphol_airport_eham_18r_36l_polderbaan` | 18R/36L | Polderbaan |
| `sensor.schiphol_airport_eham_04_22_buitenveldertbaan` | 04/22 | Buitenveldertbaan |

#### States

| State | Meaning |
|-------|---------|
| `not_in_use` | Runway is not active |
| `inbound` | Runway is being used for landings |
| `outbound` | Runway is being used for takeoffs |
| `inbound_and_outbound` | Runway is used for both simultaneously |

#### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `runway` | string | Runway designator, e.g. `"18L/36R"` |
| `name` | string | Dutch runway name, e.g. `"Aalsmeerbaan"` |
| `landing_heading` | string \| null | Active landing heading (e.g. `"18L"`), or `null` if not landing |
| `takeoff_heading` | string \| null | Active takeoff heading (e.g. `"36R"`), or `null` if not departing |
| `all_active_landing` | list | All headings currently used for landings at Schiphol |
| `all_active_takeoff` | list | All headings currently used for takeoffs at Schiphol |
| `data_source` | string | Attribution string |

---

### Peak Time Sensor

`sensor.schiphol_airport_eham_peak_time` — reflects the current peak period. Schiphol runs more runways during peaks (extra landing runways during inbound peaks, extra departure runways during outbound peaks).

#### States

| State | Meaning |
|-------|---------|
| `no_peak` | No peak period active |
| `inbound_peak` | Arrival peak active |
| `outbound_peak` | Departure peak active |
| `inbound_and_outbound_peak` | Both peaks overlap |

#### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `inbound_peak` | bool | `true` if an inbound peak is active now |
| `outbound_peak` | bool | `true` if an outbound peak is active now |
| `next_inbound_peak` | string \| null | Next inbound window, e.g. `"15:20 - 16:50"` |
| `next_outbound_peak` | string \| null | Next outbound window, e.g. `"14:00 - 15:40"` |
| `all_peaks` | list | Full list of the day's peak windows, e.g. `[{"inbound": "07:10 - 09:50", "outbound": "06:50 - 08:00"}, ...]` |
| `data_source` | string | Attribution string |

> ℹ️ Peak windows are derived from LVNL observations over the past ~14 days and represent *typical* patterns. Actual peaks may shift slightly.

---

### Peak Binary Sensors

Simple booleans, ideal for automations:

| Entity ID | `on` when… |
|-----------|-----------|
| `binary_sensor.schiphol_airport_eham_inbound_peak` | An inbound (landing) peak is active |
| `binary_sensor.schiphol_airport_eham_outbound_peak` | An outbound (departure) peak is active |

**Inbound binary sensor attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `next_inbound_peak` | string \| null | Next upcoming inbound window |
| `all_inbound_peaks` | list | All inbound windows for today |

**Outbound binary sensor attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `next_outbound_peak` | string \| null | Next upcoming outbound window |
| `all_outbound_peaks` | list | All outbound windows for today |

---

## Installation

### Via HACS (Recommended)

1. Open **HACS → Integrations**
2. Click the ⋮ menu → **Custom repositories**
3. Add this repository URL, category **Integration**
4. Search for **Schiphol Runway Monitor** → **Download**
5. **Restart Home Assistant**
6. Go to **Settings → Devices & Services → Add Integration**
7. Search for **Schiphol** and follow the setup wizard

### Manual Installation

1. Download the [latest release][release-url]
2. Copy the `custom_components/schiphol_runways/` folder into your config:
   ```
   /config/custom_components/schiphol_runways/
   ```
3. **Restart Home Assistant**
4. Go to **Settings → Devices & Services → Add Integration** → search **Schiphol**

---

## Configuration

Configured entirely through the UI. During setup (and later via **Configure**):

| Option | Default | Description |
|--------|---------|-------------|
| Poll interval | `5` minutes | How often to fetch from the data source (min 1, max 60). LVNL updates every ~5 minutes. |

---

## Automation Examples

### Notify when Aalsmeerbaan (18L/36R) starts being used for landings

```yaml
automation:
  - alias: "Schiphol | Aalsmeerbaan inbound started"
    trigger:
      - platform: state
        entity_id: sensor.schiphol_airport_eham_18l_36r_aalsmeerbaan
        to:
          - "inbound"
          - "inbound_and_outbound"
    action:
      - service: notify.mobile_app_your_phone
        data:
          title: "✈️ Aalsmeerbaan active for landings"
          message: >
            Runway 18L/36R is now landing
            (heading {{ state_attr('sensor.schiphol_airport_eham_18l_36r_aalsmeerbaan', 'landing_heading') }}).
```

### Notify when a runway stops being used

```yaml
automation:
  - alias: "Schiphol | Aalsmeerbaan no longer active"
    trigger:
      - platform: state
        entity_id: sensor.schiphol_airport_eham_18l_36r_aalsmeerbaan
        to: "not_in_use"
    action:
      - service: notify.mobile_app_your_phone
        data:
          title: "✅ Aalsmeerbaan no longer active"
          message: "Runway 18L/36R is now out of use."
```

### Notify when an inbound peak starts

```yaml
automation:
  - alias: "Schiphol | Inbound peak started"
    trigger:
      - platform: state
        entity_id: binary_sensor.schiphol_airport_eham_inbound_peak
        to: "on"
    action:
      - service: notify.mobile_app_your_phone
        data:
          title: "🛬 Schiphol inbound peak"
          message: "Arrival peak active — expect extra landing runways in use."
```

### Watch several runways at once

```yaml
automation:
  - alias: "Schiphol | Watched runway became active"
    trigger:
      - platform: state
        entity_id:
          - sensor.schiphol_airport_eham_18l_36r_aalsmeerbaan
          - sensor.schiphol_airport_eham_04_22_buitenveldertbaan
          - sensor.schiphol_airport_eham_09_27_oostbaan
        from: "not_in_use"
    action:
      - service: notify.mobile_app_your_phone
        data:
          title: "✈️ Runway active: {{ state_attr(trigger.entity_id, 'runway') }}"
          message: >
            {{ state_attr(trigger.entity_id, 'name') }} is now
            {% if trigger.to_state.state == 'inbound' %}landing
            {% elif trigger.to_state.state == 'outbound' %}departing
            {% else %}landing and departing{% endif %}.
```

---

## About Schiphol Runways

Schiphol has six runways. Which are active depends on wind, traffic volume, noise rules, and maintenance.

| Runway | Name | Notes |
|--------|------|-------|
| 18R/36L | Polderbaan | Preferred primary; routes over least-populated areas |
| 06/24 | Kaagbaan | Preferred secondary; NE-SW diagonal |
| 18C/36C | Zwanenburgbaan | Central N-S runway |
| 18L/36R | Aalsmeerbaan | SW of the airport |
| 04/22 | Buitenveldertbaan | Short runway; SE, used mainly during peaks |
| 09/27 | Oostbaan | Shortest; used selectively, mainly GA |

Quiet periods: 1 landing + 1 departure runway. Inbound peaks: 2 landing + 1 departure. Outbound peaks: 1 landing + 2 departure. Overlapping peaks: up to 2 + 2.

---

## Companion Dashboard Card

For a live visual runway map with airplane sprites and peak indicators, install the separate **[Schiphol Runway Card](https://github.com/your-repo/schiphol-runway-card)** via **HACS → Frontend**. (HACS requires integrations and frontend cards to live in separate repositories, so they're distributed separately.)

---

## Troubleshooting

**All sensors show `not_in_use` or `unavailable`**
- Check **Settings → System → Logs**, filter `schiphol_runways`
- Verify Home Assistant can reach `dutchplanespotters.nl` (firewall/DNS)
- Open https://www.dutchplanespotters.nl/api/runways/ams in a browser to confirm the source is up

**Binary sensors not triggering automations**
- Use `to: "on"` / `to: "off"` (not `"true"`/`"false"`)
- Confirm the entities exist in **Developer Tools → States**

**Icon not showing on the integration page**
- Requires Home Assistant 2026.3+ for inline brand icons
- The icon ships at `custom_components/schiphol_runways/brand/icon.png`

---

## Contributing

Issues and pull requests welcome. When reporting a bug, please include your Home Assistant version, the integration version, and relevant log lines (filter `schiphol_runways`).

---

## License

MIT — see [LICENSE](LICENSE).

Data sourced from [dutchplanespotters.nl](https://www.dutchplanespotters.nl/), which aggregates [LVNL](https://www.lvnl.nl/) data. This project is not affiliated with LVNL or Amsterdam Airport Schiphol.

[hacs-badge]: https://img.shields.io/badge/HACS-Custom-41BDF5.svg
[hacs-url]: https://hacs.xyz
[release-badge]: https://img.shields.io/github/v/release/your-repo/schiphol-runways-ha
[release-url]: https://github.com/your-repo/schiphol-runways-ha/releases
[license-badge]: https://img.shields.io/badge/License-MIT-yellow.svg
[license-url]: https://github.com/your-repo/schiphol-runways-ha/blob/main/LICENSE
