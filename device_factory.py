import pyvisa
from devices.hp8563a import HP8563A
from devices.hp8593em import HP8593EM
from devices.hp8673b import HP8673B

def create_spectrum_analyzer(resource, log_callback=print):
    """
    Factory function to create a spectrum analyzer instance based on its ID.

    Args:
        resource: An opened pyvisa resource.
        log_callback: A function for logging.

    Returns:
        An instance of a SpectrumAnalyzer subclass, or None if the device is not supported.
    """
    try:
        idn = resource.query("ID?").strip()
        log_callback(f"Queried ID for {resource.resource_name}: {idn}")
        if "8563A" in idn:
            return HP8563A(resource)
        elif "8593EM" in idn:
            return HP8593EM(resource)
        else:
            log_callback(f"Device with ID '{idn}' is not a supported SA.")
            return None
    except pyvisa.errors.VisaIOError as e:
        log_callback(f"VISA Error querying ID for {resource.resource_name}: {e}")
        return None
