from abc import ABC, abstractmethod
import pyvisa as visa

class SignalGenerator(ABC):
    def __init__(self, resource_or_address):
        if isinstance(resource_or_address, str):
            rm = visa.ResourceManager()
            self.instrument = rm.open_resource(resource_or_address)
        else:
            self.instrument = resource_or_address

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def write(self, command):
        self.instrument.write(command)

    def read(self):
        return self.instrument.read()

    def query(self, command):
        return self.instrument.query(command)

    def close(self):
        self.instrument.close()

    @abstractmethod
    def get_id(self):
        pass

    @abstractmethod
    def set_frequency(self, frequency_hz):
        pass

    @abstractmethod
    def get_frequency(self):
        pass

    @abstractmethod
    def set_power(self, power_dbm):
        pass

    @abstractmethod
    def enable_rf(self, enabled: bool):
        pass
