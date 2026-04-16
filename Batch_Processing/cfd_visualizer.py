"""
Multi-Format CFD Visualizer - BATCH EDITION (v3.1 - Optimized)
[...rest of docstring...]
"""

from paraview.simple import *
import os
import sys
import re
import shutil
import xml.etree.ElementTree as ET
import json
import math
import datetime

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("[ERROR] Required library 'Pillow' is not installed in ParaView's Python environment.")
    sys.exit(1)

# ================================================================
# 1. CONFIGURATION & SETUP
# ================================================================

def load_config(raw_path=None):
    """
    Load configuration from JSON file or treat input as CFD file path.
    If raw_path is provided (e.g., from command line), use it directly.
    Otherwise, prompt user for input.
    
    Args:
        raw_path (str): Optional path to either JSON config file or CFD data file
        
    Returns:
        tuple: (config dict or None, input_file path, output_resolution list)
    """
    # If raw_path not provided, prompt user
    if raw_path is None:
        raw_path = input("Drag and drop your CFD file OR a .json config file here > ").strip(' "\'')
    
    initial_path = os.path.abspath(raw_path)
    config = None
    output_resolution = [1920, 1080]
    
    if initial_path.lower().endswith('.json'):
        print(f"\n[INFO] Loading configuration from JSON: {initial_path}")
        try:
            with open(initial_path, 'r') as f:
                config = json.load(f)
            input_file = os.path.abspath(config.get("input_file", ""))
            output_resolution = config.get("resolution", [3840, 2160])
        except Exception as e:
            print(f"[ERROR] Failed to parse JSON config: {e}")
            sys.exit(1)
    else:
        input_file = initial_path
    
    if not os.path.exists(input_file):
        print(f"[ERROR] File not found on disk: {input_file}")
        sys.exit(1)
    
    return config, input_file, output_resolution


def get_zoom_settings(config):
    """
    Extract zoom factor and zoom center from config or prompt user.
    
    Args:
        config (dict): Configuration dictionary
        
    Returns:
        tuple: (zoom_factor float, zoom_center list or None)
    """
    zoom_factor = 1.0
    zoom_center = None
    
    if config:
        zoom_factor = float(config.get("zoom_factor", 1.0))
        zoom_center = config.get("zoom_center", None)
    else:
        try:
            user_zoom = input("\nEnter Zoom Factor (1.0 = Fit to Screen, 1.5 = Zoom In, 0.5 = Zoom Out) [Default 1.0] > ").strip()
            if user_zoom:
                zoom_factor = float(user_zoom)
        except ValueError:
            print("[WARNING] Invalid zoom factor. Defaulting to 1.0 (Fit to Screen).")
    
    return zoom_factor, zoom_center


def setup_output_directories(case_dir):
    """
    Create output directory structure with auto-incrementing run numbers.
    
    Args:
        case_dir (str): Base case directory
        
    Returns:
        tuple: (results_dir, run_dir, next_run_num)
    """
    results_dir = os.path.join(case_dir, "Images")
    os.makedirs(results_dir, exist_ok=True)
    
    run_numbers = [0]
    for f in os.listdir(results_dir):
        match = re.search(r'Run_(\d+)', f)
        if match:
            run_numbers.append(int(match.group(1)))
    
    next_run_num = max(run_numbers) + 1
    run_dir = os.path.join(results_dir, f"Run_{next_run_num}")
    os.makedirs(run_dir, exist_ok=True)
    
    return results_dir, run_dir, next_run_num


# ================================================================
# 2. HELPER FUNCTIONS
# ================================================================

def flatten_pvd(pvd_path):
    """
    Flatten PVD (ParaView Data) file structure by moving nested data files to parent directory.
    Helps with file portability and reduces clutter.
    
    Args:
        pvd_path (str): Path to PVD file
    """
    if not os.path.exists(pvd_path):
        return
    
    try:
        tree = ET.parse(pvd_path)
        root = tree.getroot()
        base_dir = os.path.dirname(pvd_path)
        data_dir_name = os.path.splitext(os.path.basename(pvd_path))[0]
        data_dir_path = os.path.join(base_dir, data_dir_name)
        
        if not os.path.exists(data_dir_path):
            return
        
        # Move all files from data directory to parent directory
        for item in os.listdir(data_dir_path):
            src_path = os.path.join(data_dir_path, item)
            dst_path = os.path.join(base_dir, item)
            if not os.path.exists(dst_path):
                shutil.move(src_path, dst_path)
        
        # Update PVD XML references to point to flattened files
        modified = False
        for dataset in root.iter('DataSet'):
            file_rel_path = dataset.get('file')
            if file_rel_path:
                dataset.set('file', os.path.basename(file_rel_path.replace('\\', '/')))
                modified = True
        
        if modified:
            tree.write(pvd_path, encoding='utf-8', xml_declaration=True)
        
        # Clean up empty directory
        if not os.listdir(data_dir_path):
            os.rmdir(data_dir_path)
    except Exception as e:
        print(f"[WARNING] Could not flatten PVD structure: {e}")


