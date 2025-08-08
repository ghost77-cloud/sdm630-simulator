"""
Common register object for SDM630 Modbus simulator
"""
from dataclasses import dataclass

@dataclass
class SDM630Register:
    address: int
    parameter_number: int
    description: str
    units: str
    value: float = 0.0
    default_value: float = 0.0
    negative_to_grid: bool = False  # True if negative values indicate power to grid

    def __init__(self, address, parameter_number, description, units, default_value=0.0, negative_to_grid=False):
        self.address = address
        self.parameter_number = parameter_number
        self.description = description
        self.units = units
        self.value = default_value
        self.default_value = default_value
        self.negative_to_grid = negative_to_grid

    def set_value(self, value: float):
        old_value = self.value
        self.value = value
        if hasattr(self, 'on_value_changed') and callable(self.on_value_changed):
            self.on_value_changed(self, old_value, value)

    def get_value(self):
        return self.value
        
    def set_value_change_callback(self, callback):
        """Set a callback to be called when the register value changes.
        
        Args:
            callback: Function that takes (register, old_value, new_value) as arguments
        """
        self.on_value_changed = callback
    
    def get_address(self):
        return self.address

@dataclass
class SDM630Registers:
    registers: list[SDM630Register]

    def __init__(self, registers: list[SDM630Register] | None = None):
        self.registers = registers if registers is not None else []

    def get_all(self):
        return self.registers
    
    def set_float(self, address: int, value: float):
        """Set a float value in the register by address."""
        for reg in self.registers:
            if reg.address == address:
                reg.set_value(float(value))
                return
    
    def get_float(self, address: int) -> float:
        """Get a float value from the register by address."""
        for reg in self.registers:
            if reg.address == address:
                return reg.get_value()
            
        raise ValueError(f"Register with address '{address}' not found.")