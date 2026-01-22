import sys
import os
import csv
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import matplotlib.lines as mlines
import re
from datetime import datetime

# --- SETTINGS ---
DOT_SIZE = 5            # Size of the dots
COLOR_MODE = "value"    # Options: "value" (gradient) OR "constellation" (fixed color)

# Default scale settings (for high values only)
V_MIN = 25              # Minimum gradient scale value 
V_MAX = 55              # Maximum gradient scale value

# Select which constellations to plot.
VISIBLE_CONSTELLATIONS = ['G', 'R', 'E', 'C']  # G=GPS,R=GLONASS, E=Galileo, C=Beidou

# Select the color for each constellation (for COLOR_MODE = "constellation" only)
CONST_COLORS = { 'G': 'green', 'R': 'red', 'E': 'blue', 'C': 'purple' }
# ----------------

# --- SMART VARIABLE MAPPING ---
# Maps a generic alias (or specific code) to the corresponding code for each constellation.
# TODO: Add more aliases
OBS_MAPPING = {
    # --- PRIMARY FREQUENCY (L1 / E1 / B1) ---
    'S1': {'G':['S1C'], 'R':['S1C'], 'E':['S1C'], 'C':['S2I']},
    'S1C': {'G':['S1C'], 'R':['S1C'], 'E':['S1C'], 'C':['S2I']},
    
    'L1': {'G':['L1C'], 'R':['L1C'], 'E':['L1C'], 'C':['L2I']},
    'L1C': {'G':['L1C'], 'R':['L1C'], 'E':['L1C'], 'C':['L2I']},

    'C1': {'G':['C1C'], 'R':['C1C'], 'E':['C1C'], 'C':['C2I']},
    'C1C': {'G':['C1C'], 'R':['C1C'], 'E':['C1C'], 'C':['C2I']},

    # --- SECONDARY FREQUENCY (L2 / G2 / B2 / E5b) ---
    # GPS: S2W/S2S, GLONASS: S2C/S2P, Beidou: S7I (B2), Galileo: S7Q (E5b)
    'S2': {'G':['S2W','S2S'], 'R':['S2C','S2P'], 'E':['S7Q'], 'C':['S7I','S6I']}, 
    'S2W': {'G':['S2W','S2S'], 'R':['S2C','S2P'], 'E':['S7Q'], 'C':['S7I']},

    'L2': {'G':['L2W','L2S'], 'R':['L2C','L2P'], 'E':['L7Q'], 'C':['L7I','L6I']},

    'C2': {'G':['C2W','C2S'], 'R':['C2C','C2P'], 'E':['C7Q'], 'C':['C7I','C6I']},
}
# ----------------


