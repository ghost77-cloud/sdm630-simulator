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
| `handle_local_echo=True` | 0 | Partiell (nur bei Block-Echo) | ❌ unzureichend |
| `delay_before_rx=0.015` | minimal | Mittel (CH348L-abhängig) | ❌ unzureichend |
| PTY Echo-Filter Proxy (sent_buffer) | mittel | – | ❌ asyncio-Race, nicht deployed |
| PTY Echo-Filter Proxy (reader-pause) | hoch | – | ❌ gescheitert, Ursache unklar |
| Log-Filter `_SimulatorOnlyFilter` | gering | Analyse-Hilfe | ❌ Pattern unvollständig |
| ModbusProtocol Monkey-Patch | gering | Sehr hoch (Direktlösung) | ❌ gescheitert |
| FTDI-basierter Adapter | €10–15 | Vollständig (hardware-seitig) | **→ Hardware-Lösung** |

## Lösungsplan mit Fallback

### Phase 1 — Quick-Test (deployed, gescheitert)

`delay_before_rx=0.015` in `RS485Settings` brachte keine ausreichende Verbesserung.
Das Echo vom CH348L trifft noch innerhalb des RX-Fensters ein.

### Phase 3 — PTY Echo-Filter Proxy (gescheitert)

Zwei Varianten wurden entwickelt und getestet, beide scheiterten.

**Variante 1 — `sent_buffer` Pattern-Matching:**

```python
for byte in data:
    if i < len(sent_buffer) and byte == sent_buffer[i]:
        i += 1  # Echo-Byte matched → verwerfen
    else:
        result.append(byte)
```

Fehler: asyncio-Race-Condition — Echo kann eintreffen, bevor `_on_pty_data`
den `sent_buffer` befüllt hat. Ergebnis: Echo wurde nicht gefiltert.

**Variante 2 — Reader-Pause (analog zum pymodbus-Client):**

```python
def _on_pty_data(self) -> None:
    data = os.read(self._master_fd, 4096)
    self._ser.write(data)
    self._loop.remove_reader(self._ser.fileno())      # RX stumm schalten
    self._loop.call_later(0.025, self._reenable_serial_reader)

def _reenable_serial_reader(self) -> None:
    self._ser.reset_input_buffer()                    # Echo verwerfen
    self._loop.add_reader(self._ser.fileno(), self._on_serial_data)
```

Ergebnis aus HA-Log: Echo-Bytes `0x2 0x10 0x0 0x1e 0xc5` und
`0x2 0x50 0x56 0x4 0x64` erscheinen weiterhin in pymodbus `extra data`.
Mögliche Ursachen noch nicht diagnostiziert.

**Logging-Filter `_SimulatorOnlyFilter` (unzureichend):**

Pattern-Matching auf `"send: 0x1 "` / `"recv: 0x1 "` deckt nicht alle
pymodbus-Meldungen ab. Weitere Nachrichten des Growatt-Verkehrs ohne dieses
Muster passieren den Filter — für die Analyse nicht brauchbar genug.

### Offene Testergebnisse

- [x] Phase 1 (`delay_before_rx=0.015`) → kein ausreichender Effekt
- [x] Phase 3 Proxy (sent_buffer) → asyncio-Race, nicht funktional
- [x] Phase 3 Proxy (reader-pause) → Echo trotzdem in pymodbus sichtbar
- [x] Logging-Filter → Pattern unvollständig, für Analyse ungeeignet
- [x] pymodbus Monkey-Patch (`_apply_modbus_echo_patch`) → gescheitert

**Monkey-Patch-Ansatz (gescheitert):**

Deadline-basiertes Verwerfen in `datagram_received` via `ModbusProtocol`-Monkey-Patch
mit `is_server`-Guard (Growatt-Client unberührt). Code in `sensor.py` implementiert
und deployed. Echo-Spam bleibt trotzdem sichtbar — Ursache unbekannt.

```python
def _patched_send(self, data, addr=None):
    if self.is_server:
        self._echo_deadline = time.monotonic() + 0.030
    _orig_send(self, data, addr)

def _patched_datagram_received(self, data, addr):
    if self.is_server and time.monotonic() < getattr(self, "_echo_deadline", 0.0):
        return  # verwerfen
    _orig_datagram_received(self, data, addr)
```

**Hypothese warum es nicht funktioniert:** pymodbus auf HAOS nutzt möglicherweise
nicht die Klasse aus dem importierten Modul-Objekt direkt, sondern instanziiert
über einen internen Factory-Mechanismus, der den Patch umgeht. Oder `datagram_received`
wird auf einem anderen Codepfad (z. B. über asyncio Protocol-Dispatch) aufgerufen, der
vom Patch nicht erfasst wird.

### Fazit: Software-Lösung erschöpft

Alle Software-seitigen Ansätze wurden versucht und sind gescheitert.
Die Ursache liegt im Hardware-Design des CH348L-Chips, der TX-Bytes auf RX zurückspiegelt
ohne steuerbare DE/RE-Pin-Kontrolle.

**Einzig verbleibende zuverlässige Lösung: Hardware-Austausch.**

Ein USB-RS485-Adapter mit synchron chip-seitiger DE/RE-Steuerung (FTDI FT232R/H-basiert)
verhindert das Echo physisch — kein Software-Workaround erforderlich.

## Aktuelle Konfiguration (Phase 4, deployed, unzureichend)

In `sensor.py` — direkter Server-Start ohne Proxy, Monkey-Patch aktiv:

```python
await StartAsyncSerialServer(
    ...
    handle_local_echo=False,
    ignore_missing_slaves=True,
)
```

## Logging

Der `_SimulatorOnlyFilter` in `sensor.py` ist installiert, aber unzureichend: pymodbus
erzeugt beim DEBUG-Level Meldungen ohne das `"send: 0x1 "` / `"recv: 0x1 "`-Präfix
(z. B. interne Decoder- und Framer-Meldungen), die den Filter passieren.

Empfohlene Minimaleinstellung für normale Betrieb:

```yaml
logger:
  default: warning
  logs:
    custom_components.sdm630_simulator: debug
    pymodbus: warning
```

## Offene Fragen / Testergebnisse

- [x] Phase 1 (`delay_before_rx=0.015`) → unzureichend
- [x] Phase 3 PTY Proxy (sent_buffer) → asyncio-Race, nicht funktional
- [x] Phase 3 PTY Proxy (reader-pause) → Echo trotzdem in pymodbus sichtbar
- [x] Logging-Filter → Pattern unvollständig
- [x] ModbusProtocol Monkey-Patch → unzureichend
- [ ] Hardware-Austausch (FTDI FT232R/H-basierter USB-RS485-Adapter)

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
