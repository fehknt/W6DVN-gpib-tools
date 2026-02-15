import pandas as pd
import json
import os
import numpy as np
import pyqtgraph as pg
import pyvisa
import sys
import time
from datetime import datetime
from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel, QPushButton, QHBoxLayout, QVBoxLayout, QWidget, QPlainTextEdit, QComboBox, QLineEdit, QSizePolicy, QFrame, QCheckBox, QAction, QMessageBox
from PyQt5.QtCore import QThread, QObject, pyqtSignal
from devices.hp8593em import HP8593EM
from devices.hp8563a import HP8563A
from device_factory import create_spectrum_analyzer
from devices.hp8673b import HP8673B
from sweep_utils import parse_frequency, run_sweep, halton

CONFIG_FILE = "config.json"


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


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("SweeperGUI")
        self.setGeometry(100, 100, 800, 500) # x, y, width, height

        self.init_menu();

        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        vlayout = QVBoxLayout()
        central_widget.setLayout(vlayout)

        # Create section label
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

        # Create more containers for the next few widgets
        hlayout = QHBoxLayout()
        vlayout.addLayout(hlayout)
        vlayout2 = QVBoxLayout()
        hlayout.addLayout(vlayout2)

        # Create selection for Signal Generator
        hlayout2 = QHBoxLayout()
        vlayout2.addLayout(hlayout2)
        self.lblSignalGenerator = QLabel("Select Signal Generator: ", self)
        hlayout2.addWidget(self.lblSignalGenerator)
        self.cbSignalGenerator = QComboBox()
        self.cbSignalGenerator.addItems(["HP8673B"]);
        hlayout2.addWidget(self.cbSignalGenerator)
        self.cbSGAddr = QComboBox()
        hlayout2.addWidget(self.cbSGAddr);

        # Create selection for Spectrum Analyzer
        hlayout3 = QHBoxLayout()
        vlayout2.addLayout(hlayout3)
        self.lblSpectrumAnalyzer = QLabel("Select Spectrum Analyzer: ", self)
        hlayout3.addWidget(self.lblSpectrumAnalyzer)
        self.cbSpectrumAnalyzer = QComboBox()
        self.cbSpectrumAnalyzer.addItems(["HP8563A", "HP8593EM"]);
        hlayout3.addWidget(self.cbSpectrumAnalyzer)
        self.cbSAAddr = QComboBox()
        hlayout3.addWidget(self.cbSAAddr)

        # Create button to discover devices
        self.btnDiscoverDevices = QPushButton("Refresh Device List", self)
        self.btnDiscoverDevices.clicked.connect(self.auto_connect_devices)
        self.btnDiscoverDevices.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        hlayout.addWidget(self.btnDiscoverDevices)

        # Create button to connect/disconnect devices
        self.btnConnectDisconnect = QPushButton("Connect Devices", self)
        self.btnConnectDisconnect.clicked.connect(self.connect_disconnect)
        vlayout.addWidget(self.btnConnectDisconnect)

        # Create section label
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

        # Create PyQtGraph plot widget
        hlayout = QHBoxLayout()
        vlayout.addLayout(hlayout)
        self.plot_widget = pg.PlotWidget()
        hlayout.addWidget(self.plot_widget)