# --- Reads RINGO Files (.csv) ---
def parse_ringo(filename, target_obs=None):
    data = {} 
    print(f"Reading RINGO file: {filename}")
    
    with open(filename, 'r') as f:
        lines = f.readlines()

    current_idx_map = {} 
    start_time_obj = None
    count = 0
    headers_found = 0
    
    # We need to know the constellation for the *current header block*
    # Since headers repeat, we'll try to detect the constellation from the data lines
    # immediately following the header.
    current_block_constellation = None
    pending_header = None
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line: 
            i += 1
            continue

        # --- CASE 1: HEADER DETECTION ---
        if "PRN" in line and ">" in line:
            clean_line = line.replace('>', '')
            pending_header = [h.strip() for h in clean_line.split(',')]
            current_block_constellation = None # Reset
            
            # Peek ahead to find constellation
            j = i + 1
            while j < len(lines):
                next_line = lines[j].strip()
                if next_line and not next_line.startswith('>'):
                    # Found a data line
                    parts = next_line.split(',')
                    if parts[0]:
                        current_block_constellation = parts[0][0] # e.g. 'G' from 'G01'
                    break
                if next_line.startswith('>'): 
                    break # Another header
                j += 1
            
            # Now resolve the columns for this constellation
            if pending_header and current_block_constellation:
                try:
                    current_idx_map = {
                        'prn': pending_header.index('PRN'),
                        'time': pending_header.index('time'),
                        'az': pending_header.index('az'),
                        'el': pending_header.index('el')
                    }
                    
                    # Resolve Value Column
                    target_idx = -1
                    if target_obs:
                        # 1. Try Smart Mapping
                        candidates = []
                        if target_obs in OBS_MAPPING:
                            candidates = OBS_MAPPING[target_obs].get(current_block_constellation, [])
                        
                        # 2. Add exact match as fallback
                        candidates.append(target_obs)
                        
                        # 3. Find first match in headers
                        for cand in candidates:
                            if cand in pending_header:
                                target_idx = pending_header.index(cand)
                                break
                    else:
                        # Auto-detect (Legacy behavior)
                        for candidate in ['S1C', 'S1', 'S2S', 'S2', 'C1C', 'L1C']:
                            if candidate in pending_header:
                                target_idx = pending_header.index(candidate)
                                break
                    
                    current_idx_map['val'] = target_idx
                    headers_found += 1
                except ValueError:
                    current_idx_map = {}

            i += 1
            continue

        # --- CASE 2: DATA PARSING ---
        if not current_idx_map: 
            i += 1
            continue

        parts = line.split(',')
        try:
            val_idx = current_idx_map.get('val', -1)
            # If this block doesn't have the requested variable, skip
            if val_idx == -1: 
                i += 1
                continue

            prn_idx = current_idx_map['prn']
            if prn_idx >= len(parts): 
                i += 1
                continue
            prn = parts[prn_idx].strip()
            if not prn: 
                i += 1
                continue

            if prn not in data: 
                data[prn] = {'az':[], 'el':[], 'val':[], 'time':[]}
            
            # Time Parsing
            time_idx = current_idx_map['time']
            t_str = parts[time_idx].strip()
            if "." in t_str:
                t_obj = datetime.strptime(t_str.split('.')[0], "%Y-%m-%d %H:%M:%S")
            else:
                t_obj = datetime.strptime(t_str, "%Y-%m-%d %H:%M:%S")
            
            if start_time_obj is None: start_time_obj = t_obj
            delta = t_obj - start_time_obj
            hours = delta.total_seconds() / 3600.0

            # Geometry
            az_idx = current_idx_map['az']
            el_idx = current_idx_map['el']
            az_txt = parts[az_idx].strip()
            el_txt = parts[el_idx].strip()
            
            if not az_txt or not el_txt:
                az, el = np.nan, np.nan
            else:
                az, el = float(az_txt), float(el_txt)
            
            # Value
            val = 0.0
            if val_idx < len(parts):
                val_txt = parts[val_idx].strip()
                if val_txt:
                    val = float(val_txt)
            
            data[prn]['az'].append(az)
            data[prn]['el'].append(el)
            data[prn]['val'].append(val)
            data[prn]['time'].append(hours)
            count += 1

        except (ValueError, IndexError):
            pass
        
        i += 1
            
    print(f"  -> Found {headers_found} header blocks.")
    print(f"  -> Successfully read {count} data points matching '{target_obs if target_obs else 'Auto'}'")
    return data


# --- Reads TEQC Files (.azi + .ele + values) ---
def parse_teqc(files):
    """Reads TEQC files."""
    data = {}
    azi_file = next((f for f in files if f.endswith('.azi')), None)
    ele_file = next((f for f in files if f.endswith('.ele')), None)
    val_file = next((f for f in files if not f.endswith('.azi') and not f.endswith('.ele')), None)
    
    t_samp = 30.0 
    if azi_file:
        with open(azi_file, 'r') as f:
            for line in f:
                if "T_SAMP" in line:
                    try:
                        t_samp = float(line.split()[1])
                        print(f"  -> Detected Sample Rate: {t_samp}s")
                    except: pass
                    break

    print(f"Reading TEQC files...")
    # (Existing TEQC logic unchanged for brevity, insert full function here if needed)
    # Re-inserting simplified compact reader for completeness
    def read_compact(fname):
        content = []
        if not fname: return content
        with open(fname, 'r') as f:
            lines = f.readlines()
        sv_pattern = re.compile(r'[GRECJSI]\d{2}')
        active_svs = []
        for line in lines:
            line = line.strip()
            if not line or "COMPACT" in line: continue
            found_svs = sv_pattern.findall(line)
            if len(found_svs) > 0:
                parts = line.split()
                if parts[0].isdigit() and int(parts[0]) == len(found_svs):
                    active_svs = found_svs
                    continue
            if active_svs:
                try:
                    vals = [float(x) for x in line.split()]
                    if len(vals) == len(active_svs):
                        content.append((active_svs, vals))
                except ValueError: continue
        return content

    azi_data = read_compact(azi_file)
    ele_data = read_compact(ele_file)
    val_data = read_compact(val_file) if val_file else []
    
    limit = max(len(azi_data), len(val_data)) if azi_data or val_data else 0
    print(f"Processing {limit} epochs...")

    for i in range(limit):
        current_time = (i * t_samp) / 3600.0
        epoch_data = {} 
        def merge(source, key):
            if i < len(source):
                svs, vals = source[i]
                for j, sv in enumerate(svs):
                    if sv not in epoch_data: epoch_data[sv] = {}
                    epoch_data[sv][key] = vals[j]
        merge(azi_data, 'az')
        merge(ele_data, 'el')
        merge(val_data, 'val')

        for sv, props in epoch_data.items():
            if sv not in data: data[sv] = {'az':[], 'el':[], 'val':[], 'time':[]}
            data[sv]['az'].append(props.get('az', np.nan))
            data[sv]['el'].append(props.get('el', np.nan))
            data[sv]['val'].append(props.get('val', 0.0))
            data[sv]['time'].append(current_time)
    return data


