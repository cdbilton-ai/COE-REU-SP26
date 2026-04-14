"""
Multi-Format CFD Visualizer - BATCH EDITION (v3.0 - PDF Output)
Supports: OpenFOAM & ANSYS EnSight
Features: JSON Automation, 4K High-Res, Native Graphs, PDF Report, State Export, Dynamic Camera, Zoom Center
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
# 1. SETUP, DIRECTORY & JSON MANAGEMENT
# ================================================================
raw_path = input("Drag and drop your CFD file OR a .json config file here > ").strip(' "\'')
initial_path = os.path.abspath(raw_path)

config = None
output_resolution = [1920, 1080]
iso_configs = []
zoom_center = None  # NEW: zoom center point

if initial_path.lower().endswith('.json'):
    print(f"\n[INFO] Loading configuration from JSON: {initial_path}")
    try:
        with open(initial_path, 'r') as f:
            config = json.load(f)
        input_file = os.path.abspath(config.get("input_file", ""))
        output_resolution = config.get("resolution", [3840, 2160])
        zoom_center = config.get("zoom_center", None)  # NEW: read zoom center from JSON
    except Exception as e:
        print(f"[ERROR] Failed to parse JSON config: {e}")
        sys.exit(1)
else:
    input_file = initial_path

zoom_factor = 1.0
if config and "zoom_factor" in config:
    zoom_factor = float(config.get("zoom_factor", 1.0))
elif not config:
    try:
        user_zoom = input("\nEnter Zoom Factor (1.0 = Fit to Screen, 1.5 = Zoom In, 0.5 = Zoom Out) [Default 1.0] > ").strip()
        if user_zoom: zoom_factor = float(user_zoom)
    except ValueError:
        print("[WARNING] Invalid zoom factor. Defaulting to 1.0 (Fit to Screen).")


print(f"[INFO] Attempting to load: {input_file}")

if not os.path.exists(input_file):
    print(f"[ERROR] File not found on disk: {input_file}")
    sys.exit(1)

case_dir = os.path.dirname(input_file)
file_extension = os.path.splitext(input_file)[1].lower()

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

print(f"========================================================")
print(f"[INFO] ALL FILES WILL BE SAVED TO: \n{run_dir}")
print(f"========================================================\n")

run_settings = {"Input File": input_file, "Regions": [], "Variables": [], "Region_Slices": {}, "Iso_Surfaces": []}
cfd_data = {
    "C_D": "N/A", "C_L": "N/A", "Reference Area": "N/A", 
    "Iterations / Time": "N/A", "Solver Version": "N/A", 
    "Run Date": "N/A", "Cell Count": "N/A"
}
all_generated_images = []

# ================================================================
# 1.B HELPER FUNCTIONS 
# ================================================================
def flatten_pvd(pvd_path):
    if not os.path.exists(pvd_path): return
    try:
        tree = ET.parse(pvd_path)
        root = tree.getroot()
        base_dir = os.path.dirname(pvd_path)
        data_dir_name = os.path.splitext(os.path.basename(pvd_path))[0]
        data_dir_path = os.path.join(base_dir, data_dir_name)
        
        if not os.path.exists(data_dir_path): return
        
        for item in os.listdir(data_dir_path):
            src_path = os.path.join(data_dir_path, item)
            dst_path = os.path.join(base_dir, item)
            if not os.path.exists(dst_path): shutil.move(src_path, dst_path)
        
        modified = False
        for dataset in root.iter('DataSet'):
            file_rel_path = dataset.get('file')
            if file_rel_path:
                dataset.set('file', os.path.basename(file_rel_path.replace('\\', '/')))
                modified = True
                
        if modified: tree.write(pvd_path, encoding='utf-8', xml_declaration=True)
        if not os.listdir(data_dir_path): os.rmdir(data_dir_path)
    except Exception as e:
        print(f"[WARNING] Could not flatten PVD structure: {e}")

def add_iso_info_overlay(img_path, iso_settings):
    try:
        with Image.open(img_path) as img:
            draw = ImageDraw.Draw(img)
            width, height = img.size
            font_size = max(int(width * 0.018), 20)
            
            try: font = ImageFont.truetype("arial.ttf", font_size) 
            except Exception: font = ImageFont.load_default()

            geom_text = f"Iso-Geometry : {iso_settings['var']} = {iso_settings['val']}"
            color_text = f"Coloring By  : {iso_settings['color'] if iso_settings['color'] else 'Solid Color'}"
            
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

            box_padding = int(font_size * 0.6)
            box_w = max_w + (2 * box_padding)
            box_h = (line_height * 2) + (2 * box_padding) - int(font_size * 0.3)
            pos_x, pos_y = int(width * 0.03), int(height * 0.05) 

            overlay = Image.new('RGBA', img.size, (255, 255, 255, 0))
            overlay_draw = ImageDraw.Draw(overlay)
            
            box_rect = [pos_x, pos_y, pos_x + box_w, pos_y + box_h]
            overlay_draw.rectangle(box_rect, fill=(255, 255, 255, 200), outline=(0, 0, 0, 255), width=max(2, int(font_size*0.1)))
            overlay_draw.text((pos_x + box_padding, pos_y + box_padding), geom_text, fill=(0, 0, 0, 255), font=font)
            overlay_draw.text((pos_x + box_padding, pos_y + box_padding + line_height), color_text, fill=(0, 0, 0, 255), font=font)
            img.paste(overlay, (0,0), overlay)
            img.convert('RGB').save(img_path)
    except Exception as e:
        print(f"[WARNING] Failed to add overlay: {e}")

renderView = GetActiveView() or CreateView('RenderView')
renderView.ViewSize = output_resolution

# DYNAMIC CAMERA UPDATE WITH ZOOM AND ZOOM CENTER
def snap_view(file_suffix, camera_pos, view_up, prefix_name, focal_point, cam_dist):
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

# ================================================================
# 2. METADATA EXTRACTION & NATIVE GRAPH GENERATION
# ================================================================
if file_extension in ['.foam', '.openfoam', '.simplefoam']:
    log_files = [f for f in os.listdir(case_dir) if f.startswith('log.') and 'checkMesh' not in f]
    if log_files and os.path.exists(os.path.join(case_dir, log_files[0])):
        with open(os.path.join(case_dir, log_files[0]), 'r') as f:
            lines = f.readlines()
            for line in lines[:50]:
                if line.startswith('Build'): cfd_data["Solver Version"] = line.split(':', 1)[1].strip()
                elif line.startswith('Date'): cfd_data["Run Date"] = line.split(':', 1)[1].strip()

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
                                            except ValueError: pass
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
                                except Exception as e: print(f"[WARNING] Matplotlib graphing failed: {e}")
                    except Exception as e: print(f"[WARNING] Error reading force file: {e}")

# ================================================================
# 3. MESH LOADING & REGION SELECTION
# ================================================================
selected_regions = []
reader = None
is_openfoam = file_extension in ['.foam', '.openfoam', '.simplefoam']

if is_openfoam:
    reader = OpenFOAMReader(FileName=input_file)
    reader.UpdatePipelineInformation() 
    available_regions = list(reader.MeshRegions.Available)
    
    if config and "regions" in config:
        selected_regions = [r for r in config["regions"] if r in available_regions]
    else:
        for i, reg in enumerate(available_regions): print(f"  {i}: {reg}")
        val = input("\nEnter region NUMBERS to analyze (e.g., 0, 3) > ").strip()
        if val:
            for v in val.split(','):
                try: selected_regions.append(available_regions[int(v.strip())])
                except (ValueError, IndexError): pass
    reader.MeshRegions = selected_regions if selected_regions else ['internalMesh']
else:
    reader = OpenDataFile(input_file)
    reader.UpdatePipelineInformation()
    selected_regions = ['Imported_Domain'] 

run_settings["Regions"] = selected_regions

# ================================================================
# 4. VARIABLE & ISO-SURFACE SELECTION 
# ================================================================
reader.UpdatePipeline()
temp_merged = MergeBlocks(Input=reader)
temp_merged.UpdatePipeline()

avail_points = list(temp_merged.PointData.keys())
avail_cells = list(temp_merged.CellData.keys())
available_vars = list(set(avail_points + avail_cells))

raw_vars = []
if available_vars:
    if config and "variables" in config:
        raw_vars = config["variables"]
    else:
        print("\nAvailable variables:")
        for var in sorted(available_vars): print(f"  - {var}")
        raw_vars = [v.strip() for v in input("\nEnter variables to plot (comma-separated) > ").split(',')]
        
variables_to_plot = [v for v in raw_vars if v in available_vars]

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
        if want_iso != 'y': break
        iso_var = input("Enter variable to contour by (e.g., p, U) > ").strip()
        if iso_var in available_vars:
            try:
                iso_val = float(input(f"Enter Iso-value for '{iso_var}' > ").strip())
                iso_color = input("Variable to color it by? (Press Enter for solid) > ").strip()
                iso_color = iso_color if iso_color in available_vars else None
                iso_configs.append({'var': iso_var, 'val': iso_val, 'color': iso_color})
            except ValueError: print("Invalid value. Skipping.")

for iso in iso_configs:
    run_settings["Iso_Surfaces"].append(f"{iso['var']}={iso['val']}" + (f" (Color: {iso['color']})" if iso['color'] else " (Solid)"))
    if iso['var'] not in variables_to_plot: variables_to_plot.append(iso['var'])
    if iso['color'] and iso['color'] not in variables_to_plot: variables_to_plot.append(iso['color'])

if hasattr(reader, 'PointArrays') and avail_points: reader.PointArrays = [v for v in variables_to_plot if v in avail_points]
if hasattr(reader, 'CellArrays') and avail_cells: reader.CellArrays = [v for v in variables_to_plot if v in avail_cells]

run_settings["Variables"] = variables_to_plot

try:
    num_cells = temp_merged.GetDataInformation().GetNumberOfCells()
    if num_cells > 0: cfd_data["Cell Count"] = f"{num_cells:,}"
except Exception as e: print(f"[WARNING] Could not get cell count: {e}")

merged_generic = temp_merged if not is_openfoam else None

# ================================================================
# 5. HIGH-RES RENDERING & SCREENSHOT GENERATION
# ================================================================
renderView.Background = [.4, .4, .4] 
renderView.UseColorPaletteForBackground = 0
try: renderView.AntiAliasing = 'FXAA'
except AttributeError: pass

for region_name in selected_regions:
    print(f"\nPROCESSING: {region_name}")
    
    if is_openfoam:
        reader.MeshRegions = [region_name]
        reader.UpdatePipeline()
        region_data = MergeBlocks(Input=reader)
        region_data.UpdatePipeline()
        is_boundary = 'patch' in region_name.lower()
    else:
        region_data, is_boundary = merged_generic, False

    bounds = region_data.GetDataInformation().GetBounds()
    cx, cy, cz = (bounds[0]+bounds[1])/2.0, (bounds[2]+bounds[3])/2.0, (bounds[4]+bounds[5])/2.0
    
    domain_diagonal = math.sqrt((bounds[1]-bounds[0])**2 + (bounds[3]-bounds[2])**2 + (bounds[5]-bounds[4])**2)
    cam_dist = max(domain_diagonal * 2.5, 0.1) 
    
    slice_axis = ""
    slice_offsets = []
    
    if is_boundary:
        run_settings["Region_Slices"][region_name] = "None (3D)"
        slice_offsets = [0]
    else:
        if config and "slices" in config and region_name in config["slices"]:
            slice_cfg = config["slices"][region_name]
            if isinstance(slice_cfg, dict):
                slice_axis = slice_cfg.get("axis", "").lower()
                b_min = bounds[0] if slice_axis=='x' else (bounds[2] if slice_axis=='y' else bounds[4])
                b_max = bounds[1] if slice_axis=='x' else (bounds[3] if slice_axis=='y' else bounds[5])
                margin = (b_max - b_min) * 0.02 
                
                user_min = float(slice_cfg.get("min", b_min + margin))
                user_max = float(slice_cfg.get("max", b_max - margin))
                
                s_min = max(b_min + margin, min(b_max - margin, user_min))
                s_max = max(b_min + margin, min(b_max - margin, user_max))
                s_count = int(slice_cfg.get("count", 1))
                
                if s_count > 1:
                    step = (s_max - s_min) / (s_count - 1)
                    slice_offsets = [s_min + (i * step) for i in range(s_count)]
                else:
                    slice_offsets = [(s_min + s_max) / 2.0]
            else:
                slice_axis = str(slice_cfg).lower()
                slice_offsets = [cx if slice_axis=='x' else (cy if slice_axis=='y' else cz)]
        elif not config:
            slice_axis = input(f"Take 2D slice of '{region_name}'? (x/y/z or Enter for 3D) > ").strip().lower()
            if slice_axis in ['x', 'y', 'z']: slice_offsets = [cx if slice_axis=='x' else (cy if slice_axis=='y' else cz)]
            else: slice_offsets = [0]

        if slice_axis in ['x', 'y', 'z']:
            print(f"\n[INFO] Starting Slices for {region_name} along {slice_axis.upper()}-axis")
            run_settings["Region_Slices"][region_name] = f"{slice_axis.upper()}-Normal ({len(slice_offsets)} slices)"
            
            slice_input = region_data
            if not is_openfoam:
                try:
                    slice_input = CellDataToPointData(Input=region_data)
                    slice_input.ProcessAllArrays = 1
                    slice_input.UpdatePipeline()
                except Exception as e:
                    pass

            Hide(region_data, renderView)

            slice_pt_vars = list(slice_input.PointData.keys())
            slice_cell_vars = list(slice_input.CellData.keys())

            for var in variables_to_plot:
                
                if var not in slice_pt_vars and var not in slice_cell_vars:
                    continue

                for i, offset in enumerate(slice_offsets):

                    slc = Slice(Input=slice_input)
                    slc.SliceType = 'Plane'
                    
                    if slice_axis == 'x':
                        slc.SliceType.Normal = [1.0, 0.0, 0.0]
                        slc.SliceType.Origin = [offset, cy, cz]
                        cam_pos, view_up = [1, 0, 0], [0, 0, 1]
                    elif slice_axis == 'y':
                        slc.SliceType.Normal = [0.0, 1.0, 0.0]
                        slc.SliceType.Origin = [cx, offset, cz]
                        cam_pos, view_up = [0, 1, 0], [0, 0, 1]
                    elif slice_axis == 'z':
                        slc.SliceType.Normal = [0.0, 0.0, 1.0]
                        slc.SliceType.Origin = [cx, cy, offset]
                        cam_pos, view_up = [0, 0, 1], [0, 1, 0]
                    
                    slc.UpdatePipeline()
                    slc_display = Show(slc, renderView)
                        
                    try:
                        if var in slice_pt_vars: ColorBy(slc_display, ('POINTS', var))
                        else: ColorBy(slc_display, ('CELLS', var))
                            
                        slc_display.SetScalarBarVisibility(renderView, True)
                        slc_display.RescaleTransferFunctionToDataRange(True, False)
                    except Exception as e:
                        pass

                    suffix = f"Slice_{slice_axis.upper()}{i+1}_{var}"
                    print(f"  -> Snapping image: {suffix}")
                    
                    snap_view(suffix, cam_pos, view_up, region_name, [cx, cy, cz], cam_dist)
                    
                    Hide(slc, renderView)
                    Delete(slc)
            
            Show(region_data, renderView)
            print(f"[INFO] Finished slicing {region_name}.")

    pvd_export_path = os.path.join(run_dir, f"Run_{next_run_num}_{region_name.replace('/', '_')}_summary.pvd")
    SaveData(pvd_export_path, proxy=region_data)
    flatten_pvd(pvd_export_path)

    if is_boundary or slice_axis not in ['x', 'y', 'z']:
        HideAll(renderView)
        display = Show(region_data, renderView)
        display.Representation = 'Surface'

        region_point_vars, region_cell_vars = list(region_data.PointData.keys()), list(region_data.CellData.keys())
        
        for var in variables_to_plot:
            if var not in raw_vars: continue 
            if var in region_point_vars: ColorBy(display, ('POINTS', var))
            elif var in region_cell_vars: ColorBy(display, ('CELLS', var))
            else: continue
            
            display.RescaleTransferFunctionToDataRange(True, False)
            display.SetScalarBarVisibility(renderView, True)

            views_to_take = [("front", [1,0,0], [0,0,1]), ("side", [0,1,0], [0,0,1]), ("top", [0,0,1], [1,0,0]), ("front_iso", [1,1,1], [0,0,1]), ("rear_iso", [-1,1,1], [0,0,1])]

            for v_name, c_pos, c_up in views_to_take: 
                snap_view(f"{var}_{v_name}", c_pos, c_up, region_name, [cx, cy, cz], cam_dist)
            
            display.SetScalarBarVisibility(renderView, False)
    
    if file_extension in ['.foam', '.openfoam', '.simplefoam']: Delete(region_data)

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
    cx, cy, cz = (bounds[0]+bounds[1])/2.0, (bounds[2]+bounds[3])/2.0, (bounds[4]+bounds[5])/2.0
    domain_diagonal = math.sqrt((bounds[1]-bounds[0])**2 + (bounds[3]-bounds[2])**2 + (bounds[5]-bounds[4])**2)
    cam_dist = max(domain_diagonal * 1.5, 0.1)

    for idx, iso_settings in enumerate(iso_configs):
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

        views_to_take = [("front", [1,0,0], [0,0,1]), ("side", [0,1,0], [0,0,1]), ("top", [0,0,1], [1,0,0]), ("front_iso", [1,1,1], [0,0,1]), ("rear_iso", [-1,1,1], [0,0,1])]
        color_suffix = iso_settings['color'] if iso_settings['color'] else "SolidColor"
        
        for v_name, c_pos, c_up in views_to_take:
            snap_view(f"{iso_settings['val']}_ColoredBy_{color_suffix}_{v_name}", c_pos, c_up, f"IsoSurface_{iso_settings['var']}", [cx, cy, cz], cam_dist)
            add_iso_info_overlay(all_generated_images[-1], iso_settings)
            
        iso_display.SetScalarBarVisibility(renderView, False)
        iso_pvd_path = os.path.join(run_dir, f"Run_{next_run_num}_IsoSurface_{iso_settings['var']}_{iso_settings['val']}.pvd")
        SaveData(iso_pvd_path, proxy=iso_filter)
        flatten_pvd(iso_pvd_path)
        
        Delete(iso_filter)
        Delete(outline)
        if c2p_filter: Delete(c2p_filter)

    if file_extension in ['.foam', '.openfoam', '.simplefoam']: Delete(iso_base)

# ================================================================
# 6. EXPORT STATE & GENERATE PDF REPORT
# ================================================================

# EXPORT PARAVIEW STATE
state_path = os.path.join(run_dir, f"Run_{next_run_num}_state.pvsm")
SaveState(state_path)
print(f"\n[INFO] Saved ParaView state to: {state_path}")

try:
    print("\n[INFO] Compiling PDF Report...")
    pdf_path = os.path.join(run_dir, f"Run_{next_run_num}_Report.pdf")
    
    # Get PDF resolution from config, or use default standard PDF size
    if config and "pdf_resolution" in config:
        pdf_resolution = config["pdf_resolution"]
    else:
        pdf_resolution = [816, 1056]
    
    PDF_WIDTH, PDF_HEIGHT = pdf_resolution[0], pdf_resolution[1]
    
    print(f"[INFO] PDF page size: {PDF_WIDTH}x{PDF_HEIGHT} pixels")
    
    # Create the Cover Page with dynamic scaling based on PDF resolution
    cover_img = Image.new('RGB', (PDF_WIDTH, PDF_HEIGHT), 'white')
    draw = ImageDraw.Draw(cover_img)
    
    # Calculate all scaling factors based on PDF width (reference: 816px = 8.5")
    scale_factor = PDF_WIDTH / 816.0
    
    try:
        # Scale font sizes dynamically based on PDF width - SMALLER sizes
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
    
    # Dynamic margins and spacing based on PDF width (all proportional to scale)
    left_margin = int(30 * scale_factor)
    top_margin = int(20 * scale_factor)
    line_spacing = int(30 * scale_factor)
    table_padding = int(6 * scale_factor)
    table_row_height = int(22 * scale_factor)
    table_header_height = int(28 * scale_factor)
    
    # Title
    draw.text((left_margin, top_margin), f"CFD Visualization Report - Run {next_run_num}", 
              fill="black", font=title_font)
    
    # Summary info section
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
    
    # Data table
    y_offset += int(line_spacing * 0.5)
    table_y = y_offset
    table_width = PDF_WIDTH - (2 * left_margin)
    
    # Table header background
    draw.rectangle(
        [left_margin, table_y, PDF_WIDTH - left_margin, table_y + table_header_height],
        fill=(200, 200, 200), outline=(0, 0, 0), width=int(1 * scale_factor)
    )
    
    # Table header text - split into Parameter and Value columns
    col1_x = left_margin + table_padding
    col2_x = int(left_margin + table_width * 0.4)
    
    draw.text((col1_x, table_y + int(table_padding * 1.2)), "Parameter", 
              fill="black", font=table_font)
    draw.text((col2_x, table_y + int(table_padding * 1.2)), "Value", 
              fill="black", font=table_font)
    
    table_y += table_header_height
    
    # Table data rows with alternating background colors
    for idx, (key, val) in enumerate(cfd_data.items()):
        # Alternate row background
        if idx % 2 == 0:
            row_fill = (245, 245, 245)
        else:
            row_fill = (255, 255, 255)
        
        draw.rectangle(
            [left_margin, table_y, PDF_WIDTH - left_margin, table_y + table_row_height],
            fill=row_fill, outline=(220, 220, 220), width=int(1 * scale_factor)
        )
        
        # Truncate text if too long
        key_text = str(key)
        val_text = str(val)
        
        draw.text((col1_x, table_y + int(table_padding * 0.6)), key_text, 
                  fill="black", font=table_font)
        draw.text((col2_x, table_y + int(table_padding * 0.6)), val_text, 
                  fill="black", font=table_font)
        
        table_y += table_row_height
    
    # Append all generated screenshots into the PDF array with standardized sizing
    pdf_pages = []
    for img_path in all_generated_images:
        if os.path.exists(img_path):
            with Image.open(img_path) as img:
                # Resize image to fit PDF page while maintaining aspect ratio
                img_rgb = img.convert('RGB')
                img_rgb.thumbnail((PDF_WIDTH, PDF_HEIGHT), Image.Resampling.LANCZOS)
                
                # Create a white background page
                page = Image.new('RGB', (PDF_WIDTH, PDF_HEIGHT), 'white')
                # Center the resized image on the page
                x_offset = (PDF_WIDTH - img_rgb.width) // 2
                y_offset_img = (PDF_HEIGHT - img_rgb.height) // 2
                page.paste(img_rgb, (x_offset, y_offset_img))
                
                pdf_pages.append(page)
                
    # Bind them all into a single file!
    if pdf_pages:
        cover_img.save(pdf_path, save_all=True, append_images=pdf_pages)
        
    # Final Cleanup: Delete the loose PNGs now that they are bound in the PDF
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