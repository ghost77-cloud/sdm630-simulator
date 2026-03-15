# SDM630 Simulator

This custom component simulates an Eastron SDM630 smart meter for Home Assistant.

Der Simulator soll dabei helfen eine Growatt - THOR 11AS-P-V1 Wallbox zu steuern und diese im Modus PV-Überschussladen zu steuern. Dabei soll der Simulator die Daten aus dem Home-Assistent zum Growatt Wechselrichter, der seine Informationen über [Growatt Modbus](https://github.com/WouterTuinstra/Homeassistant-Growatt-Local-Modbus), Kopie unterhalb vom Verzeichnis: growat-modbus\Homeassistant-Growatt-Local-Modbus bereit stellt, erhalten. Sobald ausreichend Energie ins Netz eingespeist wird, soll der Simulator melden, dass die Wallbox laden kann.
Es gibt jedoch eine Einschränkung. Die Wallbox lädt das Fahrzeug nur, wenn min. eine Überschuss, also eine Einspeisung ins Netz stattfinded, von min. 4KW vorhanden ist.
Aus den Erfahrungen aus dem letzten Jahr zeigt sich, dass sehr viel Zeit, insbesondere bei wolkiger Lage die Einspeisung sehr stark schwankt und somit kein vernünftiges PV-Überschussladen möglich ist.
Zur Optimierung dessen, soll der Speicher (10KW), der am Growatt SPH10000TL3-BH-UP 10kW Hybrid Wechselrichter hängt genutzt werden. Entsprechend soll der Simulator prüfen, wie der Speicherstand ist. Wenn ausreichend Speicher vorhanden ist (Speicher ist initial voll) und die Leistung der Sonne schwankt, soll der Simulator das Minimum von 4KW melden. Ist mehr Überschuss vorhanden, soll natürlich mehr gemeldet werden. Lädt die Wallbox muss dies ebenfalls bemerkt werden (aufgrund des Verbrauchs, den der Wechselrichter abgibt), dann wird natürlich nicht mehr so viel Überschuss gemeldet. Je nach Uhrzeit und Wettervorhersage vom Home-Assistent kann mehr Puffer vom Speicher verwendet werden.


## Features

- Simulates MODBUS responses as per SDM630 protocol
- Exposes sensors/entities in Home Assistant

## Setup

1. Copy this folder to your `custom_components` directory.
2. Add `sdm630_sim:` to your `configuration.yaml`.
3. Restart Home Assistant.

## TODO

- Implement MODBUS TCP/RTU simulation
- Map SDM630 registers to simulated values
- Expose sensors in Home Assistant

## Reference