# --- Plots the normalized data ---
def plot_data(data, mode="skyplot", obs_name=None):
    if not data:
        print("No data found (check if your requested variable exists in the file).")
        return

    # Adjust figure size
    fig_size = (12, 6) if "time" in mode or mode == "vis" else (10, 9)
    fig = plt.figure(figsize=fig_size)
    
    plot_title = f"{mode.upper()}"
    if obs_name:
        plot_title += f" - {obs_name}"

    if mode == "skyplot":
        ax = fig.add_axes([0.1, 0.1, 0.8, 0.8], projection='polar')
        ax.set_theta_zero_location('N')
        ax.set_theta_direction(-1)
        ax.set_yticks(range(0, 90, 30))
        ax.set_yticklabels(['90', '60', '30'])
        ax.set_title(plot_title, pad=20)
    elif mode == "azel":
        ax = fig.add_subplot(111)
        ax.set_xlabel("Azimuth (Deg)")
        ax.set_ylabel("Elevation (Deg)")
        ax.set_xlim(0, 360)
        ax.set_ylim(0, 90)
        ax.grid(True, linestyle='--', alpha=0.5)
        ax.set_title(plot_title)
    elif mode == "elval":
        ax = fig.add_subplot(111)
        ax.set_xlabel("Elevation (Deg)")
        ax.set_ylabel(f"Value ({obs_name if obs_name else 'Unit'})")
        ax.grid(True, linestyle='--', alpha=0.5)
        ax.set_title(plot_title)
    elif mode == "time":
        ax = fig.add_subplot(111)
        ax.set_xlabel("Time (Hours)")
        ax.set_ylabel(f"Value ({obs_name if obs_name else 'Unit'})")
        ax.grid(True, linestyle='--', alpha=0.5)
        ax.set_title(plot_title)
    elif mode == "vis":
        ax = fig.add_subplot(111)
        ax.set_xlabel("Time (Hours)")
        ax.set_ylabel("Satellite PRN")
        ax.grid(True, linestyle='--', alpha=0.5)
        ax.set_title(plot_title)

    # --- SMART SCALING LOGIC ---
    all_vals = []
    for sv in data: 
        if sv[0].upper() in VISIBLE_CONSTELLATIONS:
            all_vals.extend(data[sv]['val'])
    
    all_vals = np.array(all_vals)
    valid_vals = all_vals[(~np.isnan(all_vals)) & (np.abs(all_vals) > 0.0001)]

    if len(valid_vals) == 0:
        vmin, vmax = -1, 1 
    elif np.max(valid_vals) > 10: 
        vmin, vmax = V_MIN, V_MAX
    else:
        limit = np.percentile(np.abs(valid_vals), 98) 
        limit = max(limit, 0.2) 
        vmin, vmax = -limit, limit
        print(f"  -> Auto-detected Data Range: {vmin:.2f} to {vmax:.2f}")
        
    cmap = cm.nipy_spectral

    print(f"Plotting mode: {mode} (Color: {COLOR_MODE})...")
    sc = None 
    
    # --- FILTER SATELLITES ---
    raw_svs = sorted(data.keys())
    filtered_svs = [sv for sv in raw_svs if sv[0].upper() in VISIBLE_CONSTELLATIONS]
    print(f"Satellites found: {len(raw_svs)} -> Filtered to: {len(filtered_svs)}")

    constellation_legend_items = {} 

    for i, sv in enumerate(filtered_svs):
        d = data[sv]
        az = np.array(d['az'])
        el = np.array(d['el'])
        val = np.array(d['val'])
        time_hours = np.array(d['time']) 

        valid_mask = np.abs(val) > 0.001
        if mode in ["skyplot", "azel"]:
            valid_mask = valid_mask & (~np.isnan(az)) & (~np.isnan(el))

        az_clean = az[valid_mask]
        el_clean = el[valid_mask]
        val_clean = val[valid_mask]
        t_clean = time_hours[valid_mask]

        if len(val_clean) == 0: continue

        plot_kwargs = {}
        const_char = sv[0].upper()
        
        if COLOR_MODE == "constellation":
            c_solid = CONST_COLORS.get(const_char, 'black')
            plot_kwargs['color'] = c_solid
            plot_kwargs['edgecolors'] = 'none' 
            constellation_legend_items[const_char] = c_solid 
        else:
            plot_kwargs['c'] = val_clean
            plot_kwargs['cmap'] = cmap
            plot_kwargs['vmin'] = vmin
            plot_kwargs['vmax'] = vmax
            plot_kwargs['edgecolors'] = 'none'

        if mode == "skyplot":
            x = az_clean * np.pi / 180.0
            y = 90 - el_clean
            sc = ax.scatter(x, y, s=DOT_SIZE, **plot_kwargs)
        elif mode == "azel":
            sc = ax.scatter(az_clean, el_clean, s=DOT_SIZE, **plot_kwargs)
        elif mode == "elval":
            sc = ax.scatter(el_clean, val_clean, s=DOT_SIZE, **plot_kwargs)
        elif mode == "time":
            sort_idx = np.argsort(t_clean)
            t_sorted = t_clean[sort_idx]
            v_sorted = val_clean[sort_idx]
            dt = np.diff(t_sorted)
            gap_indices = np.where(dt > 0.2)[0]
            line_color = plot_kwargs.get('color', None) 
            if len(gap_indices) > 0:
                last_idx = 0
                for gap_idx in gap_indices:
                    segment_t = t_sorted[last_idx : gap_idx+1]
                    segment_v = v_sorted[last_idx : gap_idx+1]
                    ax.plot(segment_t, segment_v, color=line_color, linewidth=1, alpha=0.7, marker='o', markersize=DOT_SIZE/2) 
                    last_idx = gap_idx + 1
                ax.plot(t_sorted[last_idx:], v_sorted[last_idx:], label=sv, color=line_color, linewidth=1, alpha=0.7, marker='o', markersize=DOT_SIZE/2)
            else:
                ax.plot(t_sorted, v_sorted, label=sv, color=line_color, linewidth=1, alpha=0.7, marker='o', markersize=DOT_SIZE/2)
        elif mode == "vis":
            ax.scatter(t_clean, [i]*len(t_clean), s=DOT_SIZE, marker='s', **plot_kwargs)
            if COLOR_MODE == "value" and sc is None:
                sc = ax.scatter([], [], c=[], cmap=cmap, vmin=vmin, vmax=vmax) 

    if mode == "vis":
        ax.set_yticks(range(len(filtered_svs)))
        ax.set_yticklabels(filtered_svs, fontsize=8)

    if COLOR_MODE == "constellation":
        legend_handles = []
        for char, color in sorted(constellation_legend_items.items()):
            name_map = {'G':'GPS','R':'GLONASS','E':'Galileo','C':'Beidou'}
            label = f"{name_map.get(char, char)} ({char})"
            handle = mlines.Line2D([], [], color='w', marker='o', markersize=10, markerfacecolor=color, label=label)
            legend_handles.append(handle)
        if legend_handles:
            ax.legend(handles=legend_handles, loc='upper left', bbox_to_anchor=(1.05, 1), borderaxespad=0.)
            plt.subplots_adjust(right=0.8) 
    elif mode != "time" and sc:
        plt.colorbar(sc, label=obs_name if obs_name else "Value")
    
    print("Done. Window opening...")
    plt.show()


# --- Main Method ---
if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python gnssplot.py <mode> <files...> [--obs <OBS_CODE>]")
        print("Example: python gnssplot.py skyplot rnx.csv --obs S1")
        sys.exit()

    args = sys.argv[1:]
    target_obs = None
    if "--obs" in args:
        idx = args.index("--obs")
        if idx + 1 < len(args):
            target_obs = args[idx+1]
            del args[idx]; del args[idx]
        else:
            print("Error: --obs flag provided but no variable name specified.")
            sys.exit()

    mode = args[0]
    files = args[1:]
    
    print(f"Running gnssplot.py")
    print(f"Settings -> Dot Size: {DOT_SIZE}, Color Mode: {COLOR_MODE}")
    print(f"Settings -> Obs Variable: {target_obs if target_obs else 'Auto-detect'}")

    if any(f.endswith('.csv') for f in files):
        data = parse_ringo(files[0], target_obs=target_obs)
    else:
        data = parse_teqc(files)
        
    plot_data(data, mode, obs_name=target_obs)
