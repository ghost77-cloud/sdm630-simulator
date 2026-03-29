# RS485 Echo-Problem: Analyse und Lösungsweg

## Kontext

Hardwareaufbau: Raspberry Pi mit Waveshare 4-Port USB-RS485-Konverter (CH348L-Chip).

- `ttyACM0` — Growatt SPH10000 Wechselrichter (Modbus-Client, unit=1)
- `ttyACM2` — SDM630-Simulator (Modbus-Server, unit=2) + THOR K11 Wallbox (Master)

## Problem: "Frame check failed" Log-Flut

### Symptom

Nach jedem gesendeten Modbus-Frame erscheinen Tausende von Einträgen:

```text
Frame check failed, possible garbage after frame, testing..
```

Der interne `recv_buffer` wächst mit jeder Iteration und enthält immer dasselbe Muster:

```text
0x2 0x50 0x56 0x4 0x64   ← Fragment der eigenen FC04-Antwort (unit=2)
0x2 0x10 0x0 0x1e 0xc5   ← Fragment der eigenen FC16-Antwort (unit=2)
```

### Ursache: Hardware-TX-Echo

Der Waveshare USB-RS485-Adapter loopt alle gesendeten TX-Bytes auf RX zurück (fehlende
oder zu langsame DE/RE-Pin-Steuerung). Da der Simulator als **Server** dauerhaft lauscht,
landen diese Echo-Bytes im pymodbus-Frame-Buffer und werden als eingehende Frames geparst.
Die CRC-Prüfung schlägt fehl → "Frame check failed".

### Warum ttyACM0 (Client) davon nicht betroffen ist

Der pymodbus-**Client** ruft vor jeder Antwort intern `reset_input_buffer()` auf. Echo-Bytes,
die im falschen Zeitfenster ankommen, werden dadurch verworfen, bevor der Parser sie sieht.
Der **Server** führt diesen Reset nie durch — er liest alles ungefiltert in den Buffer.

## Analyse des pymodbus-Quellcodes

Datei: `pymodbus/pymodbus/transport/transport.py`

### `handle_local_echo=True` — Implementierung

```python
def datagram_received(self, data: bytes, addr: tuple | None) -> None:
    if self.comm_params.handle_local_echo and self.sent_buffer:
        if data.startswith(self.sent_buffer):
            # Echo vollständig am Anfang → entfernen
            data = data[len(self.sent_buffer):]
            self.sent_buffer = b""
        elif self.sent_buffer.startswith(data):
            # Echo nur partiell angekommen → Rest abwarten, return
            self.sent_buffer = self.sent_buffer[len(data):]
            return
        else:
            # Echo kam nicht oder in falscher Reihenfolge → ignorieren
            self.sent_buffer = b""
```

**Einschränkung:** Funktioniert nur wenn der Echo als **vollständiger Block** am Anfang des
empfangenen Datums ankommt. Bei 9600 Baud und USB-Latenz kann der Echo fragmentiert eintreffen
— dann greift der `startswith`-Zweig nicht und der Echo landet trotzdem im Buffer.

### Automatischer Buffer-Reset bei 1024 Bytes

```python
if len(self.recv_buffer) > 1024:
    self.recv_buffer = b''
```

Der Buffer wächst maximal auf 1024 Bytes, wird dann automatisch geleert. Das verhindert
unbegrenzte Akkumulation, führt aber zum periodischen Verwerfen legitimer Frame-Daten.

### `sent_buffer` wird beim Senden befüllt

```python
# in callback_new_connection / write():
if self.comm_params.handle_local_echo:
    self.sent_buffer += data
```

Der `sent_buffer` wird nur befüllt wenn `handle_local_echo=True` gesetzt ist.

## Korrektur: `data_received` leitet zu `datagram_received` weiter

Verifikation im Quellcode (`pymodbus/transport/transport.py`):

```python
def data_received(self, data: bytes) -> None:
    self.datagram_received(data, None)          # ← Serial NUTZT denselben Pfad!

def datagram_received(self, data: bytes, addr: tuple | None) -> None:
    if self.comm_params.handle_local_echo and self.sent_buffer:
        if data.startswith(self.sent_buffer):   # ← startswith-only-Match
            ...
```

`handle_local_echo=True` **läuft also für Serial** — die ursprüngliche Aussage "nur UDP" war
falsch. Das Problem ist dennoch reell: Der `startswith`-Match schlägt bei fragmentiertem Echo
fehl, und `sent_buffer` wird dann auf `b""` zurückgesetzt → Echo landet im Buffer.

## Vergleich der Optionen

| Option | Aufwand | Wirkung | Status |
|--------|---------|---------|--------|
| `handle_local_echo=True` | 0 | Partiell (nur bei Block-Echo) | War bereits aktiv |
| `delay_before_rx=0.015` | minimal | Mittel (CH348L-abhängig) | **Phase 1 — deployed** |
| PTY Echo-Filter Proxy | mittel | Sehr hoch (fragmentiert-robust) | **Phase 3 — implementiert** |
| FTDI-basierter Adapter | €10–15 | Vollständig (hardware-seitig) | Fallback |