def add_iso_info_overlay(img_path, iso_settings):
    """
    Add informational overlay to iso-surface images showing geometry and coloring details.
    Creates a semi-transparent box with text in top-left corner.
    
    Args:
        img_path (str): Path to image file
        iso_settings (dict): Dictionary containing 'var', 'val', 'color' keys
    """
    try:
        with Image.open(img_path) as img:
            draw = ImageDraw.Draw(img)
            width, height = img.size
            font_size = max(int(width * 0.018), 20)
            
            try:
                font = ImageFont.truetype("arial.ttf", font_size)
            except Exception:
                font = ImageFont.load_default()
            
            # Create overlay text
            geom_text = f"Iso-Geometry : {iso_settings['var']} = {iso_settings['val']}"
            color_text = f"Coloring By  : {iso_settings['color'] if iso_settings['color'] else 'Solid Color'}"
            
            # Calculate text dimensions
            try:
                w_geom = font.getbbox(geom_text)[2] - font.getbbox(geom_text)[0]
                w_color = font.getbbox(color_text)[2] - font.getbbox(color_text)[0]
                max_w = max(w_geom, w_color)
                line_height = font.getbbox("Ay")[3] - font.getbbox("Ay")[1] + int(font_size * 0.3)
            except AttributeError:
                w_geom, h_geom = font.getsize(geom_text)
                w_color, h_color = font.getsize(color_text)
                max_w = max(w_geom, w_color)
                line_height = max(h_geom, h_color) + int(font_size * 0.3)
            
            # Create semi-transparent overlay box
            box_padding = int(font_size * 0.6)
            box_w = max_w + (2 * box_padding)
            box_h = (line_height * 2) + (2 * box_padding) - int(font_size * 0.3)
            pos_x, pos_y = int(width * 0.03), int(height * 0.05)
            
            overlay = Image.new('RGBA', img.size, (255, 255, 255, 0))
            overlay_draw = ImageDraw.Draw(overlay)
            
            box_rect = [pos_x, pos_y, pos_x + box_w, pos_y + box_h]
            overlay_draw.rectangle(box_rect, fill=(255, 255, 255, 200), outline=(0, 0, 0, 255),
                                 width=max(2, int(font_size * 0.1)))
            overlay_draw.text((pos_x + box_padding, pos_y + box_padding), geom_text,
                            fill=(0, 0, 0, 255), font=font)
            overlay_draw.text((pos_x + box_padding, pos_y + box_padding + line_height), color_text,
                            fill=(0, 0, 0, 255), font=font)
            
            img.paste(overlay, (0, 0), overlay)
            img.convert('RGB').save(img_path)
    except Exception as e:
        print(f"[WARNING] Failed to add overlay: {e}")


def get_available_variables(reader):
    """
    Extract and return available point and cell data variables from reader.
    
    Args:
        reader: ParaView reader object with merged blocks
        
    Returns:
        tuple: (avail_points list, avail_cells list, all available_vars list)
    """
    temp_merged = MergeBlocks(Input=reader)
    temp_merged.UpdatePipeline()
    
    avail_points = list(temp_merged.PointData.keys())
    avail_cells = list(temp_merged.CellData.keys())
    available_vars = list(set(avail_points + avail_cells))
    
    return avail_points, avail_cells, available_vars, temp_merged


def select_variables(config, available_vars):
    """
    Get variables to plot from config or prompt user for selection.
    
    Args:
        config (dict): Configuration dictionary
        available_vars (list): List of available variables
        
    Returns:
        tuple: (raw_vars list, variables_to_plot list)
    """
    raw_vars = []
    
    if available_vars:
        if config and "variables" in config:
            raw_vars = config["variables"]
        else:
            print("\nAvailable variables:")
            for var in sorted(available_vars):
                print(f"  - {var}")
            raw_vars = [v.strip() for v in input("\nEnter variables to plot (comma-separated) > ").split(',')]
    
    variables_to_plot = [v for v in raw_vars if v in available_vars]
    return raw_vars, variables_to_plot


def select_iso_surfaces(config, available_vars):
    """
    Get iso-surface configurations from config or prompt user for creation.
    
    Args:
        config (dict): Configuration dictionary
        available_vars (list): List of available variables
        
    Returns:
        list: List of iso-surface configurations
    """
    iso_configs = []
    
    if config and "iso_surfaces" in config:
        for iso_cfg in config["iso_surfaces"]:
            if iso_cfg.get("create", False) and iso_cfg.get("variable") in available_vars:
                iso_configs.append({
                    'var': iso_cfg["variable"],
                    'val': float(iso_cfg["value"]),
                    'color': iso_cfg.get("color_by") if iso_cfg.get("color_by") in available_vars else None
                })
    elif not config:
        while True:
            want_iso = input("\nCreate an Iso-Surface? (y/n) > ").strip().lower()
            if want_iso != 'y':
                break
            iso_var = input("Enter variable to contour by (e.g., p, U) > ").strip()
            if iso_var in available_vars:
                try:
                    iso_val = float(input(f"Enter Iso-value for '{iso_var}' > ").strip())
                    iso_color = input("Variable to color it by? (Press Enter for solid) > ").strip()
                    iso_color = iso_color if iso_color in available_vars else None
                    iso_configs.append({'var': iso_var, 'val': iso_val, 'color': iso_color})
                except ValueError:
                    print("Invalid value. Skipping.")
    
    return iso_configs


# ================================================================
# 3. METADATA EXTRACTION
# ================================================================

