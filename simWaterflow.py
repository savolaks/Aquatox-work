# This is a sample Python script.

# Press Shift+F10 to execute it or replace it with your code.
# Press Double Shift to search everywhere for classes, files, tool windows, actions, and settings.
import math
import matplotlib.pyplot as plt

def print_hi(name):
    # Use a breakpoint in the code line below to debug your script.
    print(f'Hi, {name}')  # Press Ctrl+F8 to toggle the breakpoint.


    # Simulation parameters
    days = 365 * 4  # simulate 4 years (daily steps)
    initial_volume = 200.0  # initial volume of water (m^3)

    # Arrays to store results
    volume = [0.0] * days
    inflow = [0.0] * days
    outflow = [0.0] * days

    # Initial state
    vol = initial_volume

    for t in range(days):
        # Define a seasonal inflow (m^3/day): peaks in spring, lower in autumn
        inflow[t] = 5.0 + 2.5 * math.sin(2 * math.pi * t / 365.0)
        # Outflow rule: store water in winter, release in spring
        if t % 365 < 60:  # Jan–Feb: outflow = 70% of inflow (store water)
            outflow[t] = 0.7 * inflow[t]
        elif t % 365 < 120:  # Mar–Apr: outflow = 100% of inflow (normal)
            outflow[t] = inflow[t]
        elif t % 365 < 150:  # May (spring): outflow = 140% of inflow (flood release)
            outflow[t] = 1.4 * inflow[t]
        else:  # Jun–Dec: outflow = 100% of inflow
            outflow[t] = inflow[t]
        # Evaporation (m^3/day), assumed constant
        evap = 0.05
        # Update volume using dV = Inflow – Outflow – Evap
        vol += (inflow[t] - outflow[t] - evap)
        if vol < 0:
            vol = 0  # prevent negative volume
        volume[t] = vol

    # Output check
    print("Initial volume:", initial_volume, "m^3")
    print("Final volume after 4 years:", round(volume[-1], 2), "m^3")

    # Plot the results to visualize (if running interactively)
    plt.figure(figsize=(8, 5))
    plt.plot(volume, label="Water Volume (m^3)")
    plt.title("Simulated Water Volume Over Time")
    plt.xlabel("Day")
    plt.ylabel("Volume of water (m^3)")
    plt.legend()
    plt.show()

# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    print_hi('PyCharm')

# See PyCharm help at https://www.jetbrains.com/help/pycharm/
