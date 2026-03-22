# SDM630 Simulator

Home-Assistant Custom Component, die einen Eastron SDM630 Smart Meter
per Modbus RTU simuliert — optimiert für PV-Überschussladen mit der
Growatt THOR 11AS-P-V1 Wallbox.

## Hintergrund

Die Wallbox startet das Laden erst ab **4 kW Netzeinspeisung**. Bei
wechselhaftem Wetter schwankt die PV-Leistung jedoch stark, sodass die
Schwelle selten stabil erreicht wird. Der Simulator löst das Problem,
indem er den 10-kWh-Batteriespeicher am Growatt SPH10000TL3-BH-UP
Hybrid-Wechselrichter als Puffer einrechnet: Solange genug
Speicherladung vorhanden ist, meldet er mindestens 4 kW — auch wenn
die reale Einspeisung kurzzeitig darunter fällt.

Die Sensordaten des Wechselrichters liefert
[Growatt Modbus](https://github.com/WouterTuinstra/Homeassistant-Growatt-Local-Modbus)
(lokale Kopie unter `growat-modbus/`).

## Features

- Modbus-RTU-Server über USB-Serial (`/dev/ttyACM2`,
  9600 Baud, 8E1) — die Wallbox verbindet sich per RS485
- Modbus-TCP-Server auf Port 5020 (nur Standalone-Test)
- SDM630-Protokoll mit IEEE 754 Float-Registern
- Surplus-Engine mit Batteriepuffer, Hysterese und Fail-Safe
- SOC-Floor-Strategie nach Uhrzeit und Jahreszeit
- Optionale Wettervorhersage und Solar-Forecast-Integration
- Staleness- und Range-Validierung aller Sensoreingänge
- Dashboard-Sensoren für Überschuss, letzten Poll und Warnungen

## Installation

1. Diesen Ordner nach `custom_components/sdm630_simulator/` kopieren.
2. Abhängigkeit installieren: `pip install pymodbus>=3.11.1`
3. Konfiguration in `configuration.yaml` eintragen (siehe unten).
4. Home Assistant neu starten.

## Konfiguration

### Minimale Konfiguration

```yaml
sdm630_simulator:
  entities:
    soc: sensor.growatt_battery_soc
    power_to_grid: sensor.growatt_export_power
    pv_production: sensor.growatt_pv_power
    power_to_user: sensor.growatt_home_consumption
```

### Vollständige Konfiguration mit allen Optionen

```yaml
sdm630_simulator:
  # -- Pflicht-Entitäten --
  entities:
    soc: sensor.growatt_battery_soc             # Batterieladung (%)
    power_to_grid: sensor.growatt_export_power   # Netzeinspeisung (W)
    pv_production: sensor.growatt_pv_power       # PV-Erzeugung (W)
    power_to_user: sensor.growatt_home_consumption  # Hausverbrauch (W)
    # -- Optionale Entitäten (für Forecast) --
    weather: weather.home                        # Wetter-Service
    forecast_solar: sensor.forecast_solar_kwh    # Solar-Forecast

  # -- Schwellwerte --
  wallbox_threshold_kw: 4.2      # Min. Überschuss zum Laden (kW)
  hold_time_minutes: 10          # Hysterese-Haltezeit (Minuten)
  evaluation_interval: 15        # Auswertungsintervall (Sekunden)

  # -- Batterie --
  battery_capacity_kwh: 10.0     # Nutzbare Batteriekapazität (kWh)
  max_discharge_kw: 10.0         # Max. Entladerate (kW)
  soc_hard_floor: 50             # Absoluter SOC-Mindeststand (%)

  # -- Wechselrichter --
  max_inverter_output_kw: 10.0   # Max. Wechselrichter-Output (kW)

  # -- Staleness / Sicherheit --
  stale_threshold_seconds: 60    # Sensor-Staleness-Timeout (s)

  # -- Forecast --
  solar_remaining_threshold_kwh: 2.0  # Kritischer Solar-Rest (kWh)

  # -- SOC-Floor nach Uhrzeit --
  time_strategy:
    - before: "sunrise+2h"
      soc_floor: 100            # Morgens voll halten
    - before: "sunset-3h"
      soc_floor: 50             # Tagsüber Puffer nutzen
    - default: true
      soc_floor: 80             # Abends auffüllen

  # -- SOC-Floor nach Monat (Fallback) --
  seasonal_targets:
    1: 100    # Januar
    2: 90     # Februar
    3: 80     # März
    4: 70     # April
    5: 70     # Mai
    6: 70     # Juni
    7: 70     # Juli
    8: 70     # August
    9: 80     # September
    10: 90    # Oktober
    11: 100   # November
    12: 100   # Dezember

  # -- Wertebereiche für Sensor-Validierung --
  sensor_ranges:
    soc: [0, 100]
    power_w: [-30000, 30000]
```

## Sensoren und Entitäten

Die Komponente registriert folgende Entitäten automatisch:

| Entität | Typ | Einheit | Beschreibung |
| --- | --- | --- | --- |
| `sensor.sdm630_simulator_power` | Sensor | W | Überschuss (Modbus) |
| `sensor.sdm_raw_surplus` | Sensor | W | Roh (vor Hysterese) |
| `sensor.sdm_reported_surplus` | Sensor | W | Gefiltert (Hysterese) |
| `sensor.sdm_wallbox_last_poll` | Sensor | datetime | Letzter Wallbox-Poll |
| `binary_sensor.sdm_wallbox_poll_warning` | Binary | — | Kein Poll >5 Min. |

## Surplus-Engine

### Funktionsweise

Die Surplus-Engine wird alle 15 Sekunden (konfigurierbar) ausgewertet:

1. **Sicherheitsprüfungen** — Staleness, Verfügbarkeit, Wertebereich
2. **SOC-Floor bestimmen** — nach Uhrzeit (`time_strategy`) oder Monat
3. **Forecast-Anpassung** — bei schlechter Vorhersage SOC-Floor anheben
4. **Überschuss berechnen** — PV-Erzeugung minus Hausverbrauch
5. **Batteriepuffer** — verfügbare Energie über dem SOC-Floor einrechnen
6. **Hysterese** — Haltezeit, um bei kurzen Einbrüchen nicht abzuschalten
7. **Modbus-Register aktualisieren** — Wallbox sieht neuen Wert

### Ladezustände

| Zustand | Bedeutung |
| --- | --- |
| `ACTIVE` | Überschuss reicht — Wallbox kann laden |
| `INACTIVE` | Überschuss zu gering — kein Laden |
| `FAILSAFE` | SOC < 50 %, Sensor-Fehler oder Staleness |

### Hysterese-Filter

Der Filter verhindert schnelles Ein/Aus bei schwankender PV-Leistung:

- **Aktivierung:** Überschuss erreicht `wallbox_threshold_kw`
- **Haltezeit:** bleibt für `hold_time_minutes` aktiv, auch wenn der
  Überschuss kurz unter die Schwelle fällt
- **Deaktivierung:** erst nach Ablauf der Haltezeit, wenn weiterhin zu
  wenig Überschuss vorhanden ist

### Fail-Safe

In folgenden Fällen meldet die Engine sofort 0 kW:

- SOC unter `soc_hard_floor` (Standard: 50 %)
- Ein Pflicht-Sensor ist `unavailable` oder `unknown`
- Sensordaten älter als `stale_threshold_seconds`
- Sensorwerte außerhalb der konfigurierten Bereiche

## Wallbox-Dashboard

Eine fertige Lovelace-Card-Konfiguration liegt unter
`docs/lovelace-wallbox-card.yaml`. Die Karte zeigt:

- Rohen und gefilterten Überschuss
- Zeitstempel des letzten Wallbox-Polls
- Visuelle Warnung, wenn die Wallbox seit 5 Minuten nicht gepollt hat

### Einrichtung

1. Home Assistant: **Übersicht** → **Dashboard bearbeiten** (Stift-Icon)
2. **Karte hinzufügen** → **Manuell** (oder Raw-Konfigurationseditor)
3. Inhalt von `docs/lovelace-wallbox-card.yaml` einfügen
4. **Speichern**

Keine HACS-Installation oder Drittanbieter-Karten nötig — die Karte
verwendet nur die eingebauten Kartentypen `vertical-stack`,
`conditional` und `entities`.

### Warn-Schwelle ändern

Die Warnung wird nach 300 Sekunden (5 Minuten) ohne Modbus-Poll
ausgelöst. Um den Wert zu ändern:

1. `WALLBOX_POLL_WARNING_THRESHOLD` in `sensor.py` anpassen
2. Home Assistant neu starten

## Modbus-Verbindung

### Produktiv: Modbus RTU (Serial)

Im Home-Assistant-Betrieb startet die Komponente einen
asynchronen Modbus-RTU-Server auf einem USB-Serial-Adapter.
Die Wallbox verbindet sich physisch per RS485-Bus mit
diesem Adapter.

| Parameter | Wert |
| --- | --- |
| Protokoll | Modbus RTU |
| Serial-Port | `/dev/ttyACM2` |
| Baudrate | 9600 |
| Datenbits | 8 |
| Parität | Even (E) |
| Stoppbits | 1 |

Die Wallbox pollt per Modbus FC04 (Read Input Registers)
das Register `TOTAL_POWER` (Adresse 53–54) und liest den
berechneten Überschuss in Watt.

### Standalone-Test: Modbus TCP

Zum Testen ohne Home Assistant und ohne serielle Hardware:

```bash
python modbus_server.py
```

Startet einen TCP-Server auf Port 5020 (RTU-Framing über
TCP), der SDM630-Register mit Standardwerten liefert.
Damit lässt sich die Register-Kommunikation z. B. mit
`pymodbus.client` oder ModbusPoll prüfen.

## Referenzen

- [SDM630 Modbus-Protokoll](eastron/SDM630_MODBUS_Protocol.pdf)
- [Growatt Modbus Integration](https://github.com/WouterTuinstra/Homeassistant-Growatt-Local-Modbus)
- [HA Conditional Card](https://www.home-assistant.io/dashboards/conditional/)
