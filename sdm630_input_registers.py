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

# Constants for input register addresses (parameter numbers 1-54)
PHASE_1_VOLTAGE = 1
PHASE_2_VOLTAGE = 3
PHASE_3_VOLTAGE = 5
PHASE_1_CURRENT = 7
PHASE_2_CURRENT = 9
PHASE_3_CURRENT = 11
PHASE_1_POWER = 13
PHASE_2_POWER = 15
PHASE_3_POWER = 17
PHASE_1_VA = 19
PHASE_2_VA = 21
PHASE_3_VA = 23
PHASE_1_VAR = 25
PHASE_2_VAR = 27
PHASE_3_VAR = 29
PHASE_1_PF = 31
PHASE_2_PF = 33
PHASE_3_PF = 35
PHASE_1_ANGLE = 37
PHASE_2_ANGLE = 39
PHASE_3_ANGLE = 41
AVG_LN_VOLTAGE = 43
AVG_LINE_CURRENT = 47
SUM_LINE_CURRENT = 49
TOTAL_POWER = 53
TOTAL_VA = 57
TOTAL_VAR = 61
TOTAL_PF = 63
TOTAL_ANGLE = 67
FREQUENCY = 71
TOTAL_IMPORT_KWH = 73
TOTAL_EXPORT_KWH = 75
TOTAL_IMPORT_KVARH = 77
TOTAL_EXPORT_KVARH = 79
TOTAL_VAH = 81
TOTAL_AH = 83
TOTAL_POWER_DEMAND = 85
MAX_TOTAL_POWER_DEMAND = 87
TOTAL_VA_DEMAND = 101
MAX_TOTAL_VA_DEMAND = 103
NEUTRAL_CURRENT_DEMAND = 105
MAX_NEUTRAL_CURRENT_DEMAND = 107

@dataclass
class SDM630InputRegisters(SDM630Registers):
    registers: list[SDM630Register]

    def __init__(self):
        self.registers = []
        self._init_registers()

    def _init_registers(self):
        # Parameter numbers as per SDM630 MODBUS protocol 1.2.1 - Input Registers
        # Each register uses 2 consecutive addresses for 32-bit float values
        self.registers.append(SDM630Register(PHASE_1_VOLTAGE, 1, "Phase 1 line to neutral volts", "Volts", 250.2))
        self.registers.append(SDM630Register(PHASE_2_VOLTAGE, 2, "Phase 2 line to neutral volts", "Volts", 231.1))
        self.registers.append(SDM630Register(PHASE_3_VOLTAGE, 3, "Phase 3 line to neutral volts", "Volts", 123.45))
        self.registers.append(SDM630Register(PHASE_1_CURRENT, 4, "Phase 1 current", "Amps", 5.1))
        self.registers.append(SDM630Register(PHASE_2_CURRENT, 5, "Phase 2 current", "Amps", 5.0))
        self.registers.append(SDM630Register(PHASE_3_CURRENT, 6, "Phase 3 current", "Amps", 5.2))
        self.registers.append(SDM630Register(PHASE_1_POWER, 7, "Phase 1 power", "Watts", 100.0))
        self.registers.append(SDM630Register(PHASE_2_POWER, 8, "Phase 2 power", "Watts", 101.0))
        self.registers.append(SDM630Register(PHASE_3_POWER, 9, "Phase 3 power", "Watts", 99.0))
        self.registers.append(SDM630Register(PHASE_1_VA, 10, "Phase 1 volt amps", "VA", 110.0))
        self.registers.append(SDM630Register(PHASE_2_VA, 11, "Phase 2 volt amps", "VA", 111.0))
        self.registers.append(SDM630Register(PHASE_3_VA, 12, "Phase 3 volt amps", "VA", 109.0))
        self.registers.append(SDM630Register(PHASE_1_VAR, 13, "Phase 1 reactive power", "VAr", 10.0))
        self.registers.append(SDM630Register(PHASE_2_VAR, 14, "Phase 2 reactive power", "VAr", 11.0))
        self.registers.append(SDM630Register(PHASE_3_VAR, 15, "Phase 3 reactive power", "VAr", 9.0))
        self.registers.append(SDM630Register(PHASE_1_PF, 16, "Phase 1 power factor", "None", 0.98))
        self.registers.append(SDM630Register(PHASE_2_PF, 17, "Phase 2 power factor", "None", 0.97))
        self.registers.append(SDM630Register(PHASE_3_PF, 18, "Phase 3 power factor", "None", 0.99))
        self.registers.append(SDM630Register(PHASE_1_ANGLE, 19, "Phase 1 phase angle", "Degrees", 1.0))
        self.registers.append(SDM630Register(PHASE_2_ANGLE, 20, "Phase 2 phase angle", "Degrees", 2.0))
        self.registers.append(SDM630Register(PHASE_3_ANGLE, 21, "Phase 3 phase angle", "Degrees", 3.0))
        self.registers.append(SDM630Register(AVG_LN_VOLTAGE, 22, "Average line to neutral volts", "Volts", 230.0))
        self.registers.append(SDM630Register(AVG_LINE_CURRENT, 24, "Average line current", "Amps", 5.1))
        self.registers.append(SDM630Register(SUM_LINE_CURRENT, 25, "Sum of line currents", "Amps", 15.3))
        self.registers.append(SDM630Register(TOTAL_POWER, 27, "Total system power", "Watts", 300.0))
        self.registers.append(SDM630Register(TOTAL_VA, 29, "Total system volt amps", "VA", 330.0))
        self.registers.append(SDM630Register(TOTAL_VAR, 31, "Total system VAr", "VAr", 30.0))
        self.registers.append(SDM630Register(TOTAL_PF, 32, "Total system power factor", "None", 0.98))
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
        self.registers.append(SDM630Register(MAX_TOTAL_VA_DEMAND, 53, "Maximum total system VA demand", "VA", 360.0))
        self.registers.append(SDM630Register(NEUTRAL_CURRENT_DEMAND, 53, "Neutral current demand", "Amps", 1.0))
        self.registers.append(SDM630Register(MAX_NEUTRAL_CURRENT_DEMAND, 54, "Maximum neutral current demand", "Amps", 1.2))
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
