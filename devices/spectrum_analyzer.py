from abc import ABC, abstractmethod
import pyvisa as visa
import time

class SpectrumAnalyzer(ABC):
    def __init__(self, resource_or_address):
        if isinstance(resource_or_address, str):
            rm = visa.ResourceManager()
            self.instrument = rm.open_resource(resource_or_address)
        else:
            self.instrument = resource_or_address
        
        self.instrument.timeout = 10000

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def write(self, command):
        #print(f"GPIB WRITE: {command}")
        self.instrument.write(command)

    def read(self):
        response = self.instrument.read()
        #print(f"GPIB READ: {response.strip()}")
        return response

    def query(self, command):
        response = self.instrument.query(command)
        #print(f"GPIB QUERY '{command}': {response.strip()}")
        return response

    def close(self):
        self.instrument.close()

    @abstractmethod
    def get_id(self):
        pass

    @abstractmethod
    def reset(self):
        pass

    @abstractmethod
    def set_center_frequency(self, freq_hz):
        pass

    def set_zero_span(self):
        self.set_span(0)

    @abstractmethod
    def set_span(self, span_hz):
        pass

    @abstractmethod
    def set_start_frequency(self, freq_hz):
        pass

    @abstractmethod
    def set_end_frequency(self, freq_hz):
        pass

    @abstractmethod
    def get_start_frequency(self):
        pass

    @abstractmethod
    def get_end_frequency(self):
        pass

    @abstractmethod
    def set_resolution_bandwidth(self, rbw_hz):
        pass

    @abstractmethod
    def set_video_bandwidth(self, vbw_hz):
        pass

    @abstractmethod
    def set_attenuation(self, att_db):
        pass

    @abstractmethod
    def get_marker_power(self):
        pass

    @abstractmethod
    def set_reference_level(self, level_dbm):
        pass
        
    @abstractmethod
    def set_trace_data_format(self, format_char):
        pass

    @abstractmethod
    def take_sweep(self):
        pass

    def take_sweep_and_wait(self):
        sweep_time_s = self.get_sweep_time()
        self.take_sweep()
        # Wait for sweep to complete, with a small buffer
        time.sleep(sweep_time_s * 1.1 + 0.1)

    @abstractmethod
    def get_sweep_time(self):
        pass
    
    @abstractmethod
    def set_sweep_time(self, sweep_time):
        pass

    @abstractmethod
    def get_trace_data(self, trace_num):
        pass

    @abstractmethod
    def wait_done(self):
        pass
        
    @abstractmethod
    def set_preset_mode(self):
        pass

    @abstractmethod
    def set_single_sweep_mode(self):
        pass

    @property
    def has_tracking_generator(self):
        return False

    def turn_off_tracking_generator(self):
        if self.has_tracking_generator:
            raise NotImplementedError
        else:
            print("Warning: Tracking generator not supported on this device.")
            pass

    def set_tracking_generator_power(self, power_dbm):
        if self.has_tracking_generator:
            raise NotImplementedError
        else:
            print("Warning: Tracking generator not supported on this device.")
            pass
            
    @property
    def has_emc_personality(self):
        return False
        
    def find_peaks_emc(self):
        if self.has_emc_personality:
            raise NotImplementedError
        else:
            print("Warning: EMC personality not supported on this device.")
            return []
