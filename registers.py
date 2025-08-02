"""
Common register object for SDM630 Modbus simulator
"""

class SDM630Register:
    def __init__(self, address, parameter_number, description, units, example_value=0.0):
        self.address = address
        self.parameter_number = parameter_number
        self.description = description
        self.units = units
        self.value = example_value
        self.example_value = example_value

    def set_value(self, value):
        self.value = value

    def get_value(self):
        return self.value
