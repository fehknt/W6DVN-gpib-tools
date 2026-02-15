import pyqtgraph as pg
import sys
from datetime import datetime
from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel, QPushButton, QHBoxLayout, QVBoxLayout, QWidget, QPlainTextEdit, QComboBox, QLineEdit, QSizePolicy, QFrame, QCheckBox, QAction, QMessageBox
import numpy as np

from device_manager import DeviceManager
from sweep_model import SweepModel
from sweep_controller import SweepController

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("SweeperGUI")
        self.setGeometry(100, 100, 800, 500)

        self.init_ui()
        self.init_models_and_controllers()
        self.connect_signals()

        self.load_config()
        self.device_manager.discover_devices()

    def init_ui(self):
        self.init_menu()
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        vlayout = QVBoxLayout()
        central_widget.setLayout(vlayout)

        # Device Selection Section
        hlayout = QHBoxLayout()
        vlayout.addLayout(hlayout)
        lblSection = QLabel("Device Selection", self);
        lblSection.setStyleSheet("QLabel { color : gray; }");
        lblSection.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        hlayout.addWidget(lblSection);
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        hlayout.addWidget(line)

        hlayout = QHBoxLayout()
        vlayout.addLayout(hlayout)
        vlayout2 = QVBoxLayout()
        hlayout.addLayout(vlayout2)

        hlayout2 = QHBoxLayout()
        vlayout2.addLayout(hlayout2)
        self.lblSignalGenerator = QLabel("Select Signal Generator: ", self)
        hlayout2.addWidget(self.lblSignalGenerator)
        self.cbSignalGenerator = QComboBox()
        self.cbSignalGenerator.addItems(["HP8673B"])
        hlayout2.addWidget(self.cbSignalGenerator)
        self.cbSGAddr = QComboBox()
        hlayout2.addWidget(self.cbSGAddr)

        hlayout3 = QHBoxLayout()
        vlayout2.addLayout(hlayout3)
        self.lblSpectrumAnalyzer = QLabel("Select Spectrum Analyzer: ", self)
        hlayout3.addWidget(self.lblSpectrumAnalyzer)
        self.cbSpectrumAnalyzer = QComboBox()
        self.cbSpectrumAnalyzer.addItems(["HP8563A", "HP8593EM"])
        hlayout3.addWidget(self.cbSpectrumAnalyzer)
        self.cbSAAddr = QComboBox()
        hlayout3.addWidget(self.cbSAAddr)

        self.btnDiscoverDevices = QPushButton("Refresh Device List", self)
        self.btnDiscoverDevices.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        hlayout.addWidget(self.btnDiscoverDevices)

        self.btnConnectDisconnect = QPushButton("Connect Devices", self)
        vlayout.addWidget(self.btnConnectDisconnect)

        # Plot Section
        hlayout = QHBoxLayout()
        vlayout.addLayout(hlayout)
        lblSection = QLabel("Sweep Data Plot", self);
        lblSection.setStyleSheet("QLabel { color : gray; }");
        lblSection.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        hlayout.addWidget(lblSection);
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        hlayout.addWidget(line)

        hlayout = QHBoxLayout()
        vlayout.addLayout(hlayout)
        self.plot_widget = pg.PlotWidget()
        hlayout.addWidget(self.plot_widget)

        self.plot_widget.setBackground('w')
        self.plot_widget.setLabel('left', 'Amplitude (dBm)')
        self.plot_widget.setLabel('bottom', 'Frequency', units='Hz')
        self.plot_widget.setStyleSheet("border: 1px solid grey; border-radius: 3px; background-color: white;")
        self.plot_widget.showGrid(x=True, y=True)

        self.scatter = pg.ScatterPlotItem(pen=pg.mkPen(None), brush=pg.mkBrush(255, 0, 0, 150), size=10, hoverable=True, tip='{x:.0f}Hz\n{y:.0f}dBm'.format, hoverPen=pg.mkPen('y', width=2), hoverBrush=pg.mkBrush('g'))
        self.curve = self.plot_widget.plot([], [], pen=pg.mkPen(color='gray', width=1), symbol='o', symbolSize=8, symbolBrush=(0,0,255), symbolPen='k')
        self.plot_widget.addItem(self.scatter)

        # Sweep Configuration Section
        hlayout = QHBoxLayout()
        vlayout.addLayout(hlayout)
        lblSection = QLabel("Sweep Configuration", self);
        lblSection.setStyleSheet("QLabel { color : gray; }");
        lblSection.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        hlayout.addWidget(lblSection);
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        hlayout.addWidget(line)

        hlayout = QHBoxLayout()
        vlayout.addLayout(hlayout)
        self.lblStartFreq = QLabel("Start Freq: ", self)
        hlayout.addWidget(self.lblStartFreq)
        self.tbStartFreq = QLineEdit("23800000kHz")
        hlayout.addWidget(self.tbStartFreq)

        self.lblStopFreq = QLabel("Stop Freq: ", self)
        hlayout.addWidget(self.lblStopFreq)
        self.tbStopFreq = QLineEdit("24300000kHz")
        hlayout.addWidget(self.tbStopFreq)

        self.lblRBW = QLabel("RBW: ", self)
        hlayout.addWidget(self.lblRBW)
        self.cbRBW = QComboBox()
        self.cbRBW.addItems(["30Hz", "100Hz", "300Hz", "1kHz", "3kHz", "10kHz", "30kHz", "100kHz", "300kHz", "1MHz", "2MHz"])
        hlayout.addWidget(self.cbRBW)

        self.lblPoints = QLabel("Points: ", self)
        hlayout.addWidget(self.lblPoints)
        self.tbPoints = QLineEdit("41")
        hlayout.addWidget(self.tbPoints)

        self.lblSAFreqOffset = QLabel("Analyzer Freq Offset (Hz): ", self)
        hlayout.addWidget(self.lblSAFreqOffset)
        self.tbSAFreqOffset = QLineEdit("0")
        hlayout.addWidget(self.tbSAFreqOffset)

        hlayout = QHBoxLayout()
        vlayout.addLayout(hlayout)
        self.lblPower = QLabel("Power (dBm): ", self)
        hlayout.addWidget(self.lblPower)
        self.tbPower = QLineEdit("-40")
        hlayout.addWidget(self.tbPower)

        self.cbDisableTracking = QCheckBox("Disable signal generator tracking")
        self.cbDisableTracking.setChecked(False)
        hlayout.addWidget(self.cbDisableTracking)

        self.tbSGFreq = QLineEdit("24192000000")
        hlayout.addWidget(self.tbSGFreq)
        self.btnSetSGFreq = QPushButton("Set SG Freq", self)
        hlayout.addWidget(self.btnSetSGFreq)

        sweep_button_layout = QHBoxLayout()
        self.btnClearSweepData = QPushButton("Clear Sweep Data", self)
        self.btnClearSweepData.setStyleSheet("background-color: indianred; color: white;")
        sweep_button_layout.addWidget(self.btnClearSweepData)

        self.btnRunSweep = QPushButton("Run Sweep", self)
        sweep_button_layout.addWidget(self.btnRunSweep)

        self.btnContinuousInterpolation = QPushButton("Continuous Interpolation", self)
        sweep_button_layout.addWidget(self.btnContinuousInterpolation)
        vlayout.addLayout(sweep_button_layout)

        self.tbLog = QPlainTextEdit()
        self.tbLog.setReadOnly(True)
        self.tbLog.setMaximumBlockCount(1000)
        vlayout.addWidget(self.tbLog)

        self.ui_elements_to_disable = [
            self.cbSignalGenerator, self.cbSGAddr, self.cbSpectrumAnalyzer, self.cbSAAddr,
            self.btnDiscoverDevices, self.btnConnectDisconnect, self.tbStartFreq,
            self.tbStopFreq, self.cbRBW, self.tbPoints, self.tbSAFreqOffset,
            self.tbPower, self.cbDisableTracking, self.tbSGFreq, self.btnSetSGFreq,
            self.btnClearSweepData, self.btnRunSweep, self.btnContinuousInterpolation
        ]

    def init_menu(self):
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("File")
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        instruction_menu = menu_bar.addMenu("Instructions")
        alignment_action = QAction("Alignment Procedure", self)
        alignment_action.triggered.connect(self.show_alignment)
        instruction_menu.addAction(alignment_action)
        help_menu = menu_bar.addMenu("Help")
        about_action = QAction("About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def init_models_and_controllers(self):
        self.device_manager = DeviceManager()
        self.sweep_model = SweepModel()
        self.sweep_controller = SweepController(self.device_manager, self.sweep_model)
        self.last_sa_addr = ""
        self.last_sg_addr = ""

    def connect_signals(self):
        # Device Manager Signals
        self.device_manager.log.connect(self.log)
        self.device_manager.devices_discovered.connect(self.update_device_lists)
        self.device_manager.connection_status_changed.connect(self.on_connection_status_changed)
        self.btnDiscoverDevices.clicked.connect(self.device_manager.discover_devices)
        self.btnConnectDisconnect.clicked.connect(self.handle_connect_disconnect)

        # Sweep Model Signals
        self.sweep_model.log.connect(self.log)
        self.sweep_model.data_changed.connect(self.update_plot)
        self.btnClearSweepData.clicked.connect(self.handle_clear_data)

        # Sweep Controller Signals
        self.sweep_controller.log.connect(self.log)
        self.sweep_controller.sweep_status_changed.connect(self.set_ui_for_sweep)
        self.btnRunSweep.clicked.connect(lambda: self.handle_sweep_start('run_sweep'))
        self.btnContinuousInterpolation.clicked.connect(lambda: self.handle_sweep_start('continuous_interpolation'))
        self.btnSetSGFreq.clicked.connect(lambda: self.sweep_controller.update_sg_freq(self.tbSGFreq.text()))

    def log(self, message):
        self.tbLog.appendPlainText(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}\t{message}")
        self.tbLog.verticalScrollBar().setValue(self.tbLog.verticalScrollBar().maximum())
    
    def update_device_lists(self, devices):
        self.cbSAAddr.clear()
        self.cbSGAddr.clear()
        self.cbSAAddr.addItems(devices)
        self.cbSGAddr.addItems(devices)

        if self.last_sa_addr in devices:
            self.cbSAAddr.setCurrentText(self.last_sa_addr)
        if self.last_sg_addr in devices:
            self.cbSGAddr.setCurrentText(self.last_sg_addr)

        if self.last_sa_addr and self.last_sg_addr and not self.device_manager.connected:
            if self.last_sa_addr in devices and self.last_sg_addr in devices:
                self.handle_connect_disconnect()

    def on_connection_status_changed(self, connected, sa_id, sg_id):
        self.btnConnectDisconnect.setText("Disconnect Devices" if connected else "Connect Devices")
        if connected:
            self.log(f"Connection successful. SA: {sa_id}, SG: {sg_id}")
        else:
            self.log("Devices disconnected.")

    def handle_connect_disconnect(self):
        if self.device_manager.connected:
            self.device_manager.disconnect_devices()
        else:
            sa_addr = self.cbSAAddr.currentText()
            sg_addr = self.cbSGAddr.currentText()
            sa_model = self.cbSpectrumAnalyzer.currentText()
            sg_model = self.cbSignalGenerator.currentText()
            if not sa_addr or not sg_addr:
                self.log("Error: Please select both an SA and SG address.")
                return
            self.device_manager.connect_devices(sa_addr, sg_addr, sa_model, sg_model)

    def handle_clear_data(self):
        reply = QMessageBox.question(self, 'Clear Data', "This will clear all existing sweep data. Are you sure?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.sweep_model.clear_data()

    def handle_sweep_start(self, sweep_type):
        config = {
            "start_freq": self.tbStartFreq.text(),
            "stop_freq": self.tbStopFreq.text(),
            "rbw": self.cbRBW.currentText(),
            "points": self.tbPoints.text(),
            "sa_freq_offset": self.tbSAFreqOffset.text(),
            "power": self.tbPower.text(),
            "sg_tracking_disabled": self.cbDisableTracking.isChecked(),
            "sg_manual_freq": self.tbSGFreq.text(),
            "active_button": sweep_type
        }
        self.sweep_controller.start_sweep(sweep_type, config)
    
    def set_ui_for_sweep(self, is_running, active_button_type):
        for element in self.ui_elements_to_disable:
            if element not in [self.btnRunSweep, self.btnContinuousInterpolation]:
                element.setEnabled(not is_running)

        button_map = {
            'run_sweep': self.btnRunSweep,
            'continuous_interpolation': self.btnContinuousInterpolation
        }

        if is_running:
            for btn_type, btn_widget in button_map.items():
                if btn_type == active_button_type:
                    btn_widget.setText("Cancel Sweep")
                    btn_widget.setStyleSheet("background-color: green; color: white;")
                    btn_widget.setEnabled(True)
                else:
                    btn_widget.setEnabled(False)
        else:
            self.btnRunSweep.setText("Run Sweep")
            self.btnContinuousInterpolation.setText("Continuous Interpolation")
            for btn_widget in button_map.values():
                btn_widget.setStyleSheet("")
                btn_widget.setEnabled(True)

    def update_plot(self):
        sweep_data = self.sweep_model.get_sweep_data()
        if sweep_data.empty:
            self.scatter.setData([], [])
            self.curve.setData([], [])
            return

        raw_freqs = sweep_data['frequency'].values
        raw_powers = sweep_data['power'].values
        
        plot_df = sweep_data.copy()
        plot_df['freq_group'] = (plot_df['frequency'] / 10).round() * 10
        averaged_data = plot_df.groupby('freq_group')['power'].mean().reset_index()
        
        line_freqs = averaged_data['freq_group'].values
        line_powers = averaged_data['power'].values

        sort_indices = np.argsort(line_freqs)
        line_freqs = line_freqs[sort_indices]
        line_powers = line_powers[sort_indices]

        self.log("Updating plot...")
        self.scatter.setData(raw_freqs, raw_powers)
        self.curve.setData(line_freqs, line_powers, pen=pg.mkPen(color='b', width=2), symbol=None)

    def save_config(self):
        config = {
            "start_freq": self.tbStartFreq.text(),
            "stop_freq": self.tbStopFreq.text(),
            "rbw": self.cbRBW.currentText(),
            "points": self.tbPoints.text(),
            "sa_freq_offset": self.tbSAFreqOffset.text(),
            "power": self.tbPower.text(),
            "sg_tracking_disabled": self.cbDisableTracking.isChecked(),
            "sg_manual_freq": self.tbSGFreq.text(),
            "sa_address": self.cbSAAddr.currentText(),
            "sg_address": self.cbSGAddr.currentText()
        }
        self.sweep_model.save_config(config)

    def load_config(self):
        config = self.sweep_model.load_config()
        self.tbStartFreq.setText(config.get("start_freq", "23.8GHz"))
        self.tbStopFreq.setText(config.get("stop_freq", "24.3GHz"))
        self.cbRBW.setCurrentText(config.get("rbw", "30Hz"))
        self.tbPoints.setText(config.get("points", "41"))
        self.tbSAFreqOffset.setText(config.get("sa_freq_offset", "0"))
        self.tbPower.setText(config.get("power", "-40"))
        self.cbDisableTracking.setChecked(config.get("sg_tracking_disabled", False))
        self.tbSGFreq.setText(config.get("sg_manual_freq", ""))
        self.last_sa_addr = config.get("sa_address", "")
        self.last_sg_addr = config.get("sg_address", "")
    
    def show_alignment(self):
        QMessageBox.about(self, "Alignment Procedure", "Unless SA and SG share a common oscillator, their frequencies will not match exactly and very likely will result in data that is garbage for sweeps with low RBW.\nWe can compensate for this mismatch in software by finding the difference between SA and SG frequencies and using this value to offset the SA frequency relative to the SG frequency.\n\nSteps:\n1) Connect devices.\n2) Disable SG tracking.\n3) Manually set SG to the center frequency of your desired sweep.\n\t*Note that the frequency must be set to something evenly divisible by your SG's smallest frequency step. (Ex. HP8673B has 4kHz steps so center freq should be divisible by 4kHz.\n4) Set start/stop frequencies to be just a bit wider than the anticipated frequency offset. +/-8kHz may be good to start with and adjust accordingly.\n5) Set number of sweep points. This will also vary case-by-base, but 40-60 points is usually good.\n6) Set RBW. Typically, #Points=(SweepRange/RBW)\n7) Perform sweep.\n8) Determine where the signal peak is and calculate the difference between the expected frequency and the measured frequency.\n9) Enter this value in the Analyzer Freq Offset box.")

    def show_about(self):
        QMessageBox.about(self, "About", "SweeperGUI\nCreated with PyQt5.")

    def closeEvent(self, event):
        self.save_config()
        self.device_manager.disconnect_devices()
        super().closeEvent(event)

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
