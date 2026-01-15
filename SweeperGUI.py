import numpy as np
import pyqtgraph as pg
import pyvisa
import sys
import time
from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel, QPushButton, QHBoxLayout, QVBoxLayout, QWidget, QPlainTextEdit, QComboBox, QLineEdit, QSizePolicy, QFrame, QCheckBox
from hp8593em import HP8593EM
from devices.hp8563a import HP8563A
from hp8673b import HP8673B
from visa_utils import discover_and_connect

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("SweeperGUI")
        self.setGeometry(100, 100, 800, 500) # x, y, width, height

        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        vlayout = QVBoxLayout()
        central_widget.setLayout(vlayout)

        # Create status label
        self.lblStatus= QLabel("Not connected", self)
        vlayout.addWidget(self.lblStatus)

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
        self.cbSpectrumAnalyzer.addItems(["HP8563A"]);
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

        # Create line divider
        self.line = QFrame()
        self.line.setFrameShape(QFrame.HLine)
        self.line.setFrameShadow(QFrame.Sunken)
        vlayout.addWidget(self.line)

        # Create PyQtGraph plot widget
        self.plot_widget = pg.PlotWidget()
        vlayout.addWidget(self.plot_widget)

        # Configure plot
        self.plot_widget.setBackground('w')  # White background
        self.plot_widget.setLabel('left', 'Amplitude (dBm)')
        self.plot_widget.setLabel('bottom', 'Frequency', units='Hz')
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
        self.line = QFrame()
        self.line.setFrameShape(QFrame.HLine)
        self.line.setFrameShadow(QFrame.Sunken)
        vlayout.addWidget(self.line)

        # Create input text box for start frequency
        hlayout = QHBoxLayout()
        vlayout.addLayout(hlayout)
        self.lblStartFreq = QLabel("Start Freq: ", self)
        hlayout.addWidget(self.lblStartFreq)
        self.tbStartFreq = QLineEdit("3000000kHz")
        hlayout.addWidget(self.tbStartFreq)

        # Create input text box for stop frequency
        self.lblStopFreq = QLabel("Stop Freq: ", self)
        hlayout.addWidget(self.lblStopFreq)
        self.tbStopFreq = QLineEdit("3000020kHz")
        hlayout.addWidget(self.tbStopFreq)

        # Create input text box for points
        self.lblPoints = QLabel("Points: ", self)
        hlayout.addWidget(self.lblPoints)
        self.tbPoints = QLineEdit("21")
        hlayout.addWidget(self.tbPoints)

        # Create input text box for calibration offset
        self.lblSAFreqOffset = QLabel("Analyzer Freq Offset (Hz): ", self)
        hlayout.addWidget(self.lblSAFreqOffset)
        self.tbSAFreqOffset = QLineEdit("3250")
        hlayout.addWidget(self.tbSAFreqOffset)

        # Create combo box for RBW
        self.lblRBW = QLabel("RBW: ", self)
        hlayout.addWidget(self.lblRBW)
        self.cbRBW = QComboBox()
        self.cbRBW.addItems(["300Hz", "1kHz", "3kHz", "10kHz", "30kHz", "100kHz", "300kHz", "1MHz", "2MHz"]);
        hlayout.addWidget(self.cbRBW)

        # Create checkbox to disable signal generator tracking
        hlayout = QHBoxLayout()
        vlayout.addLayout(hlayout)
        self.cbDisableTracking = QCheckBox("Disable signal generator tracking");
        self.cbDisableTracking.setChecked(False);
        hlayout.addWidget(self.cbDisableTracking);

        # Create input text box for manual SigGen frequency
        self.tbSGFreq = QLineEdit("24721000000")
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

    def log(self, message):
        self.tbLog.appendPlainText(message)

    def updateSGFreq(self):
        self.sg.set_frequency(self.tbSGFreq.text());

    def discoverDevices(self):
        self.lblStatus.setText("Discovering devices...")
        self.rm = pyvisa.ResourceManager()
        found_devices = [r for r in self.rm.list_resources() if r.startswith("GPIB")]
        self.log("Found GPIB devices: " + str(found_devices));

        self.cbSGAddr.clear()
        self.cbSAAddr.clear()
        self.cbSGAddr.addItems(found_devices)
        self.cbSAAddr.addItems(found_devices)
        self.lblStatus.setText("Done discovering devices...")

    def connect_disconnect(self):
      if not self.connected:
        self.lblStatus.setText("Connecting to devices...")
        self.log("Connecting to devices...");

        try:
          self.sa = HP8563A(self.rm.open_resource(self.cbSAAddr.currentText()))
          self.sa.set_single_sweep_mode();
          self.log("Spectrum Analyzer ID: " + self.sa.get_id())

          self.sg = HP8673B(self.rm.open_resource(self.cbSGAddr.currentText()))
          self.log("Signal Generator Init Freq: " + self.sg.get_frequency())

          self.connected = True;
          self.btnConnectDisconnect.setText("Disconnect Devices")
        except pyvisa.errors.VisaIOError:
          self.btnConnectDisconnect.setText("Connect Devices")
          self.lblStatus.setText("Connections closed.")
          self.log("Error connecting to devices.");
          self.log("Connections closed.")
          self.sa.close()
          self.sg.close()
          self.connected = False;

      else:
        self.lblStatus.setText("Disconnecting from devices...")
        self.log("Disconnecting from devices...")
        try:
          self.sa.close()
          #self.sg.enable_rf(False)
          self.sg.close()
          self.connected = False;
        finally:
          self.btnConnectDisconnect.setText("Connect Devices")
          self.lblStatus.setText("Connections closed.")
          self.log("Connections closed.")
  
    def runSweep(self):
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
      sweep_time = "50ms";
      self.log("\t5 - Setting sweep time to " + str(sweep_time))
      self.sa.set_sweep_time(sweep_time);
      time.sleep(0.5);

      sgTrackingDisabled = True if self.cbDisableTracking.checkState() == 2 else False;
      self.lblStatus.setText("Running sweep...")
      self.results = []
      try:
        start_freq = parse_frequency(self.tbStartFreq.text())
        end_freq = parse_frequency(self.tbStopFreq.text())
        
        # Set plot limits based on frequency range
        #ax.set_xlim(start_freq / 1e6, end_freq / 1e6)
        
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
        #self.sg.set_power(0)
        #self.sg.enable_rf(True)

        # Sweep
        measured_freqs = []
        measured_powers = []
        start_time = time.time()
        for freq in frequencies:
          if not sgTrackingDisabled:
            self.log("Setting SG freq: " + str(freq))
            self.sg.set_frequency(freq + int(self.tbSAFreqOffset.text()))
          saFreq = freq + int(self.tbSAFreqOffset.text());
          self.log(f"Measuring SA (with offset) at {saFreq}Hz...")
          self.sa.set_center_frequency(saFreq)

          self.sa.take_sweep()
          self.sa.wait_done()

          # Wait for sweep to complete, with a small buffer
          #time.sleep(sweep_time)

          power = self.sa.get_marker_power()
          self.results.append((freq, power))
          self.log(f"  Power: {power:.2f} dBm")

          # Update plot
          measured_freqs.append(freq)
          measured_powers.append(power)

          # Plot curve
          try:
            self.curve.setData(measured_freqs, measured_powers, pen=pg.mkPen(color='b', width=2))
            self.scatter.setData(measured_freqs, measured_powers, pen=pg.mkPen(color='b', width=2))
          except Exception as e:
            print(f"Error updating plot: {e}")

        stop_time = time.time()
        self.lblStatus.setText("Done running sweep. Sweep took " + str(int(stop_time-start_time)) + " seconds.")

      except:
        self.lblStatus.setText("Error running sweep.")
        self.log(f"Error running sweep.")

def parse_frequency(freq_str: str) -> float:
    """Parses a frequency string with units (e.g., '100mhz', '2.4ghz') into Hz."""
    freq_str = freq_str.lower().strip()
    multiplier = 1
    if freq_str.endswith('ghz'):
        multiplier = 1e9
        freq_str = freq_str[:-3]
    elif freq_str.endswith('mhz'):
        multiplier = 1e6
        freq_str = freq_str[:-3]
    elif freq_str.endswith('khz'):
        multiplier = 1e3
        freq_str = freq_str[:-3]
    elif freq_str.endswith('hz'):
        freq_str = freq_str[:-2]
    
    return float(freq_str) * multiplier

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

