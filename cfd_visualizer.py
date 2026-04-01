"""
Multi-Format CFD Visualizer - BATCH EDITION
Supports: OpenFOAM & ANSYS EnSight
Features: JSON Automation, 4K High-Res, Native Graphs, PDF binding, Info-Box Overlays!
"""

from paraview.simple import *
import os
import sys
import re
import shutil
import xml.etree.ElementTree as ET
import json

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("[ERROR] Required library 'Pillow' is not installed in ParaView.")
    sys.exit(1)

# ================================================================
# 1. SETUP, DIRECTORY & JSON MANAGEMENT
# ================================================================
raw_path = input("Drag and drop your CFD file OR a .json config file here > ").strip(' "\'')
initial_path = os.path.abspath(raw_path)

config = None
output_resolution = [1920, 1080]

if initial_path.lower().endswith('.json'):
    print(f"\n[INFO] Loading configuration from JSON: {initial_path}")
    with open(initial_path, 'r') as f:
        config = json.load(f)
    input_file = os.path.abspath(config.get("input_file", ""))
    output_resolution = config.get("resolution", [3840, 2160]) # Default to 4K if using JSON
else:
    input_file = initial_path

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
    if match: run_numbers.append(int(match.group(1)))
next_run_num = max(run_numbers) + 1

run_dir = os.path.join(results_dir, f"Run_{next_run_num}")
os.makedirs(run_dir, exist_ok=True)

print(f"========================================================")
print(f"[INFO] ALL FILES WILL BE SAVED TO: \n{run_dir}")
print(f"========================================================\n")

run_settings = {"Input File": input_file, "Regions": [], "Variables": [], "Region_Slices": {}, "Iso_Surface": "None"}
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
        img = Image.open(img_path)
        draw = ImageDraw.Draw(img)
        width, height = img.size

        # Dynamic Font Scaling based on image resolution
        font_size = max(int(width * 0.018), 20)
        try: font = ImageFont.truetype("arial.ttf", font_size) 
        except: font = ImageFont.load_default()

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
        overlay_draw.rectangle(box_rect, fill=(255, 255, 255, 200))
        overlay_draw.rectangle(box_rect, outline=(0, 0, 0, 255), width=max(2, int(font_size*0.1)))

        overlay_draw.text((pos_x + box_padding, pos_y + box_padding), geom_text, fill=(0, 0, 0, 255), font=font)
        overlay_draw.text((pos_x + box_padding, pos_y + box_padding + line_height), color_text, fill=(0, 0, 0, 255), font=font)

        img.paste(overlay, (0,0), overlay)
        img.convert('RGB').save(img_path)
    except Exception as e:
        print(f"[WARNING] Failed to add overlay: {e}")

def snap_view(file_suffix, camera_pos, view_up, prefix_name):
    ResetCamera()
    c = renderView.CameraFocalPoint
    renderView.CameraPosition = [c[0]+camera_pos[0]*100, c[1]+camera_pos[1]*100, c[2]+camera_pos[2]*100]
    renderView.CameraFocalPoint = c
    renderView.CameraViewUp = view_up
    ResetCamera()
    Render()
    f_path = os.path.join(run_dir, f"Run_{next_run_num}_{prefix_name.replace('/', '_')}_{file_suffix}.png")
    # Using explicit resolution override for high-quality screenshots
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
                        if match: cfd_data["Reference Area"] = match.group(1); break

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
                                            except: pass
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
                                        # Match graph DPI to output scale
                                        dpi_scale = 200 * (output_resolution[0] / 1920)
                                        plt.savefig(graph_path, dpi=dpi_scale, facecolor='white')
                                        plt.close()
                                        all_generated_images.insert(0, graph_path)
                                except: pass
                    except: pass

# ================================================================
# 3. MESH LOADING & REGION SELECTION
# ================================================================
selected_regions = []
reader = None