#        hlayout.setContentsMargins(10, 10, 10, 10)  # left, top, right, bottom
#        hlayout.setSpacing(10)

        # Configure plot
        self.plot_widget.setBackground('w')  # White background
        self.plot_widget.setLabel('left', 'Amplitude (dBm)')
        self.plot_widget.setLabel('bottom', 'Frequency', units='Hz')
        self.plot_widget.setStyleSheet("""
          border: 1px solid grey;
          border-radius: 3px;
          background-color: white;
        """)
        self.plot_widget.showGrid(x=True, y=True)

        # Create a scatter plot with hover enabled
        self.scatter = pg.ScatterPlotItem(
            x=[],
            y=[],
            pen=pg.mkPen(None),
            brush=pg.mkBrush(255, 0, 0, 150),
            size=10,
            hoverable=True,
            tip='{x:.0f}Hz\n{y:.0f}dBm'.format,
            hoverPen=pg.mkPen('y', width=2),
            hoverBrush=pg.mkBrush('g')
        )

        # Default plot
        self.curve = self.plot_widget.plot([],
                                           [],
                                           pen=pg.mkPen(color='gray', width=1),
                                           symbol='o',
                                           symbolSize=8,
                                           symbolBrush=(0,0,255),
                                           symbolPen='k'
                                          )

        # Add scatter to plot
        self.plot_widget.addItem(self.scatter)

        # Create line divider
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

        # Create input text box for start frequency
        hlayout = QHBoxLayout()
        vlayout.addLayout(hlayout)
        self.lblStartFreq = QLabel("Start Freq: ", self)
        hlayout.addWidget(self.lblStartFreq)
        self.tbStartFreq = QLineEdit("23800000kHz")
        hlayout.addWidget(self.tbStartFreq)

        # Create input text box for stop frequency
        self.lblStopFreq = QLabel("Stop Freq: ", self)
        hlayout.addWidget(self.lblStopFreq)
        self.tbStopFreq = QLineEdit("24300000kHz")
        hlayout.addWidget(self.tbStopFreq)

        # Create combo box for RBW
        self.lblRBW = QLabel("RBW: ", self)
        hlayout.addWidget(self.lblRBW)
        self.cbRBW = QComboBox()
        self.cbRBW.addItems(["30Hz", "100Hz", "300Hz", "1kHz", "3kHz", "10kHz", "30kHz", "100kHz", "300kHz", "1MHz", "2MHz"]);
        hlayout.addWidget(self.cbRBW)

        # Create input text box for points
        self.lblPoints = QLabel("Points: ", self)
        hlayout.addWidget(self.lblPoints)
        self.tbPoints = QLineEdit("41")
        hlayout.addWidget(self.tbPoints)

        # Create input text box for calibration offset
        self.lblSAFreqOffset = QLabel("Analyzer Freq Offset (Hz): ", self)
        hlayout.addWidget(self.lblSAFreqOffset)
        self.tbSAFreqOffset = QLineEdit("0")
        hlayout.addWidget(self.tbSAFreqOffset)

        # Create input text box for power 
        hlayout = QHBoxLayout()
        vlayout.addLayout(hlayout)
        self.lblPower = QLabel("Power (dBm): ", self)
        hlayout.addWidget(self.lblPower)
        self.tbPower = QLineEdit("-40")
        hlayout.addWidget(self.tbPower)

        # Create checkbox to disable signal generator tracking
        self.cbDisableTracking = QCheckBox("Disable signal generator tracking");
        self.cbDisableTracking.setChecked(False);
        hlayout.addWidget(self.cbDisableTracking);

        # Create input text box for manual SigGen frequency
        self.tbSGFreq = QLineEdit("24192000000")
        hlayout.addWidget(self.tbSGFreq)
        self.btnSetSGFreq = QPushButton("Set SG Freq", self)
        self.btnSetSGFreq.clicked.connect(self.updateSGFreq)
        hlayout.addWidget(self.btnSetSGFreq)

        # Create a layout for the sweep buttons
        sweep_button_layout = QHBoxLayout()
        self.btnRunSweep = QPushButton("Run New Sweep", self)
        self.btnRunSweep.clicked.connect(self.handle_sweep_button_click)
        sweep_button_layout.addWidget(self.btnRunSweep)

        self.btnAppendSweep = QPushButton("Append Sweep", self)
        self.btnAppendSweep.clicked.connect(self.handle_sweep_button_click)
        sweep_button_layout.addWidget(self.btnAppendSweep)

        self.btnContinuousInterpolation = QPushButton("Continuous Interpolation", self)
        self.btnContinuousInterpolation.clicked.connect(self.handle_sweep_button_click)
        sweep_button_layout.addWidget(self.btnContinuousInterpolation)
        
        vlayout.addLayout(sweep_button_layout)

        # Create log text box
        self.tbLog = QPlainTextEdit()
        self.tbLog.setReadOnly(True)
        self.tbLog.setMaximumBlockCount(1000)
        vlayout.addWidget(self.tbLog)

        # Objects for spectrum analyzer device and signal generator device
        self.connected = False;
        self.rm = None
        self.sa = None
        self.sg = None
        self.last_sa_addr = None
        self.last_sg_addr = None
        self.sweep_data = pd.DataFrame(columns=['frequency', 'power'])
        self.sweep_thread = None
        self.sweep_worker = None
        self.active_sweep_button = None

        self.ui_elements_to_disable = [
            self.cbSignalGenerator, self.cbSGAddr,
            self.cbSpectrumAnalyzer, self.cbSAAddr,
            self.btnDiscoverDevices, self.btnConnectDisconnect,
            self.tbStartFreq, self.tbStopFreq, self.cbRBW,
            self.tbPoints, self.tbSAFreqOffset, self.tbPower,
            self.cbDisableTracking, self.tbSGFreq, self.btnSetSGFreq,
            self.btnRunSweep, self.btnAppendSweep, self.btnContinuousInterpolation
        ]

        # Load previous settings and then run initial discovery
        self.load_config()
        self.auto_connect_devices()

    def init_menu(self):
        # Create the menu bar
        menu_bar = self.menuBar()

        # Apply style sheet to menu bar