def extract_openfoam_metadata(case_dir, cfd_data, run_dir, next_run_num, output_resolution, all_generated_images):
    """
    Extract metadata and generate graphs from OpenFOAM simulation files.
    Looks for force coefficients and generates matplotlib graphs if available.
    
    Args:
        case_dir (str): Case directory path
        cfd_data (dict): Dictionary to store extracted data
        run_dir (str): Output run directory
        next_run_num (int): Current run number
        output_resolution (list): Output image resolution
        all_generated_images (list): List to append generated images to
    """
    # Extract solver version and run date from log file
    log_files = [f for f in os.listdir(case_dir) if f.startswith('log.') and 'checkMesh' not in f]
    if log_files and os.path.exists(os.path.join(case_dir, log_files[0])):
        with open(os.path.join(case_dir, log_files[0]), 'r') as f:
            lines = f.readlines()
            for line in lines[:50]:
                if line.startswith('Build'):
                    cfd_data["Solver Version"] = line.split(':', 1)[1].strip()
                elif line.startswith('Date'):
                    cfd_data["Run Date"] = line.split(':', 1)[1].strip()
    
    # Extract end time from controlDict
    system_dir = os.path.join(case_dir, "system")
    controlDict_path = os.path.join(system_dir, "controlDict")
    if os.path.exists(controlDict_path):
        with open(controlDict_path, 'r') as f:
            for line in f:
                if 'endTime' in line and not line.strip().startswith('//'):
                    match = re.search(r'endTime\s+([0-9\.eE\+\-]+);', line)
                    if match:
                        cfd_data["Iterations / Time"] = match.group(1)
                        break
    
    # Extract reference area from forceCoeffs or controlDict
    for dict_file in ["forceCoeffs", "controlDict"]:
        dict_path = os.path.join(system_dir, dict_file)
        if os.path.exists(dict_path) and cfd_data["Reference Area"] == "N/A":
            with open(dict_path, 'r') as f:
                for line in f:
                    if 'Aref' in line and not line.strip().startswith('//'):
                        match = re.search(r'Aref\s+([0-9\.eE\+\-]+);', line)
                        if match:
                            cfd_data["Reference Area"] = match.group(1)
                            break
    
    # Extract force coefficients and generate graph if available
    post_dir = os.path.join(case_dir, "postProcessing")
    if os.path.exists(post_dir):
        for root, dirs, files in os.walk(post_dir):
            for file in files:
                if file.endswith('.dat') and 'forceCoeffs' in root:
                    try:
                        with open(os.path.join(root, file), 'r') as f:
                            lines = f.readlines()
                            headers = next((l for l in lines if 'Cd' in l and 'Cl' in l and l.startswith('#')), None)
                            
                            if headers:
                                h_list = headers.replace('#', '').split()
                                cd_idx = h_list.index('Cd') if 'Cd' in h_list else 1
                                cl_idx = h_list.index('Cl') if 'Cl' in h_list else 3
                                data_lines = [l for l in lines if not l.startswith('#') and l.strip()]
                                
                                if data_lines:
                                    final_vals = data_lines[-1].split()
                                    if len(final_vals) > max(cd_idx, cl_idx):
                                        cfd_data["C_D"] = final_vals[cd_idx]
                                        cfd_data["C_L"] = final_vals[cl_idx]
                                
                                # Generate matplotlib graph
                                try:
                                    import matplotlib.pyplot as plt
                                    times, cds, cls = [], [], []
                                    for l in data_lines:
                                        parts = l.split()
                                        if len(parts) > max(cd_idx, cl_idx):
                                            try:
                                                times.append(float(parts[0]))
                                                cds.append(float(parts[cd_idx]))
                                                cls.append(float(parts[cl_idx]))
                                            except ValueError:
                                                pass
                                    
                                    if times:
                                        plt.figure(figsize=(10, 6))
                                        plt.plot(times, cds, label='Cd (Drag)', color='#d62728', linewidth=2)
                                        plt.plot(times, cls, label='Cl (Lift)', color='#1f77b4', linewidth=2)
                                        plt.title('Force Coefficients Development', fontsize=16, fontweight='bold')
                                        plt.xlabel('Iterations / Time', fontsize=12)
                                        plt.ylabel('Coefficient Value', fontsize=12)
                                        plt.grid(True, linestyle='--', alpha=0.7)
                                        plt.legend(fontsize=12)
                                        plt.tight_layout()
                                        
                                        graph_path = os.path.join(run_dir, f"Run_{next_run_num}_ForceCoeffs.png")
                                        dpi_scale = 200 * (output_resolution[0] / 1920)
                                        plt.savefig(graph_path, dpi=dpi_scale, facecolor='white')
                                        plt.close()
                                        all_generated_images.insert(0, graph_path)
                                except Exception as e:
                                    print(f"[WARNING] Matplotlib graphing failed: {e}")
                    except Exception as e:
                        print(f"[WARNING] Error reading force file: {e}")


# ================================================================
# 4. MESH LOADING & REGION SELECTION
# ================================================================

def load_and_select_regions(input_file, config, file_extension):
    """
    Load CFD data and select regions for analysis.
    Supports both OpenFOAM and ANSYS EnSight formats.
    
    Args:
        input_file (str): Path to CFD data file
        config (dict): Configuration dictionary
        file_extension (str): File extension (determines format)
        
    Returns:
        tuple: (reader object, selected_regions list, is_openfoam bool)
    """
    selected_regions = []
    is_openfoam = file_extension in ['.foam', '.openfoam', '.simplefoam']
    
    if is_openfoam:
        reader = OpenFOAMReader(FileName=input_file)
        reader.UpdatePipelineInformation()
        available_regions = list(reader.MeshRegions.Available)
        
        if config and "regions" in config:
            selected_regions = [r for r in config["regions"] if r in available_regions]
        else:
            for i, reg in enumerate(available_regions):
                print(f"  {i}: {reg}")
            val = input("\nEnter region NUMBERS to analyze (e.g., 0, 3) > ").strip()
            if val:
                for v in val.split(','):
                    try:
                        selected_regions.append(available_regions[int(v.strip())])
                    except (ValueError, IndexError):
                        pass
        
        reader.MeshRegions = selected_regions if selected_regions else ['internalMesh']
    else:
        reader = OpenDataFile(input_file)
        reader.UpdatePipelineInformation()
        selected_regions = ['Imported_Domain']
    
    return reader, selected_regions, is_openfoam