if file_extension in ['.encas', '.case']:
    reader = OpenDataFile(input_file)
    reader.UpdatePipelineInformation()
    selected_regions = ['EnSight_Mesh'] 
elif file_extension in ['.foam', '.openfoam', '.simplefoam']:
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
                except: pass
    reader.MeshRegions = selected_regions if selected_regions else ['internalMesh']

run_settings["Regions"] = selected_regions

# ================================================================
# 4. VARIABLE & ISO-SURFACE SELECTION 
# ================================================================
avail_points = list(reader.PointArrays.Available) if hasattr(reader, 'PointArrays') else []
avail_cells = list(reader.CellArrays.Available) if hasattr(reader, 'CellArrays') else []
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

# --- ISO-SURFACE LOGIC ---
iso_settings = None

if config and "iso_surface" in config and config["iso_surface"].get("create", False):
    iso_cfg = config["iso_surface"]
    if iso_cfg.get("variable") in available_vars:
        iso_settings = {
            'var': iso_cfg["variable"], 
            'val': float(iso_cfg["value"]), 
            'color': iso_cfg.get("color_by") if iso_cfg.get("color_by") in available_vars else None
        }
elif not config:
    want_iso = input("\nCreate an Iso-Surface? (y/n) > ").strip().lower()
    if want_iso == 'y':
        iso_var = input("Enter variable to contour by (e.g., p, U) > ").strip()
        if iso_var in available_vars:
            try:
                iso_val = float(input(f"Enter Iso-value for '{iso_var}' > ").strip())
                iso_color = input("Variable to color it by? (Press Enter for solid) > ").strip()
                iso_color = iso_color if iso_color in available_vars else None
                iso_settings = {'var': iso_var, 'val': iso_val, 'color': iso_color}
            except ValueError: pass

if iso_settings:
    run_settings["Iso_Surface"] = f"{iso_settings['var']} = {iso_settings['val']}" + (f" (Color: {iso_settings['color']})" if iso_settings['color'] else " (Solid)")
    if iso_settings['var'] not in variables_to_plot: variables_to_plot.append(iso_settings['var'])
    if iso_settings['color'] and iso_settings['color'] not in variables_to_plot: variables_to_plot.append(iso_settings['color'])

if hasattr(reader, 'PointArrays') and avail_points: reader.PointArrays = [v for v in variables_to_plot if v in avail_points]
if hasattr(reader, 'CellArrays') and avail_cells: reader.CellArrays = [v for v in variables_to_plot if v in avail_cells]
run_settings["Variables"] = variables_to_plot

reader.UpdatePipeline()
temp_merged = MergeBlocks(Input=reader)
temp_merged.UpdatePipeline()

try:
    num_cells = temp_merged.GetDataInformation().GetNumberOfCells()
    if num_cells > 0: cfd_data["Cell Count"] = f"{num_cells:,}"
except: pass

merged_ensight = temp_merged if file_extension in ['.encas', '.case'] else None

# ================================================================
# 5. HIGH-RES RENDERING & SCREENSHOT GENERATION
# ================================================================
renderView = GetActiveView() or CreateView('RenderView')
renderView.ViewSize = [1920, 1080] # Base window size
renderView.Background = [.4, .4, .4] 

# --- IMAGE QUALITY UPGRADES ---
renderView.UseColorPaletteForBackground = 0
try:
    renderView.AntiAliasing = 'FXAA' # Enable hardware anti-aliasing
except: pass

