from PyQt5.QtCore import QObject, pyqtSignal, QThread
from sweep_utils import parse_frequency
import numpy as np
from sweep_worker import SweepWorker

class SweepController(QObject):
    log = pyqtSignal(str)
    sweep_status_changed = pyqtSignal(bool, str) # is_running, sweep_type

    def __init__(self, device_manager, sweep_model, parent=None):
        super().__init__(parent)
        self.device_manager = device_manager
        self.sweep_model = sweep_model
        self.sweep_thread = None
        self.sweep_worker = None

    def start_sweep(self, sweep_type, sweep_config):
        if self.sweep_thread and self.sweep_thread.isRunning():
            self.cancel_sweep()
            return

        if not self.device_manager.connected:
            self.log.emit("Cannot start sweep: Devices are not connected.")
            return

        try:
            start_freq = parse_frequency(sweep_config["start_freq"])
            stop_freq = parse_frequency(sweep_config["stop_freq"])
            
            if sweep_type == 'run_sweep':
                self.log.emit("Running sweep with current settings.")
                num_points = int(sweep_config["points"])
                frequencies = np.linspace(start_freq, stop_freq, num_points)
                self._start_sweep_thread(frequencies, 'finite', sweep_config, start_freq=start_freq, stop_freq=stop_freq)
            
            elif sweep_type == 'continuous_interpolation':
                self.log.emit("Starting continuous interpolation sweep.")
                self._start_sweep_thread([], 'continuous', sweep_config, initial_data=self.sweep_model.get_sweep_data(), 
                                         start_freq=start_freq, stop_freq=stop_freq)

        except Exception as e:
            self.log.emit(f"Invalid sweep parameter: {e}")

    def _start_sweep_thread(self, frequencies, mode, sweep_config, initial_data=None, start_freq=None, stop_freq=None):
        
        try:
            rbw = parse_frequency(sweep_config["rbw"])
            power = sweep_config["power"]
            sg_tracking_disabled = sweep_config["sg_tracking_disabled"]
            sa_freq_offset = int(sweep_config["sa_freq_offset"])
        except Exception as e:
            self.log.emit(f"Invalid sweep parameter: {e}")
            return

        self.sweep_status_changed.emit(True, sweep_config.get("active_button"))
        self.sweep_thread = QThread()
        self.sweep_worker = SweepWorker(
            sa=self.device_manager.sa,
            sg=self.device_manager.sg,
            frequencies=frequencies,
            sg_tracking_disabled=sg_tracking_disabled,
            sa_freq_offset=sa_freq_offset,
            power=power,
            rbw=rbw,
            mode=mode,
            initial_data=initial_data,
            start_freq=start_freq,
            stop_freq=stop_freq
        )
        self.sweep_worker.moveToThread(self.sweep_thread)

        self.sweep_thread.started.connect(self.sweep_worker.run)
        self.sweep_worker.finished.connect(self.on_sweep_finished)
        self.sweep_worker.progress.connect(self.sweep_model.add_data_point)
        self.sweep_worker.error.connect(self.log.emit)
        self.sweep_worker.log.connect(self.log.emit)
        
        self.sweep_worker.finished.connect(self.sweep_thread.quit)
        self.sweep_worker.finished.connect(self.sweep_worker.deleteLater)
        self.sweep_thread.finished.connect(self.sweep_thread.deleteLater)
        self.sweep_thread.finished.connect(self._on_thread_finished)

        self.sweep_thread.start()

    def cancel_sweep(self):
        self.log.emit("Attempting to cancel sweep...")
        if self.sweep_worker:
            self.sweep_worker.stop()

    def on_sweep_finished(self):
        self.log.emit("Sweep has finished or was cancelled.")
        self.sweep_status_changed.emit(False, "")
    
    def _on_thread_finished(self):
        self.log.emit("Sweep thread has finished.")
        self.sweep_thread = None
        self.sweep_worker = None

    def update_sg_freq(self, freq_str):
        if self.device_manager.connected and self.device_manager.sg:
            try:
                freq = parse_frequency(freq_str)
                self.device_manager.sg.set_frequency(freq)
                self.log.emit(f"Signal generator frequency set to {freq} Hz")
            except Exception as e:
                self.log.emit(f"Invalid frequency: {e}")