## Lösungsplan mit Fallback

### Phase 1 — Quick-Test (sofort, nur Deploy)

`delay_before_rx=0.015` in `RS485Settings`: pyserial/Kernel wartet 15 ms nach TX,
bevor RX geöffnet wird. Bei 9600 Baud entspricht ein 15-Byte-Frame ~17 ms —
das Fenster ist knapp, aber bei USB-Latenz des CH348L oft ausreichend.

**Testen:** HA neu starten, 10 Minuten Log beobachten.
Falls "Frame check failed" deutlich abnimmt → weiter zu Phase 3.
Falls THOR-Fehler durch zu langes RX-Gate entstehen → auf `0.020` erhöhen.

### Phase 3 — PTY Echo-Filter Proxy (parallel entwickelt)

Neues Modul [`echo_filter_proxy.py`](echo_filter_proxy.py), `AsyncEchoFilterProxy`:

**Architektur:**

```text
THOR (bus master)
  │
[ /dev/ttyACM2 ] ←── RS485  +  Hardware-TX-Echo (CH348L)
  │
[ AsyncEchoFilterProxy ]  ← asyncio add_reader auf HA Event Loop
  │  _on_serial_data: read → filter_echo → os.write(master_fd)
  │  _on_pty_data:    os.read(master_fd) → serial.write + sent_buffer tracken
  ↓
[ /dev/pts/X ] (PTY Slave)  ← pymodbus "sieht" dies als normalen Serial-Port
  │
pymodbus / StartAsyncSerialServer
```

**Echo-Filter-Algorithmus** (fragmentierungs-robust, anders als pymodbus `startswith`):

```python
for byte in data:
    if i < len(sent_buffer) and byte == sent_buffer[i]:
        i += 1  # Echo-Byte matched → verwerfen
    else:
        result.append(byte)  # kein Echo → behalten
del sent_buffer[:i]
```

**Aktivierung:** In `sensor.py` das Toggle setzen:

```python
USE_ECHO_FILTER_PROXY: bool = True   # False = Phase 1, True = Phase 3
```

**HA Green / HAOS Kompatibilität:**

- `pty` Modul: Python stdlib, auf Linux immer verfügbar ✓
- PTY-Slave als pyserial-Port öffenbar (`/dev/pts/X`) ✓
- Kein `socat`, kein externer Prozess nötig ✓
- asyncio `add_reader` läuft im HA Event Loop — keine Threads ✓
- `RS485Settings` entfällt für PTY (CH348L steuert DE/RE automatisch) ✓

### Fallback — FTDI-basierter RS485-Adapter (€10–15)

Falls Phase 1 und Phase 3 nicht ausreichen: FTDI FT232R oder FT232H basierter
USB-RS485-Adapter. Dieser steuert DE/RE via RTS **synchron auf Chip-Ebene** —
kein Echo entsteht. Empfehlungen:

- Waveshare USB-to-RS485 (FT232-basiert, **nicht** CH348L-Variante prüfen)
- FTDI USB-RS485-WE-1800-BT

## Aktuelle Konfiguration (Phase 1, deployed)

In `sensor.py` (`USE_ECHO_FILTER_PROXY = False`):

```python
await StartAsyncSerialServer(
    ...
    handle_local_echo=True,
    ignore_missing_slaves=True,
    rs485_mode=RS485Settings(
        rts_level_for_tx=True,
        rts_level_for_rx=False,
        delay_before_tx=0.0,
        delay_before_rx=0.015,   # ← Phase-1-Änderung
    ),
)
```

## Logging-Empfehlung (weiterhin sinnvoll)

```yaml
logger:
  default: warning
  logs:
    custom_components.sdm630_simulator: debug
    pymodbus: warning
```

## Offene Fragen / Testergebnisse

- [ ] Phase 1 testen: Nimmt "Frame check failed"-Frequenz mit `delay_before_rx=0.015` ab?
- [ ] THOR-Fehler durch 1024-Byte-Buffer-Overflow? (Reset während FC04-Anfrage → Timeout)
- [ ] Phase 3 testen: `USE_ECHO_FILTER_PROXY = True` → vollständige Echo-Eliminierung?

## Bus-Topologie

```text
THOR Wallbox (Master)
    │
    ├─── RS485 ──── ttyACM2 ──── SDM630-Simulator (unit=2)
    │                               ↑ TX-Echo zurück auf RX (Hardware-Problem)
    │
Growatt SPH10000 (unit=1)
    │
    ├─── RS485 ──── ttyACM0 ──── Growatt-Integration (Client)
```

Die Growatt-Integration und der SDM630-Simulator liegen auf **getrennten RS485-Segmenten**
(separate Kabelpaare am 4-Port-Konverter). Cross-Bus-Störungen sind daher ausgeschlossen.