for region_name in selected_regions:
    print(f"\nPROCESSING: {region_name}")
    
    if file_extension in ['.foam', '.openfoam', '.simplefoam']:
        reader.MeshRegions = [region_name]
        reader.UpdatePipeline()
        region_data = MergeBlocks(Input=reader)
        region_data.UpdatePipeline()
        is_boundary = 'patch' in region_name.lower()
    else:
        region_data, is_boundary = merged_ensight, False

    data_to_render = region_data
    slice_axis = ""
    
    if is_boundary:
        run_settings["Region_Slices"][region_name] = "None (3D)"
    else:
        bounds = region_data.GetDataInformation().GetBounds()
        cx, cy, cz = (bounds[0]+bounds[1])/2.0, (bounds[2]+bounds[3])/2.0, (bounds[4]+bounds[5])/2.0
        
        if config and "slices" in config and region_name in config["slices"]:
            slice_axis = config["slices"][region_name].lower()
        elif not config:
            slice_axis = input(f"Take 2D slice of '{region_name}'? (x/y/z or Enter for 3D) > ").strip().lower()

        if slice_axis in ['x', 'y', 'z']:
            slice_filter = Slice(Input=region_data)
            slice_filter.SliceType = 'Plane'
            slice_filter.SliceType.Origin = [cx, cy, cz]
            slice_filter.SliceType.Normal = [1.0 if slice_axis=='x' else 0.0, 1.0 if slice_axis=='y' else 0.0, 1.0 if slice_axis=='z' else 0.0]
            slice_filter.UpdatePipeline()
            data_to_render = slice_filter 
            run_settings["Region_Slices"][region_name] = f"{slice_axis.upper()}-Normal"
        else:
            run_settings["Region_Slices"][region_name] = "None (Full 3D)"

    if is_boundary or slice_axis not in ['x', 'y', 'z']:
        views_to_take = [("front", [1,0,0], [0,0,1]), ("side", [0,1,0], [0,0,1]), ("top", [0,0,1], [1,0,0]), ("front_iso", [1,1,1], [0,0,1]), ("rear_iso", [-1,1,1], [0,0,1])]
    else:
        views_to_take = [(f"{slice_axis.upper()}_Normal", [1 if slice_axis=='x' else 0, 1 if slice_axis=='y' else 0, 1 if slice_axis=='z' else 0], [0,0,1] if slice_axis in ['x','y'] else [1,0,0])]

    HideAll(renderView)
    display = Show(data_to_render, renderView)
    display.Representation = 'Surface'
    ColorBy(display, None)
    display.DiffuseColor = [0.8, 0.8, 0.8]
    display.SetScalarBarVisibility(renderView, False)
    
    for v_name, c_pos, c_up in views_to_take:
        if is_boundary and v_name in ["top", "rear_iso"]: continue 
        snap_view(f"Gray_{v_name}", c_pos, c_up, region_name)

    region_point_vars, region_cell_vars = list(data_to_render.PointData.keys()), list(data_to_render.CellData.keys())
    for var in variables_to_plot:
        if var not in raw_vars: continue 
        
        if var in region_point_vars: ColorBy(display, ('POINTS', var))
        elif var in region_cell_vars: ColorBy(display, ('CELLS', var))
        else: continue
        
        display.RescaleTransferFunctionToDataRange(True, False)
        display.SetScalarBarVisibility(renderView, True)
        for v_name, c_pos, c_up in views_to_take: snap_view(f"{var}_{v_name}", c_pos, c_up, region_name)
        display.SetScalarBarVisibility(renderView, False)

    pvd_export_path = os.path.join(run_dir, f"Run_{next_run_num}_{region_name.replace('/', '_')}_summary.pvd")
    SaveData(pvd_export_path, proxy=data_to_render)
    flatten_pvd(pvd_export_path)

