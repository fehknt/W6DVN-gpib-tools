import pyvisa
from devices.signal_generator import SignalGenerator

class HP8673B(SignalGenerator):
    def __init__(self, resource_or_address):
        super().__init__(resource_or_address)

    def get_id(self):
        return "HP8673B"

    def set_frequency(self, frequency_hz):
        self.instrument.write(f"CW{int(frequency_hz)}HZ")

    def get_frequency(self):
        return self.instrument.query(f"CW?")

    def set_power(self, power_dbm):
        self.instrument.write(f"PL{int(power_dbm)}DB")

    def enable_rf(self, enabled: bool):
        if enabled:
            self.instrument.write("RF1")
        else:
            self.instrument.write("RF0")

if __name__ == '__main__':
    rm = pyvisa.ResourceManager()
    print(rm.list_resources())
    # Example usage:
    # gen = HP8673B('GPIB0::19::INSTR')
    # print(gen.get_id())
    # gen.set_frequency(1e9)
    # gen.set_power(0)
    # gen.enable_rf(True)
    # gen.close()
