"""
SDM630 Input Register Definitions
All input registers for SDM630 from 30001 to 30381, with metadata from specification.
"""
from dataclasses import dataclass

if __package__ is None or __package__ == '':
    # Running standalone, use absolute imports
    from registers import SDM630Register, SDM630Registers
else:
    # Running as a package (Home Assistant component), use relative imports
    from .registers import SDM630Register, SDM630Registers

# Constants for input register addresses (1-based PDU addresses as per SDM630 spec)
# The SDM630 spec uses 1-based addressing: first register pair starts at PDU 0x0001.
# Formula: address = (2 * param_number) - 1
PHASE_1_VOLTAGE = 1      # 0x0001  param 1
PHASE_2_VOLTAGE = 3      # 0x0003  param 2
PHASE_3_VOLTAGE = 5      # 0x0005  param 3
PHASE_1_CURRENT = 7      # 0x0007  param 4
PHASE_2_CURRENT = 9      # 0x0009  param 5
PHASE_3_CURRENT = 11     # 0x000B  param 6
PHASE_1_POWER = 13       # 0x000D  param 7
PHASE_2_POWER = 15       # 0x000F  param 8
PHASE_3_POWER = 17       # 0x0011  param 9
PHASE_1_VA = 19          # 0x0013  param 10
PHASE_2_VA = 21          # 0x0015  param 11
PHASE_3_VA = 23          # 0x0017  param 12
PHASE_1_VAR = 25         # 0x0019  param 13
PHASE_2_VAR = 27         # 0x001B  param 14
PHASE_3_VAR = 29         # 0x001D  param 15
PHASE_1_PF = 31          # 0x001F  param 16
PHASE_2_PF = 33          # 0x0021  param 17
PHASE_3_PF = 35          # 0x0023  param 18
PHASE_1_ANGLE = 37       # 0x0025  param 19
PHASE_2_ANGLE = 39       # 0x0027  param 20
PHASE_3_ANGLE = 41       # 0x0029  param 21
AVG_LN_VOLTAGE = 43      # 0x002B  param 22
AVG_LINE_CURRENT = 47    # 0x002F  param 24
SUM_LINE_CURRENT = 49    # 0x0031  param 25
TOTAL_POWER = 53         # 0x0035  param 27
TOTAL_VA = 57            # 0x0039  param 29
TOTAL_VAR = 61           # 0x003D  param 31
TOTAL_PF = 63            # 0x003F  param 32
TOTAL_ANGLE = 67         # 0x0043  param 34
FREQUENCY = 71           # 0x0047  param 36
TOTAL_IMPORT_KWH = 73    # 0x0049  param 37
TOTAL_EXPORT_KWH = 75    # 0x004B  param 38
TOTAL_IMPORT_KVARH = 77  # 0x004D  param 39
TOTAL_EXPORT_KVARH = 79  # 0x004F  param 40
TOTAL_VAH = 81           # 0x0051  param 41
TOTAL_AH = 83            # 0x0053  param 42
TOTAL_POWER_DEMAND = 85  # 0x0055  param 43
MAX_TOTAL_POWER_DEMAND = 87   # 0x0057  param 44
TOTAL_VA_DEMAND = 101         # 0x0065  param 51
MAX_TOTAL_VA_DEMAND = 103     # 0x0067  param 52
NEUTRAL_CURRENT_DEMAND = 105  # 0x0069  param 53
MAX_NEUTRAL_CURRENT_DEMAND = 107  # 0x006B  param 54