# --- ISO-SURFACE RENDERING ---
if iso_settings:
    print(f"\nPROCESSING: Iso-Surface ({iso_settings['var']} = {iso_settings['val']})")
    if file_extension in ['.foam', '.openfoam', '.simplefoam']:
        current_regions = list(reader.MeshRegions)
        if 'internalMesh' not in current_regions:
            reader.MeshRegions = current_regions + ['internalMesh']
            reader.UpdatePipeline()
        iso_base = MergeBlocks(Input=reader)
        iso_base.UpdatePipeline()
    else: iso_base = merged_ensight

    base_cell_vars = list(iso_base.CellData.keys())
    if iso_settings['var'] in base_cell_vars or (iso_settings['color'] and iso_settings['color'] in base_cell_vars):
        iso_base = CellDatatoPointData(Input=iso_base)

    iso_filter = Contour(Input=iso_base)
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
        snap_view(f"{iso_settings['val']}_ColoredBy_{color_suffix}_{v_name}", c_pos, c_up, f"IsoSurface_{iso_settings['var']}")
        add_iso_info_overlay(all_generated_images[-1], iso_settings)
        
    iso_display.SetScalarBarVisibility(renderView, False)
    iso_pvd_path = os.path.join(run_dir, f"Run_{next_run_num}_IsoSurface_{iso_settings['var']}.pvd")
    SaveData(iso_pvd_path, proxy=iso_filter)
    flatten_pvd(iso_pvd_path)

# ================================================================
# 6. EXPORT PDF, SETTINGS & CLEANUP
# ================================================================
settings_path = os.path.join(run_dir, f"Run_{next_run_num}_settings.txt")
with open(settings_path, 'w') as f:
    f.write(f"========================================\n  CFD VISUALIZER LOG - RUN {next_run_num}\n========================================\n\n")
    f.write(f"Input File  : {run_settings['Input File']}\n")
    f.write(f"Regions     : {', '.join(run_settings['Regions'])}\n")
    f.write(f"Variables   : {', '.join(run_settings['Variables'])}\n")
    f.write(f"Iso-Surface : {run_settings['Iso_Surface']}\n")
    for key, value in cfd_data.items(): f.write(f"{key:<18}: {value}\n")

try:
    # Dynamic table sizing
    w, h = output_resolution
    table_path = os.path.join(run_dir, f"Run_{next_run_num}_DataTable.png")
    img = Image.new('RGB', (w, h), color=(255, 255, 255))
    d = ImageDraw.Draw(img)
    
    f_title_sz, f_text_sz = int(w * 0.03), int(w * 0.02)
    try: font_title, font_text = ImageFont.truetype("arial.ttf", f_title_sz), ImageFont.truetype("arial.ttf", f_text_sz)
    except: font_title, font_text = ImageFont.load_default(), ImageFont.load_default()
    
    start_x, start_y = int(w*0.08), int(h*0.1)
    d.text((start_x, start_y), f"CFD Run Summary (Run {next_run_num})", fill=(0,0,0), font=font_title)
    for i, (k, v) in enumerate(cfd_data.items()):
        y_pos = start_y + int(h*0.15) + (i * int(f_text_sz * 1.8))
        d.text((start_x, y_pos), f"{k}:", fill=(100,100,100), font=font_text)
        d.text((start_x + int(w*0.25), y_pos), f"{v}", fill=(0,0,0), font=font_text)
    img.save(table_path)
    
    pdf_path = os.path.join(run_dir, f"Run_{next_run_num}.pdf")
    compiled = [Image.open(table_path).convert('RGB')]
    
    for p in all_generated_images:
        if os.path.exists(p):
            try:
                curr_img = Image.open(p)
                if curr_img.mode in ('RGBA', 'LA') or (curr_img.mode == 'P' and 'transparency' in curr_img.info):
                    alpha = curr_img.convert('RGBA').split()[-1]
                    bg = Image.new("RGB", curr_img.size, (255, 255, 255))
                    bg.paste(curr_img, mask=alpha)
                    compiled.append(bg)
                else: compiled.append(curr_img.convert('RGB'))
            except: pass
        
    compiled[0].save(pdf_path, save_all=True, append_images=compiled[1:])
    print(f"\n[SUCCESS] Generated high-res PDF Report: {pdf_path}")
    
    if os.path.exists(table_path): os.remove(table_path)
    for p in all_generated_images:
        if os.path.exists(p):
            try: os.remove(p)
            except: pass
            
    print(f"\n--- DONE ---")
except Exception as e:
    print(f"\n[WARNING] PDF creation failed: {e}")