# ================================================================
# 5. RENDERING & SCREENSHOT GENERATION
# ================================================================

def snap_view(renderView, file_suffix, camera_pos, view_up, prefix_name, focal_point, cam_dist,
              run_dir, next_run_num, output_resolution, zoom_factor, zoom_center, all_generated_images):
    """
    Set camera position, render scene, and save screenshot.
    Applies zoom factor and optional zoom center.
    
    Args:
        renderView: ParaView RenderView object
        file_suffix (str): Suffix for output filename
        camera_pos (list): Camera direction vector
        view_up (list): Up vector for camera
        prefix_name (str): Prefix for output filename
        focal_point (list): Default focal point coordinates
        cam_dist (float): Camera distance from focal point
        run_dir (str): Output directory
        next_run_num (int): Run number
        output_resolution (list): Output image resolution
        zoom_factor (float): Zoom factor (>1 zooms in)
        zoom_center (list): Optional custom zoom center point
        all_generated_images (list): List to append screenshot path to
    """
    # Use zoom_center if specified, otherwise use focal_point
    center_point = zoom_center if zoom_center is not None else focal_point
    
    renderView.CameraFocalPoint = center_point
    renderView.CameraPosition = [
        center_point[0] + camera_pos[0] * cam_dist,
        center_point[1] + camera_pos[1] * cam_dist,
        center_point[2] + camera_pos[2] * cam_dist
    ]
    renderView.CameraViewUp = view_up
    ResetCamera()
    
    # Apply zoom factor if not 1.0
    if zoom_factor != 1.0:
        pos = renderView.CameraPosition
        foc = renderView.CameraFocalPoint
        renderView.CameraPosition = [
            foc[0] + (pos[0] - foc[0]) / zoom_factor,
            foc[1] + (pos[1] - foc[1]) / zoom_factor,
            foc[2] + (pos[2] - foc[2]) / zoom_factor
        ]
        renderView.CameraParallelScale = renderView.CameraParallelScale / zoom_factor
    
    Render()
    f_path = os.path.join(run_dir, f"Run_{next_run_num}_{prefix_name.replace('/', '_')}_{file_suffix}.png")
    SaveScreenshot(f_path, renderView, ImageResolution=output_resolution, TransparentBackground=0)
    all_generated_images.append(f_path)


