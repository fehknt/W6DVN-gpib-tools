import numpy as np
import pyqtgraph as pg
import pyvisa
import sys
import time
from datetime import datetime
from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel, QPushButton, QHBoxLayout, QVBoxLayout, QWidget, QPlainTextEdit, QComboBox, QLineEdit, QSizePolicy, QFrame, QCheckBox, QAction, QMessageBox
from devices.hp8593em import HP8593EM
from devices.hp8563a import HP8563A
from devices.hp8673b import HP8673B
from sweep_utils import parse_frequency, run_sweep, halton
from visa_utils import discover_and_connect

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
        self.btnDiscoverDevices.clicked.connect(self.discoverDevices)
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
            x=np.linspace(0,10,10),
            y=np.linspace(0,10,10),
            pen=pg.mkPen(None),
            brush=pg.mkBrush(255, 0, 0, 150),
            size=10,
            hoverable=True,
            tip='{x:.0f}Hz\n{y:.0f}dBm'.format,
            hoverPen=pg.mkPen('y', width=2),
            hoverBrush=pg.mkBrush('g')
        )

        # Default plot
        self.curve = self.plot_widget.plot(np.linspace(0, 10, 10),
                                           np.linspace(0, 10, 10),
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

        # Create button to run sweep
        self.btnRunSweep = QPushButton("Run Sweep", self)
        self.btnRunSweep.clicked.connect(self.runSweep)
        vlayout.addWidget(self.btnRunSweep)

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

        # Run initial discovery
        self.discoverDevices()

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

    def discoverDevices(self):
        self.log("Discovering devices...")
        self.rm = pyvisa.ResourceManager()
        found_devices = [r for r in self.rm.list_resources() if "GPIB" in r]
        self.log("Found GPIB devices: " + str(found_devices));

        self.cbSGAddr.clear()
        self.cbSAAddr.clear()
        self.cbSGAddr.addItems(found_devices)
        self.cbSAAddr.addItems(found_devices)
        self.log("Done discovering devices...")

    def connect_disconnect(self):
      if not self.connected:
        self.log("Connecting to devices...");

        try:
          if self.cbSpectrumAnalyzer.currentText() == "HP8563A":
            self.sa = HP8563A(self.rm.open_resource(self.cbSAAddr.currentText()))
            self.log("Spectrum Analyzer ID: " + self.sa.get_id())
            if "8563A" in self.sa.get_id():
              self.log("Verified connection to HP8563A.")
            else:
              self.log("Warning: Connected device does not identify as HP8563A.")
          elif self.cbSpectrumAnalyzer.currentText() == "HP8593EM":
            self.sa = HP8593EM(self.rm.open_resource(self.cbSAAddr.currentText()))
            self.log("Spectrum Analyzer ID: " + self.sa.get_id())
            if "8593EM" in self.sa.get_id():
              self.log("Verified connection to HP8593EM.")
            else:
              self.log("Warning: Connected device does not identify as HP8593EM.")
          else:
            self.log("Unsupported Spectrum Analyzer selected.")
            return

          if self.cbSignalGenerator.currentText() == "HP8673B":
            self.sg = HP8673B(self.rm.open_resource(self.cbSGAddr.currentText()))
            self.log("Signal Generator Init Freq: " + self.sg.get_frequency())
          else:
            self.log("Unsupported Signal Generator selected.")
            return

          self.connected = True;
          self.btnConnectDisconnect.setText("Disconnect Devices")
        except pyvisa.errors.VisaIOError:
          self.log("Error connecting to devices.");
          self.btnConnectDisconnect.setText("Connect Devices")
          self.connected = False;

      else:
        self.log("Disconnecting from devices...")
        try:
          self.sa.close()
          self.sg.enable_rf(False)
          self.sg.close()
          self.connected = False;
          self.log("Connections closed.")
        except:
          self.log("Error closing connections...")
        finally:
          self.btnConnectDisconnect.setText("Connect Devices")
  
    def runSweep(self):
      try:
        self.log("Configuring Spectrum Analyzer...")
        self.log("\t1 - Setting preset mode.")
        self.sa.set_preset_mode();
        time.sleep(1);
        self.log("\t2 - Setting single sweep mode.")
        self.sa.set_single_sweep_mode();
        time.sleep(0.5);
        self.log("\t3 - Setting zero span.")
        self.sa.set_zero_span();
        time.sleep(0.5);
        rbw = parse_frequency(self.cbRBW.currentText());
        self.log("\t4 - Setting resolution bandwidth to " + str(rbw) + "Hz.")
        self.sa.set_resolution_bandwidth(rbw);
        time.sleep(0.5);

        sgTrackingDisabled = self.cbDisableTracking.checkState() == 2
        sa_freq_offset = int(self.tbSAFreqOffset.text())
        self.log("Running sweep...")
        self.results = []

        start_freq = parse_frequency(self.tbStartFreq.text())
        end_freq = parse_frequency(self.tbStopFreq.text())
        
        if self.tbPoints.text():
          num_points = int(self.tbPoints.text())
          frequencies = np.linspace(start_freq, end_freq, num_points)
          self.log(f"Performing linear sweep with {num_points} points.")
        else:
          num_points = 1000  # Default for Halton
          self.log(f"Performing Halton sequence sweep with {num_points} points.")
          frequencies = [start_freq + (end_freq - start_freq) * halton(i, 2) for i in range(1, num_points + 1)]
          frequencies.insert(0, start_freq)
          frequencies.append(end_freq)

        # Setup devices
        self.sg.set_power(self.tbPower.text())
        self.sg.enable_rf(True)

        # Sweep
        measured_freqs = []
        measured_powers = []
        
        sweep_generator = run_sweep(self.sa, self.sg, frequencies, 
                                    sg_tracking_disabled=sgTrackingDisabled, 
                                    sa_freq_offset=sa_freq_offset, 
                                    log_callback=self.log)

        for freq, power in sweep_generator:
            self.results.append((freq, power))
            
            # Update plot
            measured_freqs.append(freq)
            measured_powers.append(power)

            try:
                self.curve.setData(measured_freqs, measured_powers, pen=pg.mkPen(color='b', width=2))
                self.scatter.setData(measured_freqs, measured_powers, pen=pg.mkPen(color='b', width=2))
            except Exception as e:
                print(f"Error updating plot: {e}")

        self.sg.enable_rf(False)
        self.log("Sweep finished.")

      except Exception as e:
        self.log(f"Error running sweep: {e}")


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

