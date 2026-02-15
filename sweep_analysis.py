import csv
import time

import matplotlib.pyplot as plt
import numpy as np
import pyvisa
from devices.hp8593em import HP8593EM
from devices.hp8673b import HP8673B
from sweep_utils import halton, parse_frequency, run_sweep
from visa_utils import discover_and_connect


def main():
    """
    Main function to run the sweep analysis.
    """
    sa = None
    sg = None
    results = []
    
    # Setup plot
    plt.ion()
    fig, ax = plt.subplots()
    line, = ax.plot([], [], 'o-')
    ax.set_xlabel("Frequency (MHz)")
    ax.set_ylabel("Power (dBm)")
    ax.grid()

    try:
        device_map = {
            '8593EM': HP8593EM,
            '8673B': HP8673B
        }
        found_devices = discover_and_connect(device_map)
        sa = found_devices['8593EM']
        sg = found_devices['8673B']
        print("Successfully connected to both devices.")

        start_freq_str = input("Enter start frequency (e.g., 100MHz, 1.5GHz): ")
        end_freq_str = input("Enter end frequency (e.g., 500MHz, 2.5GHz): ")
        points_str = input("Enter number of points (optional, default is 1000 for Halton): ")

        start_freq = parse_frequency(start_freq_str)
        end_freq = parse_frequency(end_freq_str)
        
        # Set plot limits based on frequency range
        ax.set_xlim(start_freq / 1e6, end_freq / 1e6)
        
        if points_str:
            num_points = int(points_str)
            frequencies = np.linspace(start_freq, end_freq, num_points)
            print(f"Performing linear sweep with {num_points} points.")
        else:
            num_points = 1000  # Default for Halton
            print(f"Performing Halton sequence sweep with {num_points} points.")
            frequencies = [start_freq + (end_freq - start_freq) * halton(i, 2) for i in range(1, num_points + 1)]
            frequencies.insert(0, start_freq)
            frequencies.append(end_freq)


        # Setup devices
        sg.set_power(0)
        sg.enable_rf(True)
        sa.set_zero_span()

        # Sweep
        measured_freqs = []
        measured_powers = []
        
        sweep_generator = run_sweep(sa, sg, frequencies, log_callback=print)

        for freq, power in sweep_generator:
            results.append((freq, power))
            
            # Update plot
            measured_freqs.append(freq / 1e6)
            measured_powers.append(power)
            line.set_data(measured_freqs, measured_powers)
            
            # Adjust Y axis limits
            if measured_powers:
                ax.set_ylim(min(measured_powers) - 5, max(measured_powers) + 5)
                
            plt.pause(0.01)

    except ConnectionError as e:
        print(f"Error: {e}")
    except ValueError:
        print("Invalid frequency or number of points.")
    finally:
        if sa:
            sa.close()
        if sg:
            sg.enable_rf(False)
            sg.close()
        print("Connections closed.")
        
        if results:
            print("\n--- Final Results ---")
            # Sort results by frequency for clean plotting and reporting
            results.sort(key=lambda x: x[0])
            for freq, power in results:
                print(f"{freq/1e6:.3f} MHz: {power:.2f} dBm")

            # Update final plot with sorted data
            sorted_freqs_mhz = [r[0] / 1e6 for r in results]
            sorted_powers = [r[1] for r in results]
            line.set_data(sorted_freqs_mhz, sorted_powers)
            ax.set_xlim(min(sorted_freqs_mhz), max(sorted_freqs_mhz))
            ax.set_ylim(min(sorted_powers) - 5, max(sorted_powers) + 5)
            fig.canvas.draw()
            fig.canvas.flush_events()


            # Save CSV
            csv_filename = input("Enter CSV filename to save data (or press Enter to skip): ")
            if csv_filename:
                if not csv_filename.lower().endswith('.csv'):
                    csv_filename += '.csv'
                with open(csv_filename, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(['Frequency (Hz)', 'Power (dBm)'])
                    writer.writerows(results)
                print(f"Data saved to {csv_filename}")

            # Save Plot
            png_filename = input("Enter PNG filename to save plot (or press Enter to skip): ")
            if png_filename:
                if not png_filename.lower().endswith('.png'):
                    png_filename += '.png'
                fig.savefig(png_filename)
                print(f"Plot saved to {png_filename}")

        plt.ioff()
        print("Script finished. Close the plot window to exit.")
        plt.show()

if __name__ == "__main__":
    main()
