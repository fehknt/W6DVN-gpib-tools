import numpy as np
import time

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

def halton(index, base):
    """Generator for Halton sequence."""
    result = 0
    f = 1
    i = index
    while i > 0:
        f = f / base
        result = result + f * (i % base)
        i = int(i / base)
    return result

def run_sweep(sa, sg, frequencies, sg_tracking_disabled=False, sa_freq_offset=0, log_callback=None):
    """
    Runs a frequency sweep and yields the results.

    Args:
        sa: Spectrum analyzer instance.
        sg: Signal generator instance.
        frequencies: A list or array of frequencies to sweep.
        sg_tracking_disabled (bool): If True, the SG frequency is not changed.
        sa_freq_offset (int): Frequency offset for the spectrum analyzer.
        log_callback: A function to call for logging messages.
    """
    if log_callback is None:
        log_callback = print

    start_time = time.time()
    for freq in frequencies:
        if not sg_tracking_disabled:
            log_callback(f"Setting SG freq: {freq}")
            sg.set_frequency(freq + sa_freq_offset)
            sleep(0.1)  # Small delay to allow SG to settle
        
        sa_freq = freq + sa_freq_offset
        log_callback(f"Measuring SA (with offset) at {sa_freq}Hz...")
        sa.set_center_frequency(sa_freq)

        sa.take_sweep()
        sa.wait_done()

        power = sa.get_marker_power()
        log_callback(f"  Power: {power:.2f} dBm")
        
        yield freq, power
    
    stop_time = time.time()
    log_callback(f"Done running sweep. Sweep took {int(stop_time-start_time)} seconds.")