#        menu_bar.setStyleSheet("""
#            QMenuBar {
#                background-color: white;   /* Dark blue background */
#                color: black;                /* White text */
#                border: 1px solid black;   /* Border around menu bar */
#            }
#            QMenuBar::item {
#                background-color: transparent;
#                padding: 4px 10px;
#            }
#            QMenuBar::item:selected {
#                background-color: #34495e;   /* Hover color */
#            }
#            QMenu {
#                background-color: #34495e;   /* Menu background */
#                color: white;                /* Menu text color */
#            }
#            QMenu::item:selected {
#                background-color: #1abc9c;   /* Selected item color */
#            }
#        """)

        # ===== File Menu =====
        file_menu = menu_bar.addMenu("File")

        # Open Action
        #open_action = QAction("Open...", self)
        #open_action.setStatusTip("Open an existing file")
        #open_action.triggered.connect(self.open_file)
        #file_menu.addAction(open_action)

        # Exit Action
        exit_action = QAction("Exit", self)
        exit_action.setStatusTip("Exit the application")
        exit_action.triggered.connect(self.close_app)
        file_menu.addAction(exit_action)

        # ===== Instructions Menu =====
        instruction_menu = menu_bar.addMenu("Instructions")

        alignment_action = QAction("Alignment Procedure", self)
        alignment_action.setStatusTip("How to align SA and SG frequencies in software")
        alignment_action.triggered.connect(self.show_alignment)
        instruction_menu.addAction(alignment_action)

        # ===== Help Menu =====
        help_menu = menu_bar.addMenu("Help")

        about_action = QAction("About", self)
        about_action.setStatusTip("About this application")
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def open_file(self):
        try:
            file_path, _ = QFileDialog.getOpenFileName(self, "Open File", "", "All Files (*.*)")
            if file_path:
                QMessageBox.information(self, "File Opened", f"Opened file:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open file:\n{str(e)}")

    def close_app(self):
        self.close()

    def show_alignment(self):
        QMessageBox.about(self, "Alignment Procedure", "Unless SA and SG share a common oscillator, their frequencies will not match exactly and very likely will result in data that is garbage for sweeps with low RBW.\nWe can compensate for this mismatch in software by finding the difference between SA and SG frequencies and using this value to offset the SA frequency relative to the SG frequency.\n\nSteps:\n1) Connect devices.\n2) Disable SG tracking.\n3) Manually set SG to the center frequency of your desired sweep.\n\t*Note that the frequency must be set to something evenly divisible by your SG's smallest frequency step. (Ex. HP8673B has 4kHz steps so center freq should be divisible by 4kHz.\n4) Set start/stop frequencies to be just a bit wider than the anticipated frequency offset. +/-8kHz may be good to start with and adjust accordingly.\n5) Set number of sweep points. This will also vary case-by-base, but 40-60 points is usually good.\n6) Set RBW. Typically, #Points=(SweepRange/RBW)\n7) Perform sweep.\n8) Determine where the signal peak is and calculate the difference between the expected frequency and the measured frequency.\n9) Enter this value in the Analyzer Freq Offset box.")

    def show_about(self):
        QMessageBox.about(self, "About", "PyQt Menu Bar Example\nCreated with PyQt5.")

    def log(self, message):
        self.tbLog.appendPlainText(datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3] + "\t" + message)
        #self.tbLog.verticalScrollBar().setValue(self.log.verticalScrollBar().maximum())  # Auto-scroll
        self.tbLog.repaint()  # Force immediate redraw of just this widget
        #QApplication.processEvents(QEventLoop.ExcludeUserInputEvents)  # Process paint events only

    def updateSGFreq(self):
        self.sg.set_frequency(self.tbSGFreq.text());

    def auto_connect_devices(self):
        self.log("Discovering devices...")
        if self.connected:
            self.connect_disconnect() # Disconnect first if already connected
        
        self.rm = pyvisa.ResourceManager()
        found_devices = [r for r in self.rm.list_resources() if "GPIB" in r]
        self.log(f"Found GPIB devices: {found_devices}")

        # Populate device lists
        self.cbSGAddr.clear()
        self.cbSAAddr.clear()
        self.cbSGAddr.addItems(found_devices)
        self.cbSAAddr.addItems(found_devices)

        # Restore last used addresses if they are present
        if self.last_sa_addr and self.last_sa_addr in found_devices:
            self.cbSAAddr.setCurrentText(self.last_sa_addr)
        if self.last_sg_addr and self.last_sg_addr in found_devices:
            self.cbSGAddr.setCurrentText(self.last_sg_addr)

        # Attempt auto-connection if exactly two devices are found
        if len(found_devices) == 2:
            self.log("Two devices found, attempting auto-connection...")
            
            sa_addr, sg_addr = (found_devices[0], found_devices[1]) if "18" in found_devices[0] else (found_devices[1], found_devices[0])
            
            if "18" not in sa_addr:
                self.log("Could not identify SA by address '18'. Please connect manually.")
                return

            try:
                sa_resource = self.rm.open_resource(sa_addr)
                self.sa = create_spectrum_analyzer(sa_resource, log_callback=self.log)

                if self.sa:
                    sg_resource = self.rm.open_resource(sg_addr)
                    self.sg = HP8673B(sg_resource) # Assume the other is the SG
                    self.log(f"Auto-connected to SA: {self.sa.get_id()} and assumed SG at {sg_addr}")

                    self.connected = True
                    self.btnConnectDisconnect.setText("Disconnect Devices")
                    
                    # Update UI
                    self.cbSAAddr.setCurrentText(sa_addr)
                    self.cbSGAddr.setCurrentText(sg_addr)
                    sa_model = self.sa.__class__.__name__
                    self.cbSpectrumAnalyzer.setCurrentText(sa_model)
                    return

                else:
                    self.log("Auto-connection failed: Could not identify SA.")
                    if sa_resource: sa_resource.close()

            except Exception as e:
                self.log(f"Error during auto-connection: {e}")
        
        self.log("Auto-connection not performed. Please select devices manually.")

    def connect_disconnect(self):
      if not self.connected:
        self.log("Connecting to devices manually...");
        try:
          sa_addr = self.cbSAAddr.currentText()
          sg_addr = self.cbSGAddr.currentText()
          
          if not sa_addr or not sg_addr:
              self.log("Error: Please select both an SA and SG address.")
              return

          sa_resource = self.rm.open_resource(sa_addr)
          self.sa = create_spectrum_analyzer(sa_resource, log_callback=self.log)

          if not self.sa:
              self.log(f"Error: Could not connect to a supported SA at {sa_addr}")
              sa_resource.close()
              return

          # Manual SG connection
          sg_resource = None
          if self.cbSignalGenerator.currentText() == "HP8673B":
              sg_resource = self.rm.open_resource(sg_addr)
              self.sg = HP8673B(sg_resource)
          else:
              self.log("Unsupported Signal Generator selected.")
              self.sa.close()
              return
          
          self.log(f"Connected to SA: {self.sa.get_id()} and SG.")
          self.connected = True
          self.btnConnectDisconnect.setText("Disconnect Devices")

        except pyvisa.errors.VisaIOError as e:
          self.log(f"Error connecting to devices: {e}");
          self.btnConnectDisconnect.setText("Connect Devices")
          self.connected = False

      else:
        self.log("Disconnecting from devices...")
        try:
          if self.sa: self.sa.close()
          if self.sg: self.sg.enable_rf(False); self.sg.close()
          self.connected = False
          self.log("Connections closed.")
        except Exception as e:
          self.log(f"Error closing connections: {e}")
        finally:
          self.btnConnectDisconnect.setText("Connect Devices")
  
    def handle_sweep_button_click(self):
        sender = self.sender()
        if self.sweep_thread and self.sweep_thread.isRunning():
            # The click must have come from the active cancel button
            self.cancel_sweep()
            return

        if not self.connected:
            self.log("Cannot start sweep: Devices are not connected.")
            return

        self.active_sweep_button = sender # Set the active button
        frequencies = []
        sweep_type = "sweep"

        try:
            if sender == self.btnRunSweep:
                sweep_type = "new"
                if not self.sweep_data.empty:
                    reply = QMessageBox.question(self, 'Clear Data',
                                                 "This will clear all existing sweep data. Are you sure?",
                                                 QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                    if reply == QMessageBox.No:
                        self.active_sweep_button = None # Reset if user cancels
                        return
                self.log("Starting new sweep and clearing existing data.")
                self.sweep_data = pd.DataFrame(columns=['frequency', 'power'])
                self.update_plot()
                
                start_freq = parse_frequency(self.tbStartFreq.text())
                end_freq = parse_frequency(self.tbStopFreq.text())
                num_points = int(self.tbPoints.text()) if self.tbPoints.text() else 41
                frequencies = np.linspace(start_freq, end_freq, num_points)

            elif sender == self.btnAppendSweep:
                sweep_type = "append"
                self.log("Appending sweep with current settings.")
                start_freq = parse_frequency(self.tbStartFreq.text())
                end_freq = parse_frequency(self.tbStopFreq.text())
                num_points = int(self.tbPoints.text()) if self.tbPoints.text() else 41
                frequencies = np.linspace(start_freq, end_freq, num_points)
                self._start_sweep_thread(frequencies, sweep_type)

            elif sender == self.btnContinuousInterpolation:
                sweep_type = "continuous"
                start_freq = parse_frequency(self.tbStartFreq.text())
                end_freq = parse_frequency(self.tbStopFreq.text())

                if self.sweep_data.empty or len(self.sweep_data['frequency'].unique()) < 2:
                    self.log("Not enough data to perform continuous interpolation. Running a new sweep first might be needed.")
                
                self.log("Starting continuous interpolation sweep.")
                self._start_sweep_thread([], sweep_type, mode='continuous', initial_data=self.sweep_data, 
                                         start_freq=start_freq, stop_freq=end_freq)

        except Exception as e:
            self.log(f"Invalid sweep parameter: {e}")
            self.active_sweep_button = None # Reset
            return
        
    def _start_sweep_thread(self, frequencies, sweep_type, mode='finite', initial_data=None, start_freq=None, stop_freq=None):
        """Helper function to create and start the sweep worker thread."""
        self.log(f"Starting {sweep_type} sweep.")
        
        try:
            rbw = parse_frequency(self.cbRBW.currentText())
            power = self.tbPower.text()
            sg_tracking_disabled = self.cbDisableTracking.isChecked()
            sa_freq_offset = int(self.tbSAFreqOffset.text())
        except Exception as e:
            self.log(f"Invalid sweep parameter: {e}")
            self.active_sweep_button = None # Reset
            return

        self.set_ui_for_sweep(is_running=True)

        self.sweep_thread = QThread()
        self.sweep_worker = SweepWorker(self.sa, self.sg, frequencies, sg_tracking_disabled,
                                        sa_freq_offset, power, rbw, mode=mode, initial_data=initial_data,
                                        start_freq=start_freq, stop_freq=stop_freq)
        self.sweep_worker.moveToThread(self.sweep_thread)

        self.sweep_thread.started.connect(self.sweep_worker.run)
        self.sweep_worker.finished.connect(self.on_sweep_finished)
        self.sweep_worker.progress.connect(self.update_sweep_progress)
        self.sweep_worker.error.connect(self.log)
        self.sweep_worker.log.connect(self.log)
        
        self.sweep_worker.finished.connect(self.sweep_thread.quit)
        self.sweep_worker.finished.connect(self.sweep_worker.deleteLater)
        self.sweep_thread.finished.connect(self.sweep_thread.deleteLater)
        self.sweep_thread.finished.connect(self._on_thread_finished)

        self.sweep_thread.start()

    def cancel_sweep(self):
        self.log("Attempting to cancel sweep...")
        if self.sweep_worker:
            self.sweep_worker.stop()

    def on_sweep_finished(self):
        """This slot is connected to the SweepWorker's finished signal."""
        self.log("Sweep has finished or was cancelled. Cleaning up UI.")
        self.set_ui_for_sweep(is_running=False)
        self.update_plot()
    
    def _on_thread_finished(self):
        """This slot is connected to the QThread's finished signal."""
        self.log("Sweep thread has finished.")
        self.sweep_thread = None
        self.sweep_worker = None

    def update_sweep_progress(self, freq, power):
        new_data = pd.DataFrame([{'frequency': freq, 'power': power}])
        if self.sweep_data.empty:
            self.sweep_data = new_data
        else:
            self.sweep_data = pd.concat([self.sweep_data, new_data], ignore_index=True)
        
        # For performance, only update the plot periodically or at the end
        if len(self.sweep_data) % 5 == 0 or len(self.sweep_data) < 5:
             self.update_plot()

    def set_ui_for_sweep(self, is_running):
        """Enable or disable UI elements based on sweep status."""
        # Disable all regular input elements first
        for element in self.ui_elements_to_disable:
            if element not in [self.btnRunSweep, self.btnAppendSweep, self.btnContinuousInterpolation]:
                element.setEnabled(not is_running)

        if is_running:
            # Disable all sweep buttons, then enable and modify the active one
            for btn in [self.btnRunSweep, self.btnAppendSweep, self.btnContinuousInterpolation]:
                btn.setEnabled(False)  # Disable first
                if btn == self.active_sweep_button:
                    btn.setText("Cancel Sweep")
                    btn.setStyleSheet("background-color: green; color: white;")
                    btn.setEnabled(True)  # Re-enable so it can be clicked
        else:
            # Restore all buttons to their normal state
            self.btnRunSweep.setText("Run New Sweep")
            self.btnAppendSweep.setText("Append Sweep")
            self.btnContinuousInterpolation.setText("Continuous Interpolation")

            for btn in [self.btnRunSweep, self.btnAppendSweep, self.btnContinuousInterpolation]:
                btn.setStyleSheet("")
                btn.setEnabled(True)
            
            self.active_sweep_button = None

    def update_plot(self):
        if self.sweep_data.empty:
            self.scatter.setData([], [])
            self.curve.setData([], [])
            return

        # Raw data for scatter plot
        raw_freqs = self.sweep_data['frequency'].values
        raw_powers = self.sweep_data['power'].values
        
        # Create a temporary copy for grouping and averaging
        plot_df = self.sweep_data.copy()
        
        # Group by frequency and average for the line plot
        # Round to nearest 10Hz to group close points
        plot_df['freq_group'] = (plot_df['frequency'] / 10).round() * 10
        averaged_data = plot_df.groupby('freq_group')['power'].mean().reset_index()
        
        line_freqs = averaged_data['freq_group'].values
        line_powers = averaged_data['power'].values

        # Sort line data for correct plotting
        sort_indices = np.argsort(line_freqs)
        line_freqs = line_freqs[sort_indices]
        line_powers = line_powers[sort_indices]

        self.log("Updating plot...")
        self.scatter.setData(raw_freqs, raw_powers)
        self.curve.setData(line_freqs, line_powers, pen=pg.mkPen(color='b', width=2), symbol=None)


    def save_config(self):
        """Saves the current UI settings to a config file."""
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
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(config, f, indent=4)
            self.log("Configuration saved.")
        except Exception as e:
            self.log(f"Error saving configuration: {e}")

    def load_config(self):
        """Loads UI settings from a config file."""
        if not os.path.exists(CONFIG_FILE):
            self.log("No config file found.")
            return
        
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
            
            self.tbStartFreq.setText(config.get("start_freq", ""))
            self.tbStopFreq.setText(config.get("stop_freq", ""))
            self.cbRBW.setCurrentText(config.get("rbw", "30Hz"))
            self.tbPoints.setText(config.get("points", "41"))
            self.tbSAFreqOffset.setText(config.get("sa_freq_offset", "0"))
            self.tbPower.setText(config.get("power", "-40"))
            self.cbDisableTracking.setChecked(config.get("sg_tracking_disabled", False))
            self.tbSGFreq.setText(config.get("sg_manual_freq", ""))
            
            # Store addresses to be used after device discovery
            self.last_sa_addr = config.get("sa_address", "")
            self.last_sg_addr = config.get("sg_address", "")

            self.log("Configuration loaded.")
        except Exception as e:
            self.log(f"Error loading configuration: {e}")

    def closeEvent(self, event):
        """Handle the window's close event."""
        self.save_config()
        super().closeEvent(event)


def main():
    """
    Main function to start the GUI.
    """

    # Every PyQt5 application must create a QApplication object
    app = QApplication(sys.argv)

    # Create the main window instance
    window = MainWindow()
    window.show() # Make the window visible

    # Start the application event loop
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()