def process_region(renderView, reader, region_name, config, is_openfoam, variables_to_plot, raw_vars,
                   run_dir, next_run_num, output_resolution, zoom_factor, zoom_center, all_generated_images,
                   merged_generic=None):
    """
    Process a single region: perform slicing in multiple directions and 3D rendering as needed.
    Unified function supporting both OpenFOAM and ANSYS formats.
    
    Args:
        renderView: ParaView RenderView object
        reader: ParaView reader object
        region_name (str): Name of region to process
        config (dict): Configuration dictionary
        is_openfoam (bool): Whether data is OpenFOAM format
        variables_to_plot (list): Variables to visualize
        raw_vars (list): Raw variable list from config
        run_dir (str): Output directory
        next_run_num (int): Run number
        output_resolution (list): Output image resolution
        zoom_factor (float): Zoom factor
        zoom_center (list): Optional custom zoom center
        all_generated_images (list): List to append screenshots to
        merged_generic: Merged data for non-OpenFOAM formats
        
    Returns:
        region_data: Processed region data for further operations
    """
    print(f"\nPROCESSING: {region_name}")
    
    # Load region data
    if is_openfoam:
        reader.MeshRegions = [region_name]
        reader.UpdatePipeline()
        region_data = MergeBlocks(Input=reader)
        region_data.UpdatePipeline()
        is_boundary = 'patch' in region_name.lower()
    else:
        region_data, is_boundary = merged_generic, False
    
    # Get bounds for this region
    bounds = region_data.GetDataInformation().GetBounds()
    cx, cy, cz = ((bounds[0] + bounds[1]) / 2.0, (bounds[2] + bounds[3]) / 2.0, (bounds[4] + bounds[5]) / 2.0)
    
    domain_diagonal = math.sqrt((bounds[1] - bounds[0]) ** 2 + (bounds[3] - bounds[2]) ** 2 + (bounds[5] - bounds[4]) ** 2)
    cam_dist = max(domain_diagonal * 2.5, 0.1)
    
    print(f"[INFO] Region bounds: X[{bounds[0]:.4f}, {bounds[1]:.4f}], Y[{bounds[2]:.4f}, {bounds[3]:.4f}], Z[{bounds[4]:.4f}, {bounds[5]:.4f}]")
    print(f"[INFO] Domain diagonal: {domain_diagonal:.4f}, Camera distance: {cam_dist:.4f}")
    
    # ================================================================
    # SLICING SECTION - Supports multiple axes
    # ================================================================
    
    slicing_performed = False
    
    if not is_boundary and config and "slices" in config and region_name in config["slices"]:
        slice_cfg = config["slices"][region_name]
        slice_axes = []
        
        # Parse slice configuration - support both old and new formats
        if "axes" in slice_cfg:
            # NEW FORMAT: Multiple axes
            slice_axes = slice_cfg["axes"]
            print(f"[INFO] Multiple slice axes configured: {len(slice_axes)} axis/axes")
        elif "axis" in slice_cfg:
            # OLD FORMAT: Single axis (backward compatible)
            slice_axes = [slice_cfg]
            print(f"[INFO] Single slice axis configured: {slice_cfg.get('axis')}")
        else:
            print(f"[WARNING] Slice config found but no axis/axes specified")
        
        # Process each slice axis
        for axis_idx, axis_config in enumerate(slice_axes):
            slice_axis = axis_config.get("axis", "").lower()
            
            if slice_axis not in ['x', 'y', 'z']:
                print(f"[WARNING] Invalid slice axis: {slice_axis}. Skipping.")
                continue
            
            # Determine axis bounds based on region geometry
            if slice_axis == 'x':
                b_min = bounds[0]
                b_max = bounds[1]
            elif slice_axis == 'y':
                b_min = bounds[2]
                b_max = bounds[3]
            else:  # z
                b_min = bounds[4]
                b_max = bounds[5]
            
            # Apply 2% margin for safety
            margin = (b_max - b_min) * 0.02
            
            # Get user-specified min/max, or use auto-calculated bounds
            user_min = float(axis_config.get("min", b_min + margin))
            user_max = float(axis_config.get("max", b_max - margin))
            
            # Clamp values to safe range
            s_min = max(b_min + margin, min(b_max - margin, user_min))
            s_max = max(b_min + margin, min(b_max - margin, user_max))
            s_count = int(axis_config.get("count", 1))
            
            # Generate slice offsets
            if s_count > 1:
                step = (s_max - s_min) / (s_count - 1)
                slice_offsets = [s_min + (i * step) for i in range(s_count)]
            else:
                slice_offsets = [(s_min + s_max) / 2.0]
            
            # Log slice information
            print(f"\n[INFO] === Slice Axis {axis_idx + 1}: {slice_axis.upper()} ===")
            print(f"[INFO] Geometry bounds: {b_min:.4f} to {b_max:.4f}")
            print(f"[INFO] Slice range: {s_min:.4f} to {s_max:.4f} ({s_count} slices)")
            
            # Prepare data for slicing
            slice_input = region_data
            if not is_openfoam:
                try:
                    slice_input = CellDataToPointData(Input=region_data)
                    slice_input.ProcessAllArrays = 1
                    slice_input.UpdatePipeline()
                    print(f"[INFO] Converted cell data to point data")
                except Exception as e:
                    print(f"[WARNING] Could not convert cell data to point data: {e}")
            
            Hide(region_data, renderView)
            
            # Get available variables in slice
            slice_pt_vars = list(slice_input.PointData.keys())
            slice_cell_vars = list(slice_input.CellData.keys())
            print(f"[INFO] Available variables - Point: {slice_pt_vars}, Cell: {slice_cell_vars}")
            
            # Slice each variable
            for var in variables_to_plot:
                if var not in slice_pt_vars and var not in slice_cell_vars:
                    print(f"[WARNING] Variable '{var}' not found. Skipping.")
                    continue
                
                print(f"[INFO] Processing variable: {var}")
                
                # Create slice at each offset
                for i, offset in enumerate(slice_offsets):
                    try:
                        slc = Slice(Input=slice_input)
                        slc.SliceType = 'Plane'
                        
                        # Set slice plane based on axis
                        if slice_axis == 'x':
                            slc.SliceType.Normal = [1.0, 0.0, 0.0]
                            slc.SliceType.Origin = [offset, cy, cz]
                            cam_pos, view_up = [1, 0, 0], [0, 0, 1]
                        elif slice_axis == 'y':
                            slc.SliceType.Normal = [0.0, 1.0, 0.0]
                            slc.SliceType.Origin = [cx, offset, cz]
                            cam_pos, view_up = [0, 1, 0], [0, 0, 1]
                        else:  # z
                            slc.SliceType.Normal = [0.0, 0.0, 1.0]
                            slc.SliceType.Origin = [cx, cy, offset]
                            cam_pos, view_up = [0, 0, 1], [0, 1, 0]
                        
                        slc.UpdatePipeline()
                        slc_display = Show(slc, renderView)
                        
                        # Color the slice by variable
                        try:
                            if var in slice_pt_vars:
                                ColorBy(slc_display, ('POINTS', var))
                            else:
                                ColorBy(slc_display, ('CELLS', var))
                            
                            slc_display.SetScalarBarVisibility(renderView, True)
                            slc_display.RescaleTransferFunctionToDataRange(True, False)
                        except Exception as e:
                            print(f"[WARNING] Could not color by {var}: {e}")
                        
                        # Take screenshot
                        suffix = f"Slice_{slice_axis.upper()}{i + 1}_{var}"
                        print(f"  -> Snapping: {suffix}")
                        
                        snap_view(renderView, suffix, cam_pos, view_up, region_name, [cx, cy, cz], cam_dist,
                                run_dir, next_run_num, output_resolution, zoom_factor, zoom_center, all_generated_images)
                        
                        Hide(slc, renderView)
                        Delete(slc)
                        
                    except Exception as e:
                        print(f"[ERROR] Failed to slice: {e}")
            
            Show(region_data, renderView)
            slicing_performed = True
            print(f"[INFO] Finished {slice_axis.upper()}-axis slicing")
    
    # Export region data
    pvd_export_path = os.path.join(run_dir, f"Run_{next_run_num}_{region_name.replace('/', '_')}_summary.pvd")
    try:
        SaveData(pvd_export_path, proxy=region_data)
        flatten_pvd(pvd_export_path)
        print(f"[INFO] Exported PVD: {pvd_export_path}")
    except Exception as e:
        print(f"[WARNING] Could not export PVD: {e}")
    
    # ================================================================
    # 3D RENDERING SECTION
    # ================================================================
    
    should_do_3d = is_boundary or not slicing_performed
    
    if should_do_3d:
        print(f"\n[INFO] Starting 3D rendering for {region_name}")
        HideAll(renderView)
        display = Show(region_data, renderView)
        display.Representation = 'Surface'
        
        region_point_vars, region_cell_vars = list(region_data.PointData.keys()), list(region_data.CellData.keys())
        print(f"[INFO] Available 3D variables - Point: {region_point_vars}, Cell: {region_cell_vars}")
        
        for var in variables_to_plot:
            if var not in raw_vars:
                continue
            
            # Color by variable
            if var in region_point_vars:
                ColorBy(display, ('POINTS', var))
                print(f"[INFO] 3D coloring by POINTS: {var}")
            elif var in region_cell_vars:
                ColorBy(display, ('CELLS', var))
                print(f"[INFO] 3D coloring by CELLS: {var}")
            else:
                print(f"[WARNING] Variable not found: {var}")
                continue
            
            try:
                display.RescaleTransferFunctionToDataRange(True, False)
                display.SetScalarBarVisibility(renderView, True)
            except Exception as e:
                print(f"[WARNING] Could not set color range: {e}")
            
            # Generate multiple 3D views
            views_to_take = [
                ("front", [1, 0, 0], [0, 0, 1]),
                ("side", [0, 1, 0], [0, 0, 1]),
                ("top", [0, 0, 1], [1, 0, 0]),
                ("front_iso", [1, 1, 1], [0, 0, 1]),
                ("rear_iso", [-1, 1, 1], [0, 0, 1])
            ]
            
            for v_name, c_pos, c_up in views_to_take:
                try:
                    snap_view(renderView, f"{var}_{v_name}", c_pos, c_up, region_name, [cx, cy, cz], cam_dist,
                            run_dir, next_run_num, output_resolution, zoom_factor, zoom_center, all_generated_images)
                except Exception as e:
                    print(f"[WARNING] Failed snapshot {v_name} for {var}: {e}")
            
            display.SetScalarBarVisibility(renderView, False)
    
    return region_data