@dataclass
class SDM630InputRegisters(SDM630Registers):
    registers: list[SDM630Register]

    def __init__(self):
        self.registers = []
        self._init_registers()

    def _init_registers(self):
        # Parameter numbers as per SDM630 MODBUS protocol 1.2.1 - Input Registers
        # Each register uses 2 consecutive addresses for 32-bit float values
        self.registers.append(SDM630Register(PHASE_1_VOLTAGE, 1, "Phase 1 line to neutral volts", "Volts", 237.2))
        self.registers.append(SDM630Register(PHASE_2_VOLTAGE, 2, "Phase 2 line to neutral volts", "Volts", 235.1))
        self.registers.append(SDM630Register(PHASE_3_VOLTAGE, 3, "Phase 3 line to neutral volts", "Volts", 239.45))
        self.registers.append(SDM630Register(PHASE_1_CURRENT, 4, "Phase 1 current", "Amps", 5.1))
        self.registers.append(SDM630Register(PHASE_2_CURRENT, 5, "Phase 2 current", "Amps", 5.0))
        self.registers.append(SDM630Register(PHASE_3_CURRENT, 6, "Phase 3 current", "Amps", 5.2))
        self.registers.append(SDM630Register(PHASE_1_POWER, 7, "Phase 1 power", "Watts", 100.0, True))
        self.registers.append(SDM630Register(PHASE_2_POWER, 8, "Phase 2 power", "Watts", 101.0, True))
        self.registers.append(SDM630Register(PHASE_3_POWER, 9, "Phase 3 power", "Watts", 99.0, True))
        self.registers.append(SDM630Register(PHASE_1_VA, 10, "Phase 1 volt amps", "VA", 110.0))
        self.registers.append(SDM630Register(PHASE_2_VA, 11, "Phase 2 volt amps", "VA", 111.0))
        self.registers.append(SDM630Register(PHASE_3_VA, 12, "Phase 3 volt amps", "VA", 109.0))
        self.registers.append(SDM630Register(PHASE_1_VAR, 13, "Phase 1 reactive power", "VAr", 10.0, True))
        self.registers.append(SDM630Register(PHASE_2_VAR, 14, "Phase 2 reactive power", "VAr", 11.0, True))
        self.registers.append(SDM630Register(PHASE_3_VAR, 15, "Phase 3 reactive power", "VAr", 9.0, True))
        self.registers.append(SDM630Register(PHASE_1_PF, 16, "Phase 1 power factor", "None", 0.98, True))
        self.registers.append(SDM630Register(PHASE_2_PF, 17, "Phase 2 power factor", "None", 0.97, True))
        self.registers.append(SDM630Register(PHASE_3_PF, 18, "Phase 3 power factor", "None", 0.99, True))
        self.registers.append(SDM630Register(PHASE_1_ANGLE, 19, "Phase 1 phase angle", "Degrees", 1.0))
        self.registers.append(SDM630Register(PHASE_2_ANGLE, 20, "Phase 2 phase angle", "Degrees", 2.0))
        self.registers.append(SDM630Register(PHASE_3_ANGLE, 21, "Phase 3 phase angle", "Degrees", 3.0))
        self.registers.append(SDM630Register(AVG_LN_VOLTAGE, 22, "Average line to neutral volts", "Volts", 230.0))
        self.registers.append(SDM630Register(AVG_LINE_CURRENT, 24, "Average line current", "Amps", 5.1))
        self.registers.append(SDM630Register(SUM_LINE_CURRENT, 25, "Sum of line currents", "Amps", 15.3))
        self.registers.append(SDM630Register(TOTAL_POWER, 27, "Total system power", "Watts", 300.0, True))
        self.registers.append(SDM630Register(TOTAL_VA, 29, "Total system volt amps", "VA", 330.0))
        self.registers.append(SDM630Register(TOTAL_VAR, 31, "Total system VAr", "VAr", 30.0, True))
        self.registers.append(SDM630Register(TOTAL_PF, 32, "Total system power factor", "None", 0.98, True))
        self.registers.append(SDM630Register(TOTAL_ANGLE, 34, "Total system phase angle", "Degrees", 2.0))
        self.registers.append(SDM630Register(FREQUENCY, 36, "Frequency of supply voltages", "Hz", 50.0))
        self.registers.append(SDM630Register(TOTAL_IMPORT_KWH, 37, "Total Import kWh", "kWh", 1000.0))
        self.registers.append(SDM630Register(TOTAL_EXPORT_KWH, 38, "Total Export kWh", "kWh", 500.0))
        self.registers.append(SDM630Register(TOTAL_IMPORT_KVARH, 39, "Total Import kVArh", "kVArh", 200.0))
        self.registers.append(SDM630Register(TOTAL_EXPORT_KVARH, 40, "Total Export kVArh", "kVArh", 100.0))
        self.registers.append(SDM630Register(TOTAL_VAH, 41, "Total VAh", "kVAh", 1500.0))
        self.registers.append(SDM630Register(TOTAL_AH, 42, "Total Ah", "Ah", 300.0))
        self.registers.append(SDM630Register(TOTAL_POWER_DEMAND, 43, "Total system power demand", "W", 320.0))
        self.registers.append(SDM630Register(MAX_TOTAL_POWER_DEMAND, 44, "Maximum total system power demand", "VA", 350.0))
        self.registers.append(SDM630Register(TOTAL_VA_DEMAND, 51, "Total system VA demand", "VA", 340.0))
        self.registers.append(SDM630Register(MAX_TOTAL_VA_DEMAND, 52, "Maximum total system VA demand", "VA", 360.0))
        self.registers.append(SDM630Register(NEUTRAL_CURRENT_DEMAND, 53, "Neutral current demand", "Amps", 1.0))
        self.registers.append(SDM630Register(MAX_NEUTRAL_CURRENT_DEMAND, 54, "Maximum neutral current demand", "Amps", 1.2))
        self.registers.append(SDM630Register(201, 101, "Line 1 to Line 2 volts", "Volts", 400.0))         # 0x00C9
        self.registers.append(SDM630Register(203, 102, "Line 2 to Line 3 volts", "Volts", 400.0))         # 0x00CB
        self.registers.append(SDM630Register(205, 103, "Line 3 to Line 1 volts", "Volts", 400.0))         # 0x00CD
        self.registers.append(SDM630Register(207, 104, "Average line to line volts", "Volts", 400.0))      # 0x00CF
        self.registers.append(SDM630Register(225, 113, "Neutral current", "Amps", 0.2))                   # 0x00E1
        self.registers.append(SDM630Register(235, 118, "Phase 1 L/N volts THD", "%", 0.2))                # 0x00EB
        self.registers.append(SDM630Register(237, 119, "Phase 2 L/N volts THD", "%", 0.3))                # 0x00ED
        self.registers.append(SDM630Register(239, 120, "Phase 3 L/N volts THD", "%", 0.4))                # 0x00EF
        self.registers.append(SDM630Register(241, 121, "Phase 1 Current THD", "%", 0.3))                  # 0x00F1
        self.registers.append(SDM630Register(243, 122, "Phase 2 Current THD", "%", 0.6))                  # 0x00F3
        self.registers.append(SDM630Register(245, 123, "Phase 3 Current THD", "%", 0.3))                  # 0x00F5
        self.registers.append(SDM630Register(249, 125, "Average line to neutral volts THD", "%", 0.2))    # 0x00F9
        self.registers.append(SDM630Register(251, 126, "Average line current THD", "%", 0.4))             # 0x00FB
        self.registers.append(SDM630Register(259, 130, "Phase 1 current demand", "Amps", 0.0))            # 0x0103
        self.registers.append(SDM630Register(261, 131, "Phase 2 current demand", "Amps", 3.0))            # 0x0105
        self.registers.append(SDM630Register(263, 132, "Phase 3 current demand", "Amps", 1.0))            # 0x0107
        self.registers.append(SDM630Register(265, 133, "Maximum phase 1 current demand", "Amps", 13.0))   # 0x0109
        self.registers.append(SDM630Register(267, 134, "Maximum phase 2 current demand", "Amps", 13.0))   # 0x010B
        self.registers.append(SDM630Register(269, 135, "Maximum phase 3 current demand", "Amps", 13.0))   # 0x010D
        self.registers.append(SDM630Register(335, 168, "Line 1 to line 2 volts THD", "%", 0.5))           # 0x014F
        self.registers.append(SDM630Register(337, 169, "Line 2 to line 3 volts THD", "%", 0.3))           # 0x0151
        self.registers.append(SDM630Register(339, 170, "Line 3 to line 1 volts THD", "%", 0.4))           # 0x0153
        self.registers.append(SDM630Register(341, 171, "Average line to line volts THD", "%", 0.3))       # 0x0155
        self.registers.append(SDM630Register(343, 172, "Total kwh(3)", "kWh", 1348.8))                    # 0x0157
        self.registers.append(SDM630Register(345, 173, "Total kvarh(3)", "kvarh", 125.0))                 # 0x0159
        self.registers.append(SDM630Register(347, 174, "L1 import kwh", "kWh", 420.0))                    # 0x015B
        self.registers.append(SDM630Register(349, 175, "L2 import kwh", "kWh", 370.0))                    # 0x015D
        self.registers.append(SDM630Register(351, 176, "L3 import kWh", "kWh", 580.0))                    # 0x015F
        self.registers.append(SDM630Register(353, 177, "L1 export kWh", "kWh", 1500.0))                   # 0x0161
        self.registers.append(SDM630Register(355, 178, "L2 export kwh", "kWh", 1400.0))                   # 0x0163
        self.registers.append(SDM630Register(357, 179, "L3 export kWh", "kWh", 1300.0))                   # 0x0165
        self.registers.append(SDM630Register(359, 180, "L1 total kwh(3)", "kWh", 420.0))                  # 0x0167
        self.registers.append(SDM630Register(361, 181, "L2 total kWh(3)", "kWh", 370.0))                  # 0x0169
        self.registers.append(SDM630Register(363, 182, "L3 total kwh(3)", "kWh", 580.0))                  # 0x016B
        self.registers.append(SDM630Register(365, 183, "L1 import kvarh", "kvarh", 10.0))                 # 0x016D
        self.registers.append(SDM630Register(367, 184, "L2 import kvarh", "kvarh", 13.0))                 # 0x016F
        self.registers.append(SDM630Register(369, 185, "L3 import kvarh", "kvarh", 17.0))                 # 0x0171
        self.registers.append(SDM630Register(371, 186, "L1 export kvarh", "kvarh", 12.0))                 # 0x0173
        self.registers.append(SDM630Register(373, 187, "L2 export kvarh", "kvarh", 16.0))                 # 0x0175
        self.registers.append(SDM630Register(375, 188, "L3 export kvarh", "kvarh", 19.0))                 # 0x0177
        self.registers.append(SDM630Register(377, 189, "L1 total kvarh (3)", "kvarh", 25.0))              # 0x0179
        self.registers.append(SDM630Register(379, 190, "L2 total kvarh (3)", "kvarh", 27.0))              # 0x017B
        self.registers.append(SDM630Register(381, 191, "L3 total kvarh (3)", "kvarh", 30.0))              # 0x017D
        
        super().__init__(self.registers)
        
    def get_by_address(self, address):
        for reg in self.registers:
            if reg.address == address:
                return reg
        return None

    def update_by_constant(self, constant, value):
        reg = self.get_by_address(constant)
        if reg:
            reg.set_value(value)
            return True
        return False
