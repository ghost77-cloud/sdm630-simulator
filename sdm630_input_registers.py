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

# Constants for input register addresses (0-based PDU addresses from SDM630 spec)
PHASE_1_VOLTAGE = 0      # 0x0000
PHASE_2_VOLTAGE = 2      # 0x0002
PHASE_3_VOLTAGE = 4      # 0x0004
PHASE_1_CURRENT = 6      # 0x0006
PHASE_2_CURRENT = 8      # 0x0008
PHASE_3_CURRENT = 10     # 0x000A
PHASE_1_POWER = 12       # 0x000C
PHASE_2_POWER = 14       # 0x000E
PHASE_3_POWER = 16       # 0x0010
PHASE_1_VA = 18          # 0x0012
PHASE_2_VA = 20          # 0x0014
PHASE_3_VA = 22          # 0x0016
PHASE_1_VAR = 24         # 0x0018
PHASE_2_VAR = 26         # 0x001A
PHASE_3_VAR = 28         # 0x001C
PHASE_1_PF = 30          # 0x001E
PHASE_2_PF = 32          # 0x0020
PHASE_3_PF = 34          # 0x0022
PHASE_1_ANGLE = 36       # 0x0024
PHASE_2_ANGLE = 38       # 0x0026
PHASE_3_ANGLE = 40       # 0x0028
AVG_LN_VOLTAGE = 42      # 0x002A
AVG_LINE_CURRENT = 46    # 0x002E
SUM_LINE_CURRENT = 48    # 0x0030
TOTAL_POWER = 52         # 0x0034
TOTAL_VA = 56            # 0x0038
TOTAL_VAR = 60           # 0x003C
TOTAL_PF = 62            # 0x003E
TOTAL_ANGLE = 66         # 0x0042
FREQUENCY = 70           # 0x0046
TOTAL_IMPORT_KWH = 72    # 0x0048
TOTAL_EXPORT_KWH = 74    # 0x004A
TOTAL_IMPORT_KVARH = 76  # 0x004C
TOTAL_EXPORT_KVARH = 78  # 0x004E
TOTAL_VAH = 80           # 0x0050
TOTAL_AH = 82            # 0x0052
TOTAL_POWER_DEMAND = 84  # 0x0054
MAX_TOTAL_POWER_DEMAND = 86  # 0x0056
TOTAL_VA_DEMAND = 100        # 0x0064
MAX_TOTAL_VA_DEMAND = 102    # 0x0066
NEUTRAL_CURRENT_DEMAND = 104 # 0x0068
MAX_NEUTRAL_CURRENT_DEMAND = 106  # 0x006A

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
        self.registers.append(SDM630Register(200, 101, "Line 1 to Line 2 volts", "Volts", 400.0))        # 0x00C8
        self.registers.append(SDM630Register(202, 102, "Line 2 to Line 3 volts", "Volts", 400.0))        # 0x00CA
        self.registers.append(SDM630Register(204, 103, "Line 3 to Line 1 volts", "Volts", 400.0))        # 0x00CC
        self.registers.append(SDM630Register(206, 104, "Average line to line volts", "Volts", 400.0))     # 0x00CE
        self.registers.append(SDM630Register(224, 113, "Neutral current", "Amps", 0.2))                  # 0x00E0
        self.registers.append(SDM630Register(234, 118, "Phase 1 L/N volts THD", "%", 0.2))               # 0x00EA
        self.registers.append(SDM630Register(236, 119, "Phase 2 L/N volts THD", "%", 0.3))               # 0x00EC
        self.registers.append(SDM630Register(238, 120, "Phase 3 L/N volts THD", "%", 0.4))               # 0x00EE
        self.registers.append(SDM630Register(240, 121, "Phase 1 Current THD", "%", 0.3))                 # 0x00F0
        self.registers.append(SDM630Register(242, 122, "Phase 2 Current THD", "%", 0.6))                 # 0x00F2
        self.registers.append(SDM630Register(244, 123, "Phase 3 Current THD", "%", 0.3))                 # 0x00F4
        self.registers.append(SDM630Register(248, 125, "Average line to neutral volts THD", "%", 0.2))   # 0x00F8
        self.registers.append(SDM630Register(250, 126, "Average line current THD", "%", 0.4))            # 0x00FA
        self.registers.append(SDM630Register(258, 130, "Phase 1 current demand", "Amps", 0.0))           # 0x0102
        self.registers.append(SDM630Register(260, 131, "Phase 2 current demand", "Amps", 3.0))           # 0x0104
        self.registers.append(SDM630Register(262, 132, "Phase 3 current demand", "Amps", 1.0))           # 0x0106
        self.registers.append(SDM630Register(264, 133, "Maximum phase 1 current demand", "Amps", 13.0))  # 0x0108
        self.registers.append(SDM630Register(266, 134, "Maximum phase 2 current demand", "Amps", 13.0))  # 0x010A
        self.registers.append(SDM630Register(268, 135, "Maximum phase 3 current demand", "Amps", 13.0))  # 0x010C
        self.registers.append(SDM630Register(334, 168, "Line 1 to line 2 volts THD", "%", 0.5))          # 0x014E
        self.registers.append(SDM630Register(336, 169, "Line 2 to line 3 volts THD", "%", 0.3))          # 0x0150
        self.registers.append(SDM630Register(338, 170, "Line 3 to line 1 volts THD", "%", 0.4))          # 0x0152
        self.registers.append(SDM630Register(340, 171, "Average line to line volts THD", "%", 0.3))      # 0x0154
        self.registers.append(SDM630Register(342, 172, "Total kwh(3)", "kWh", 1348.8))                   # 0x0156
        self.registers.append(SDM630Register(344, 173, "Total kvarh(3)", "kvarh", 125.0))                # 0x0158
        self.registers.append(SDM630Register(346, 174, "L1 import kwh", "kWh", 420.0))                   # 0x015A
        self.registers.append(SDM630Register(348, 175, "L2 import kwh", "kWh", 370.0))                   # 0x015C
        self.registers.append(SDM630Register(350, 176, "L3 import kWh", "kWh", 580.0))                   # 0x015E
        self.registers.append(SDM630Register(352, 177, "L1 export kWh", "kWh", 1500.0))                  # 0x0160
        self.registers.append(SDM630Register(354, 178, "L2 export kwh", "kWh", 1400.0))                  # 0x0162
        self.registers.append(SDM630Register(356, 179, "L3 export kWh", "kWh", 1300.0))                  # 0x0164
        self.registers.append(SDM630Register(358, 180, "L1 total kwh(3)", "kWh", 420.0))                 # 0x0166
        self.registers.append(SDM630Register(360, 181, "L2 total kWh(3)", "kWh", 370.0))                 # 0x0168
        self.registers.append(SDM630Register(362, 182, "L3 total kwh(3)", "kWh", 580.0))                 # 0x016A
        self.registers.append(SDM630Register(364, 183, "L1 import kvarh", "kvarh", 10.0))                # 0x016C
        self.registers.append(SDM630Register(366, 184, "L2 import kvarh", "kvarh", 13.0))                # 0x016E
        self.registers.append(SDM630Register(368, 185, "L3 import kvarh", "kvarh", 17.0))                # 0x0170
        self.registers.append(SDM630Register(370, 186, "L1 export kvarh", "kvarh", 12.0))                # 0x0172
        self.registers.append(SDM630Register(372, 187, "L2 export kvarh", "kvarh", 16.0))                # 0x0174
        self.registers.append(SDM630Register(374, 188, "L3 export kvarh", "kvarh", 19.0))                # 0x0176
        self.registers.append(SDM630Register(376, 189, "L1 total kvarh (3)", "kvarh", 25.0))             # 0x0178
        self.registers.append(SDM630Register(378, 190, "L2 total kvarh (3)", "kvarh", 27.0))             # 0x017A
        self.registers.append(SDM630Register(380, 191, "L3 total kvarh (3)", "kvarh", 30.0))             # 0x017C
        
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
