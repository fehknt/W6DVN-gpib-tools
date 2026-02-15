import pandas as pd
import numpy as np
import time
from PyQt5.QtCore import QObject, pyqtSignal
from sweep_utils import run_sweep

class SweepWorker(QObject):
    finished = pyqtSignal()
    progress = pyqtSignal(float, float)
    error = pyqtSignal(str)
    log = pyqtSignal(str)

    def __init__(self, sa, sg, frequencies, sg_tracking_disabled, sa_freq_offset, power, rbw, 
                 mode='finite', initial_data=None, start_freq=None, stop_freq=None):
        super().__init__()
        self.sa = sa
        self.sg = sg
        self.frequencies = frequencies
        self.sg_tracking_disabled = sg_tracking_disabled
        self.sa_freq_offset = sa_freq_offset
        self.power = power
        self.rbw = rbw
        self.mode = mode
        self.sweep_data = initial_data.copy() if initial_data is not None else pd.DataFrame(columns=['frequency', 'power'])
        self.start_freq = start_freq
        self.stop_freq = stop_freq
        self._is_cancelled = False

    def run(self):
        try:
            self.log.emit("Configuring devices for sweep...")
            self.sa.set_single_sweep_mode()
            self.sa.set_resolution_bandwidth(self.rbw)
            self.sa.set_zero_span()
            self.sg.set_power(self.power)
            self.sg.enable_rf(True)

            if self.mode == 'finite':
                sweep_generator = run_sweep(self.sa, self.sg, self.frequencies,
                                            sg_tracking_disabled=self.sg_tracking_disabled,
                                            sa_freq_offset=self.sa_freq_offset,
                                            log_callback=self.log.emit)
                for freq, power in sweep_generator:
                    if self._is_cancelled:
                        self.log.emit("Sweep cancellation requested.")
                        break
                    self.progress.emit(freq, power)
            
            elif self.mode == 'continuous':
                
                def _measure_point(freq):
                    """Helper to measure power at a single frequency."""
                    self.log.emit(f"Measuring at: {freq} Hz")
                    if not self.sg_tracking_disabled:
                        self.sg.set_frequency(freq + self.sa_freq_offset)
                        time.sleep(0.1)
                    sa_freq = freq + self.sa_freq_offset
                    self.sa.set_center_frequency(sa_freq)
                    self.sa.take_sweep()
                    self.sa.wait_done()
                    power = self.sa.get_marker_power()
                    self.log.emit(f"  Power: {power:.2f} dBm")
                    return power

                def _add_data_point(freq, power):
                    """Helper to add a data point to the worker's DataFrame and emit progress."""
                    new_point_df = pd.DataFrame([{'frequency': freq, 'power': power}])
                    if self.sweep_data.empty:
                        self.sweep_data = new_point_df
                    else:
                        self.sweep_data = pd.concat([self.sweep_data, new_point_df], ignore_index=True)
                    self.progress.emit(freq, power)

                # Ensure start and stop frequencies are included before interpolating
                for freq_endpoint in [self.start_freq, self.stop_freq]:
                    if freq_endpoint not in self.sweep_data['frequency'].values:
                        if self._is_cancelled: break
                        power = _measure_point(freq_endpoint)
                        _add_data_point(freq_endpoint, power)

                while not self._is_cancelled:
                    if len(self.sweep_data['frequency'].unique()) < 2:
                        self.log.emit("Not enough data to interpolate. Stopping continuous mode.")
                        break
                    
                    unique_freqs = sorted(self.sweep_data['frequency'].unique())
                    gaps = np.diff(unique_freqs)
                    if not np.any(gaps > 0):
                        self.log.emit("No frequency gaps found to interpolate. Stopping.")
                        break

                    gap_index = np.argmax(gaps)
                    start_gap = unique_freqs[gap_index]
                    end_gap = unique_freqs[gap_index+1]
                    next_freq = int(round(start_gap + (end_gap - start_gap) / 2))

                    if next_freq <= start_gap or next_freq >= end_gap:
                        self.log.emit("No new measurable points to add. Smallest gap reached. Stopping.")
                        break

                    power = _measure_point(next_freq)
                    _add_data_point(next_freq, power)

        except Exception as e:
            self.error.emit(f"Error running sweep: {e}")
        finally:
            if self.sg:
                self.sg.enable_rf(False)
            self.log.emit("Sweep finished.")
            self.finished.emit()

    def stop(self):
        self._is_cancelled = True