# ================================================================
# 6. PDF REPORT GENERATION
# ================================================================

def create_pdf_cover_page(pdf_width, pdf_height, next_run_num, run_settings, cfd_data):
    """
    Create cover page for PDF report with dynamically scaled text and table.
    
    Args:
        pdf_width (int): PDF width in pixels
        pdf_height (int): PDF height in pixels
        next_run_num (int): Run number
        run_settings (dict): Run configuration settings
        cfd_data (dict): CFD simulation data
        
    Returns:
        Image: PIL Image object containing cover page
    """
    cover_img = Image.new('RGB', (pdf_width, pdf_height), 'white')
    draw = ImageDraw.Draw(cover_img)
    
    # Calculate scaling factor (reference: 816px standard letter width)
    scale_factor = pdf_width / 816.0
    
    try:
        title_font_size = int(28 * scale_factor)
        text_font_size = int(12 * scale_factor)
        table_font_size = int(10 * scale_factor)
        
        title_font = ImageFont.truetype("arial.ttf", title_font_size)
        text_font = ImageFont.truetype("arial.ttf", text_font_size)
        table_font = ImageFont.truetype("arial.ttf", table_font_size)
    except:
        title_font = ImageFont.load_default()
        text_font = ImageFont.load_default()
        table_font = ImageFont.load_default()
    
    # Dynamic layout parameters
    left_margin = int(30 * scale_factor)
    top_margin = int(20 * scale_factor)
    line_spacing = int(30 * scale_factor)
    table_padding = int(6 * scale_factor)
    table_row_height = int(22 * scale_factor)
    table_header_height = int(28 * scale_factor)
    
    # Draw title
    draw.text((left_margin, top_margin), f"CFD Visualization Report - Run {next_run_num}",
            fill="black", font=title_font)
    
    # Draw summary info section
    y_offset = top_margin + int(line_spacing * 1.3)
    info_sections = [
        f"Input File: {run_settings['Input File']}",
        f"Regions: {', '.join(run_settings['Regions'])}",
        f"Variables: {', '.join(run_settings['Variables'])}",
        f"Report Date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    ]
    
    for info in info_sections:
        draw.text((left_margin, y_offset), info, fill="black", font=text_font)
        y_offset += line_spacing
    
    # Draw data table
    y_offset += int(line_spacing * 0.5)
    table_y = y_offset
    table_width = pdf_width - (2 * left_margin)
    
    # Table header
    draw.rectangle(
        [left_margin, table_y, pdf_width - left_margin, table_y + table_header_height],
        fill=(200, 200, 200), outline=(0, 0, 0), width=int(1 * scale_factor)
    )
    
    col1_x = left_margin + table_padding
    col2_x = int(left_margin + table_width * 0.4)
    
    draw.text((col1_x, table_y + int(table_padding * 1.2)), "Parameter",
            fill="black", font=table_font)
    draw.text((col2_x, table_y + int(table_padding * 1.2)), "Value",
            fill="black", font=table_font)
    
    table_y += table_header_height
    
    # Table data rows
    for idx, (key, val) in enumerate(cfd_data.items()):
        row_fill = (245, 245, 245) if idx % 2 == 0 else (255, 255, 255)
        
        draw.rectangle(
            [left_margin, table_y, pdf_width - left_margin, table_y + table_row_height],
            fill=row_fill, outline=(220, 220, 220), width=int(1 * scale_factor)
        )
        
        draw.text((col1_x, table_y + int(table_padding * 0.6)), str(key),
                fill="black", font=table_font)
        draw.text((col2_x, table_y + int(table_padding * 0.6)), str(val),
                fill="black", font=table_font)
        
        table_y += table_row_height
    
    return cover_img


def generate_pdf_report(run_dir, next_run_num, output_resolution, config, run_settings, cfd_data, all_generated_images):
    """
    Generate complete PDF report with cover page and image appendix.
    
    Args:
        run_dir (str): Output directory
        next_run_num (int): Run number
        output_resolution (list): Output image resolution
        config (dict): Configuration dictionary
        run_settings (dict): Run settings
        cfd_data (dict): CFD data
        all_generated_images (list): List of image paths
    """
    try:
        print("\n[INFO] Compiling PDF Report...")
        pdf_path = os.path.join(run_dir, f"Run_{next_run_num}_Report.pdf")
        
        # Get PDF resolution from config or use default
        if config and "pdf_resolution" in config:
            pdf_resolution = config["pdf_resolution"]
        else:
            pdf_resolution = [816, 1056]
        
        PDF_WIDTH, PDF_HEIGHT = pdf_resolution[0], pdf_resolution[1]
        
        print(f"[INFO] PDF page size: {PDF_WIDTH}x{PDF_HEIGHT} pixels")
        
        # Create cover page
        cover_img = create_pdf_cover_page(PDF_WIDTH, PDF_HEIGHT, next_run_num, run_settings, cfd_data)
        
        # Append all generated screenshots
        pdf_pages = []
        for img_path in all_generated_images:
            if os.path.exists(img_path):
                with Image.open(img_path) as img:
                    img_rgb = img.convert('RGB')
                    img_rgb.thumbnail((PDF_WIDTH, PDF_HEIGHT), Image.Resampling.LANCZOS)
                    
                    # Create white page and center image
                    page = Image.new('RGB', (PDF_WIDTH, PDF_HEIGHT), 'white')
                    x_offset = (PDF_WIDTH - img_rgb.width) // 2
                    y_offset = (PDF_HEIGHT - img_rgb.height) // 2
                    page.paste(img_rgb, (x_offset, y_offset))
                    
                    pdf_pages.append(page)
        
        # Save PDF
        if pdf_pages:
            cover_img.save(pdf_path, save_all=True, append_images=pdf_pages)
        
        # Clean up individual images
        for img_path in all_generated_images:
            if os.path.exists(img_path):
                try:
                    os.remove(img_path)
                except:
                    pass
        
        print(f"[SUCCESS] Generated Multi-page PDF Report: {pdf_path}")
        print(f"\n--- DONE ---")
    
    except Exception as e:
        print(f"\n[WARNING] PDF generation failed: {e}")


# ================================================================
# 7. MAIN EXECUTION
# ================================================================

def main():
    """Main execution flow for CFD visualizer."""
    
    # Check if config file was passed as command line argument
    config_file = None
    if len(sys.argv) > 1:
        config_file = sys.argv[1]
        print(f"[INFO] Using config file from command line: {config_file}")
    
    # Load configuration (with optional command line argument)
    config, input_file, output_resolution = load_config(config_file)
    
    # Get zoom settings
    zoom_factor, zoom_center = get_zoom_settings(config)
    
    # Setup output directories
    case_dir = os.path.dirname(input_file)
    file_extension = os.path.splitext(input_file)[1].lower()
    results_dir, run_dir, next_run_num = setup_output_directories(case_dir)
    
    print(f"========================================================")
    print(f"[INFO] ALL FILES WILL BE SAVED TO: \n{run_dir}")
    print(f"========================================================\n")
    
    # Initialize data structures
    run_settings = {"Input File": input_file, "Regions": [], "Variables": [],
                   "Region_Slices": {}, "Iso_Surfaces": []}
    cfd_data = {
        "C_D": "N/A", "C_L": "N/A", "Reference Area": "N/A",
        "Iterations / Time": "N/A", "Solver Version": "N/A",
        "Run Date": "N/A", "Cell Count": "N/A"
    }
    all_generated_images = []
    
    # Extract OpenFOAM metadata if applicable
    if file_extension in ['.foam', '.openfoam', '.simplefoam']:
        extract_openfoam_metadata(case_dir, cfd_data, run_dir, next_run_num, output_resolution, all_generated_images)
    
    # Load mesh and select regions
    reader, selected_regions, is_openfoam = load_and_select_regions(input_file, config, file_extension)
    run_settings["Regions"] = selected_regions
    
    # Get available variables and select those to plot
    avail_points, avail_cells, available_vars, temp_merged = get_available_variables(reader)
    raw_vars, variables_to_plot = select_variables(config, available_vars)
    
    # Get iso-surface configurations
    iso_configs = select_iso_surfaces(config, available_vars)
    
    # Update run settings with iso-surface info
    for iso in iso_configs:
        run_settings["Iso_Surfaces"].append(
            f"{iso['var']}={iso['val']}" + (f" (Color: {iso['color']})" if iso['color'] else " (Solid)")
        )
        if iso['var'] not in variables_to_plot:
            variables_to_plot.append(iso['var'])
        if iso['color'] and iso['color'] not in variables_to_plot:
            variables_to_plot.append(iso['color'])
    
    # Set reader arrays
    if hasattr(reader, 'PointArrays') and avail_points:
        reader.PointArrays = [v for v in variables_to_plot if v in avail_points]
    if hasattr(reader, 'CellArrays') and avail_cells:
        reader.CellArrays = [v for v in variables_to_plot if v in avail_cells]
    
    run_settings["Variables"] = variables_to_plot
    
    # Get cell count
    try:
        num_cells = temp_merged.GetDataInformation().GetNumberOfCells()
        if num_cells > 0:
            cfd_data["Cell Count"] = f"{num_cells:,}"
    except Exception as e:
        print(f"[WARNING] Could not get cell count: {e}")
    
    merged_generic = temp_merged if not is_openfoam else None
    
    # Setup render view
    renderView = GetActiveView() or CreateView('RenderView')
    renderView.ViewSize = output_resolution
    renderView.Background = [.4, .4, .4]
    renderView.UseColorPaletteForBackground = 0
    try:
        renderView.AntiAliasing = 'FXAA'
    except AttributeError:
        pass
    
    # Process each region
    for region_name in selected_regions:
        region_data = process_region(renderView, reader, region_name, config, is_openfoam,
                                    variables_to_plot, raw_vars, run_dir, next_run_num,
                                    output_resolution, zoom_factor, zoom_center,
                                    all_generated_images, merged_generic)
        
        if file_extension in ['.foam', '.openfoam', '.simplefoam']:
            Delete(region_data)
    
    # Process iso-surfaces if configured
    if iso_configs:
        if is_openfoam:
            current_regions = list(reader.MeshRegions)
            if 'internalMesh' not in current_regions:
                reader.MeshRegions = current_regions + ['internalMesh']
                reader.UpdatePipeline()
            iso_base = MergeBlocks(Input=reader)
            iso_base.UpdatePipeline()
        else:
            iso_base = merged_generic
        
        bounds = iso_base.GetDataInformation().GetBounds()
        cx, cy, cz = ((bounds[0] + bounds[1]) / 2.0, (bounds[2] + bounds[3]) / 2.0, (bounds[4] + bounds[5]) / 2.0)
        domain_diagonal = math.sqrt((bounds[1] - bounds[0]) ** 2 + (bounds[3] - bounds[2]) ** 2 + (bounds[5] - bounds[4]) ** 2)
        cam_dist = max(domain_diagonal * 1.5, 0.1)
        
        for iso_settings in iso_configs:
            print(f"\nPROCESSING: Iso-Surface ({iso_settings['var']} = {iso_settings['val']})")
            
            base_cell_vars = list(iso_base.CellData.keys())
            data_for_contour = iso_base
            c2p_filter = None
            
            if iso_settings['var'] in base_cell_vars or (iso_settings['color'] and iso_settings['color'] in base_cell_vars):
                c2p_filter = CellDatatoPointData(Input=iso_base)
                data_for_contour = c2p_filter
            
            iso_filter = Contour(Input=data_for_contour)
            iso_filter.ContourBy = ['POINTS', iso_settings['var']]
            iso_filter.Isosurfaces = [iso_settings['val']]
            iso_filter.ComputeNormals = 1
            iso_filter.UpdatePipeline()
            
            HideAll(renderView)
            outline = Outline(Input=iso_base)
            out_disp = Show(outline, renderView)
            out_disp.AmbientColor, out_disp.DiffuseColor = [0, 0, 0], [0, 0, 0]
            out_disp.LineWidth = 2.0
            
            iso_display = Show(iso_filter, renderView)
            iso_display.Representation = 'Surface'
            
            if iso_settings['color']:
                ColorBy(iso_display, ('POINTS', iso_settings['color']))
                iso_display.RescaleTransferFunctionToDataRange(True, False)
                iso_display.SetScalarBarVisibility(renderView, True)
            else:
                ColorBy(iso_display, None)
                iso_display.DiffuseColor = [0.8, 0.4, 0.4]
            
            views_to_take = [("front", [1, 0, 0], [0, 0, 1]), ("side", [0, 1, 0], [0, 0, 1]),
                           ("top", [0, 0, 1], [1, 0, 0]), ("front_iso", [1, 1, 1], [0, 0, 1]),
                           ("rear_iso", [-1, 1, 1], [0, 0, 1])]
            color_suffix = iso_settings['color'] if iso_settings['color'] else "SolidColor"
            
            for v_name, c_pos, c_up in views_to_take:
                snap_view(renderView, f"{iso_settings['val']}_ColoredBy_{color_suffix}_{v_name}",
                        c_pos, c_up, f"IsoSurface_{iso_settings['var']}", [cx, cy, cz], cam_dist,
                        run_dir, next_run_num, output_resolution, zoom_factor, zoom_center, all_generated_images)
                add_iso_info_overlay(all_generated_images[-1], iso_settings)
            
            iso_display.SetScalarBarVisibility(renderView, False)
            iso_pvd_path = os.path.join(run_dir, f"Run_{next_run_num}_IsoSurface_{iso_settings['var']}_{iso_settings['val']}.pvd")
            SaveData(iso_pvd_path, proxy=iso_filter)
            flatten_pvd(iso_pvd_path)
            
            Delete(iso_filter)
            Delete(outline)
            if c2p_filter:
                Delete(c2p_filter)
        
        if file_extension in ['.foam', '.openfoam', '.simplefoam']:
            Delete(iso_base)
    
    # Export ParaView state
    state_path = os.path.join(run_dir, f"Run_{next_run_num}_state.pvsm")
    SaveState(state_path)
    print(f"\n[INFO] Saved ParaView state to: {state_path}")
    
    # Generate PDF report
    generate_pdf_report(run_dir, next_run_num, output_resolution, config, run_settings, cfd_data, all_generated_images)


if __name__ == "__main__":
    main()