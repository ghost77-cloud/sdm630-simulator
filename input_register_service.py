"""
Service to update SDM630 input registers by constant.
"""
if __package__ is None or __package__ == '':
    # Running standalone, use absolute imports
    from sdm630_input_registers import SDM630InputRegisters, PHASE_1_VOLTAGE, PHASE_2_VOLTAGE, PHASE_3_VOLTAGE, PHASE_1_CURRENT, PHASE_2_CURRENT, PHASE_3_CURRENT
else:
    # Running as a package (Home Assistant component), use relative imports
    from .sdm630_input_registers import SDM630InputRegisters, PHASE_1_VOLTAGE, PHASE_2_VOLTAGE, PHASE_3_VOLTAGE, PHASE_1_CURRENT, PHASE_2_CURRENT, PHASE_3_CURRENT

class InputRegisterService:
    def __init__(self, input_registers: SDM630InputRegisters):
        self.input_registers = input_registers

    def update(self, register_constant, value):
        """Update the value of the input register addressed by constant."""
        return self.input_registers.update_by_constant(register_constant, value)

# Example usage:
# input_registers_obj = SDM630InputRegisters()
# service = InputRegisterService(input_registers_obj)
# service.update(PHASE_1_VOLTAGE, 235.0)
