# gnssplot.py
Python3 CLI utility to parse and plot gnss quality control data produced from RINGO and TEQC.

--- Installation ---

1. Place 'gnssplot.py' in C:\GNSSPLOT (or any other directory you wish).
2. Add C:\GNSSPLOT to PATH to be able to execute without specifying its location each time.
3. Place your Quality Control files in C:\GNSSPLOT\QC (or any other directory you wish).

--- Necessary Quality Control Files ---

- RINGO: you need the file that contains the aggregated observables (.csv).

- TEQC: you need two files for geometry (.ele + .azi) and one for the values you wish to plot (.sn1/.sn2/.mp1/.mp2/.ion/.iod).

--- Commands ---

- First go to the directory you keep the quality control files

  cd C:\GNSSPLOT\QC

- For RINGO:

  python gnssplot.py [plottype] [.csv filename] --obs [observable to plot]

  e.g. python gnssplot.py skyplot rnx.csv --obs S1

- For TEQC:

  python gnssplot.py [plottype] [.azi filename] [.ele filename] [value filename]

  e.g. python gnssplot.py azel rnx.azi rnx.ele rnx.sn1

--- Plot Types ---

- skyplot: Elevation vs Azimuth Polar Graph
- azel: Elevation vs Azimuth Cartesian Graph
- elval: Elevation vs Value Cartesian Graph
- time: Time Series
- vis: Visibility/Gantt Chart

--- Observable to Plot (RINGO only) ---

- S1: Signal Strength on Primary Freq (L1/E1/B1)
- L1: Carrier Phase on Primary Freq (L1/E1/B1)
- C1: Pseudorange on Primary Freq (L1/E1/B1)
- S2: Signal Strength on Secondary Freq (L2/G2)
- L2: Carrier Phase on Secondary Freq (L2/G2)
- C2: Pseudorange on Secondary Freq (L2/G2)
