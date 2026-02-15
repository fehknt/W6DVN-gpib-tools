import pyvisa
from PyQt5.QtCore import QObject, pyqtSignal
from device_factory import create_spectrum_analyzer
from devices.hp8673b import HP8673B

class DeviceManager(QObject):
    log = pyqtSignal(str)
    devices_discovered = pyqtSignal(list)
    connection_status_changed = pyqtSignal(bool, str, str) # connected, sa_id, sg_id

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rm = pyvisa.ResourceManager()
        self.sa = None
        self.sg = None
        self.connected = False

    def discover_devices(self):
        self.log.emit("Discovering devices...")
        try:
            # On some systems, finding the resource can be slow, so we need to be patient
            found_devices = [r for r in self.rm.list_resources() if "GPIB" in r]
            self.log.emit(f"Found GPIB devices: {found_devices}")
            self.devices_discovered.emit(found_devices)
            return found_devices
        except Exception as e:
            self.log.emit(f"Error discovering devices: {e}")
            self.devices_discovered.emit([])
            return []

    def connect_devices(self, sa_addr, sg_addr, sa_model_name, sg_model_name):
        if self.connected:
            self.disconnect_devices()

        self.log.emit(f"Connecting to SA at {sa_addr} and SG at {sg_addr}...")
        try:
            sa_resource = self.rm.open_resource(sa_addr)
            self.sa = create_spectrum_analyzer(sa_resource, log_callback=self.log.emit)

            if not self.sa:
                self.log.emit(f"Error: Could not connect to a supported SA at {sa_addr}")
                sa_resource.close()
                self.connection_status_changed.emit(False, "", "")
                return

            sg_resource = self.rm.open_resource(sg_addr)
            if sg_model_name == "HP8673B":
                self.sg = HP8673B(sg_resource)
            else:
                self.log.emit(f"Unsupported Signal Generator: {sg_model_name}")
                self.sa.close()
                self.sa = None
                self.connection_status_changed.emit(False, "", "")
                return

            self.connected = True
            sa_id = self.sa.get_id()
            sg_id = self.sg.get_id()
            self.log.emit(f"Connected to SA: {sa_id} and SG: {sg_id}")
            self.connection_status_changed.emit(True, sa_id, sg_id)

        except pyvisa.errors.VisaIOError as e:
            self.log.emit(f"Error connecting to devices: {e}")
            if self.sa:
                self.sa.close()
            if self.sg:
                self.sg.close()
            self.sa = None
            self.sg = None
            self.connected = False
            self.connection_status_changed.emit(False, "", "")

    def disconnect_devices(self):
        self.log.emit("Disconnecting from devices...")
        try:
            if self.sa:
                self.sa.close()
            if self.sg:
                self.sg.enable_rf(False)
                self.sg.close()
            self.log.emit("Connections closed.")
        except Exception as e:
            self.log.emit(f"Error closing connections: {e}")
        finally:
            self.sa = None
            self.sg = None
            self.connected = False
            self.connection_status_changed.emit(False, "", "")
