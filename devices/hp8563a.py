from devices.spectrum_analyzer import SpectrumAnalyzer
import time

class HP8563A(SpectrumAnalyzer):
    def __init__(self, resource_or_address):
        super().__init__(resource_or_address)

    def get_id(self):
        return self.query("ID?")

    def reset(self):
        """Resets the instrument and configures it for measurements."""
        self.write("*RST")
        time.sleep(1)
        self.write("AT AUTO")
        self.write("AUNITS DBM")

    def set_preset_mode(self):
        self.write(f"IP")

    def set_single_sweep_mode(self):
        self.write(f"SNGLS")

    def set_center_frequency(self, freq_hz):
        self.write(f"CF {freq_hz}Hz")

    def set_span(self, span_hz):
        self.write(f"SP {span_hz}Hz")

    def set_start_frequency(self, freq_hz):
        self.write(f"FA {freq_hz}Hz")

    def set_end_frequency(self, freq_hz):
        self.write(f"FB {freq_hz}Hz")

    def get_start_frequency(self):
        return float(self.query("FA?"))

    def get_end_frequency(self):
        return float(self.query("FB?"))

    def set_resolution_bandwidth(self, rbw_hz):
        self.write(f"RB {rbw_hz}Hz")

    def set_video_bandwidth(self, vbw_hz):
        self.write(f"VB {vbw_hz}Hz")

    def set_attenuation(self, att_db):
        self.write(f"AT {att_db}dB")

    def get_marker_power(self):
        return float(self.query("MKA?"))

    def set_reference_level(self, level_dbm):
        self.write(f"RL {level_dbm}DBM")

    def set_trace_data_format(self, format_char):
        self.write(f"TDF {format_char}")

    def take_sweep(self):
        self.write("TS")

    def get_sweep_time(self):
        """Queries the instrument for its sweep time."""
        return float(self.query("ST?"))

    def set_sweep_time(self, sweep_time):
        self.write(f"ST {sweep_time}")

    def get_trace_data(self, trace_num):
        return self.query(f"TA?")

    def wait_done(self):
        """Queries whether previous task has completed."""
        return self.query(f"DONE?")
