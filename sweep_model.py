import pandas as pd
import json
import os
from PyQt5.QtCore import QObject, pyqtSignal

class SweepModel(QObject):
    data_changed = pyqtSignal()
    log = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.sweep_data = pd.DataFrame(columns=['frequency', 'power'])
        self.config = {}
        self.config_file = "config.json"

    def add_data_point(self, freq, power):
        new_data = pd.DataFrame([{'frequency': freq, 'power': power}])
        if self.sweep_data.empty:
            self.sweep_data = new_data
        else:
            self.sweep_data = pd.concat([self.sweep_data, new_data], ignore_index=True)
        self.data_changed.emit()

    def clear_data(self):
        self.sweep_data = pd.DataFrame(columns=['frequency', 'power'])
        self.log.emit("Sweep data cleared.")
        self.data_changed.emit()

    def get_sweep_data(self):
        return self.sweep_data.copy()

    def save_config(self, config):
        self.config = config
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=4)
            self.log.emit("Configuration saved.")
        except Exception as e:
            self.log.emit(f"Error saving configuration: {e}")

    def load_config(self):
        if not os.path.exists(self.config_file):
            self.log.emit("No config file found.")
            return {}
        
        try:
            with open(self.config_file, 'r') as f:
                self.config = json.load(f)
            self.log.emit("Configuration loaded.")
            return self.config
        except Exception as e:
            self.log.emit(f"Error loading configuration: {e}")
            return {}
