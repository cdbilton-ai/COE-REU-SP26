"""
Multi-Format CFD Visualizer
Supports: OpenFOAM (.foam, .simpleFoam) and ANSYS EnSight (.encas, .case)
This script automates the process of loading CFD data, selecting regions/variables,
taking standard camera angles, and compiling a PDF report.
"""

from paraview.simple import *
import os
import sys
import re

# ================================================================
# 1. SETUP & DIRECTORY MANAGEMENT
# ================================================================
# Prompt the user for the file path and clean up quotes from drag-and-drop
raw_path = input("Drag and drop your .encas, .foam, or .simpleFoam file here > ")
input_file = raw_path.strip().replace('"', '').replace("'", "")

if not os.path.exists(input_file):
    print(f"[ERROR] File not found: {input_file}")
    sys.exit(1)

case_dir = os.path.dirname(input_file)
file_extension = os.path.splitext(input_file)[1].lower()

# Create a dedicated "Images" folder inside the case directory
results_dir = os.path.join(case_dir, "Images")
os.makedirs(results_dir, exist_ok=True)

# Scan the Images folder to automatically determine the next Run number
run_numbers = [0]
for f in os.listdir(results_dir):
    match = re.search(r'Run_(\d+)', f)
    if match: run_numbers.append(int(match.group(1)))
next_run_num = max(run_numbers) + 1

# Dictionaries to store user settings and extracted CFD metadata
run_settings = {"Input File": input_file, "Regions": [], "Variables": [], "Region_Slices": {}}
cfd_data = {"C_D": "N/A", "C_L": "N/A", "Reference Area": "N/A", "Solve Time": "N/A", "Solver Version": "N/A", "Run Date": "N/A", "Cell Count": "N/A"}

# ================================================================
# 2. METADATA EXTRACTION (OpenFOAM Logs)
# ================================================================
# If OpenFOAM, parse the text log files to populate the final summary table
if file_extension in ['.foam', '.simplefoam']:
    log_files = [f for f in os.listdir(case_dir) if f.startswith('log.') and 'checkMesh' not in f]
    if log_files and os.path.exists(os.path.join(case_dir, log_files[0])):
        with open(os.path.join(case_dir, log_files[0]), 'r') as f:
            lines = f.readlines()
            # Grab solver info and run date from the top of the log
            for line in lines[:50]:
                if line.startswith('Build'): cfd_data["Solver Version"] = line.split(':', 1)[1].strip()
                elif line.startswith('Date'): cfd_data["Run Date"] = line.split(':', 1)[1].strip()
            # Read from the bottom up to get the final solve time/iteration
            for line in reversed(lines):
                if line.startswith('Time ='):
                    cfd_data["Solve Time"] = line.split('=')[1].strip() + " (Iters/Time)"
                    break

    # Look for force coefficient data (.dat files) to extract final Drag and Lift
    post_dir = os.path.join(case_dir, "postProcessing")
    if os.path.exists(post_dir):
        for root, dirs, files in os.walk(post_dir):
            for file in files:
                if file.endswith('.dat'):
                    try:
                        with open(os.path.join(root, file), 'r') as f:
                            lines = f.readlines()
                            headers = next((l for l in lines if 'Cd' in l and 'Cl' in l and l.startswith('#')), None)
                            if headers:
                                h_list = headers.replace('#', '').split()
                                cd_idx, cl_idx = (h_list.index('Cd') if 'Cd' in h_list else 1), (h_list.index('Cl') if 'Cl' in h_list else 3)
                                data_lines = [l for l in lines if not l.startswith('#') and l.strip()]
                                if data_lines:
                                    vals = data_lines[-1].split()
                                    if len(vals) > max(cd_idx, cl_idx): cfd_data["C_D"], cfd_data["C_L"] = vals[cd_idx], vals[cl_idx]
                    except: pass

# ================================================================
# 3. MESH LOADING & REGION SELECTION
# ================================================================
selected_regions = []

# EnSight files load all parts at once; OpenFOAM allows specific region selection
if file_extension in ['.encas', '.case']:
    reader = OpenDataFile(input_file)
    reader.UpdatePipelineInformation() # Loads lightweight metadata only
    selected_regions = ['EnSight_Mesh'] 

elif file_extension in ['.foam', '.simplefoam']:
    reader = OpenFOAMReader(FileName=input_file)
    reader.UpdatePipelineInformation() 
    available_regions = list(reader.MeshRegions.Available)
    
    # Prompt user to select specific mesh boundaries or internal volumes
    for i, reg in enumerate(available_regions): print(f"  {i}: {reg}")
    val = input("\nEnter region NUMBERS to analyze (e.g., 0, 3) > ").strip()
    if val:
        for v in val.split(','):
            try: selected_regions.append(available_regions[int(v.strip())])
            except: pass
    reader.MeshRegions = selected_regions if selected_regions else ['internalMesh']

run_settings["Regions"] = selected_regions

# ================================================================
# 4. VARIABLE SELECTION (LAZY LOADING)
# ================================================================
# Scan metadata for variables (Pressure, Velocity, etc.) BEFORE loading heavy data into RAM
avail_points = list(reader.PointArrays.Available) if hasattr(reader, 'PointArrays') else []
avail_cells = list(reader.CellArrays.Available) if hasattr(reader, 'CellArrays') else []
available_vars = list(set(avail_points + avail_cells))

if available_vars:
    print("\nAvailable variables:")
    for var in sorted(available_vars): print(f"  - {var}")
    raw_vars = [v.strip() for v in input("\nEnter variables to plot (comma-separated) > ").split(',')]
    variables_to_plot = [v for v in raw_vars if v in available_vars]
else:
    variables_to_plot = []

# Tell the reader to ONLY load the variables the user specifically requested
if hasattr(reader, 'PointArrays') and avail_points: reader.PointArrays = [v for v in variables_to_plot if v in avail_points]
if hasattr(reader, 'CellArrays') and avail_cells: reader.CellArrays = [v for v in variables_to_plot if v in avail_cells]
run_settings["Variables"] = variables_to_plot

# Execute the heavy data load into memory
reader.UpdatePipeline()
temp_merged = MergeBlocks(Input=reader)
temp_merged.UpdatePipeline()

# Universal cell counter (works for both ANSYS and OpenFOAM formats)
try:
    num_cells = temp_merged.GetDataInformation().GetNumberOfCells()
    if num_cells > 0: cfd_data["Cell Count"] = f"{num_cells:,}"
except: pass

merged_ensight = temp_merged if file_extension in ['.encas', '.case'] else None

# ================================================================
# 5. RENDERING & SCREENSHOT GENERATION
# ================================================================
# Set up ParaView's virtual camera environment (1080p, white background)
renderView = GetActiveView() or CreateView('RenderView')
renderView.ViewSize = [1920, 1080]
renderView.Background = [1, 1, 1] 
all_generated_images = []

# Loop through every mesh region the user selected
for region_name in selected_regions:
    print(f"\nPROCESSING: {region_name}")
    
    # Isolate the current region
    if file_extension in ['.foam', '.simplefoam']:
        reader.MeshRegions = [region_name]
        reader.UpdatePipeline()
        region_data = MergeBlocks(Input=reader)
        region_data.UpdatePipeline()
        is_boundary = 'patch' in region_name.lower() # Check if it's a 2D surface
    else:
        region_data, is_boundary = merged_ensight, False

    data_to_render = region_data
    slice_axis = ""
    
    # If it's a 3D volume, ask the user if they want to cut a 2D slice through the center
    if is_boundary:
        run_settings["Region_Slices"][region_name] = "None (3D Surface)"
    else:
        bounds = region_data.GetDataInformation().GetBounds()
        cx, cy, cz = (bounds[0]+bounds[1])/2.0, (bounds[2]+bounds[3])/2.0, (bounds[4]+bounds[5])/2.0
        slice_axis = input(f"Take 2D slice of '{region_name}'? (x/y/z or Enter for 3D) > ").strip().lower()

        if slice_axis in ['x', 'y', 'z']:
            slice_filter = Slice(Input=region_data)
            slice_filter.SliceType = 'Plane'
            slice_filter.SliceType.Origin = [cx, cy, cz]
            slice_filter.SliceType.Normal = [1.0 if slice_axis=='x' else 0.0, 1.0 if slice_axis=='y' else 0.0, 1.0 if slice_axis=='z' else 0.0]
            slice_filter.UpdatePipeline()
            data_to_render = slice_filter 
            run_settings["Region_Slices"][region_name] = f"{slice_axis.upper()}-Normal Slice"
        else:
            run_settings["Region_Slices"][region_name] = "None (Full 3D Volume)"

    # Determine which camera angles make sense based on if it's 3D or a 2D slice
    if is_boundary or slice_axis not in ['x', 'y', 'z']:
        views_to_take = [("front", [1,0,0], [0,0,1]), ("side", [0,1,0], [0,0,1]), ("top", [0,0,1], [1,0,0]), ("front_iso", [1,1,1], [0,0,1]), ("rear_iso", [-1,1,1], [0,0,1])]
    else:
        views_to_take = [(f"{slice_axis.upper()}_Normal", [1 if slice_axis=='x' else 0, 1 if slice_axis=='y' else 0, 1 if slice_axis=='z' else 0], [0,0,1] if slice_axis in ['x','y'] else [1,0,0])]

    HideAll(renderView)
    display = Show(data_to_render, renderView)
    display.Representation = 'Surface'

    # Helper function to move camera and save PNG
    def snap_view(file_suffix, camera_pos, view_up):
        ResetCamera()
        c = renderView.CameraFocalPoint
        renderView.CameraPosition = [c[0]+camera_pos[0]*100, c[1]+camera_pos[1]*100, c[2]+camera_pos[2]*100]
        renderView.CameraFocalPoint = c
        renderView.CameraViewUp = view_up
        ResetCamera()
        Render()
        f_path = os.path.join(results_dir, f"Run_{next_run_num}_{region_name.replace('/', '_')}_{file_suffix}.png")
        SaveScreenshot(f_path, renderView)
        all_generated_images.append(f_path)

    # First, take standard gray geometry pictures
    ColorBy(display, None)
    display.DiffuseColor = [0.8, 0.8, 0.8]
    display.SetScalarBarVisibility(renderView, False)
    for v_name, c_pos, c_up in views_to_take:
        if is_boundary and v_name in ["top", "rear_iso"]: continue 
        snap_view(f"Gray_{v_name}", c_pos, c_up)

    # Next, loop through user variables, apply colors/legends, and re-take the pictures
    region_point_vars, region_cell_vars = list(data_to_render.PointData.keys()), list(data_to_render.CellData.keys())
    for var in variables_to_plot:
        if var in region_point_vars: ColorBy(display, ('POINTS', var))
        elif var in region_cell_vars: ColorBy(display, ('CELLS', var))
        else: continue
        
        display.RescaleTransferFunctionToDataRange(True, False)
        display.SetScalarBarVisibility(renderView, True)
        for v_name, c_pos, c_up in views_to_take: snap_view(f"{var}_{v_name}", c_pos, c_up)
        display.SetScalarBarVisibility(renderView, False)

# ================================================================
# 6. EXPORT PDF & CLEANUP
# ================================================================
# Save the exact settings used for this run to a text file
with open(os.path.join(results_dir, f"Run_{next_run_num}_settings.txt"), 'w') as f:
    f.write(f"CFD VISUALIZER SETTINGS - RUN {next_run_num}\nInput: {run_settings['Input File']}\nRegions: {', '.join(run_settings['Regions'])}\nVariables: {', '.join(run_settings['Variables'])}\nSlices: {run_settings['Region_Slices']}\n")

# Use Pillow (PIL) to create a summary data table, then combine all PNGs into one PDF
if all_generated_images:
    try:
        from PIL import Image, ImageDraw, ImageFont
        table_path = os.path.join(results_dir, f"Run_{next_run_num}_DataTable.png")
        img = Image.new('RGB', (1920, 1080), color=(255, 255, 255))
        d = ImageDraw.Draw(img)
        
        try: font_title, font_text = ImageFont.truetype("arial.ttf", 60), ImageFont.truetype("arial.ttf", 45)
        except: font_title, font_text = ImageFont.load_default(), ImageFont.load_default()
        
        d.text((150, 150), f"CFD Run Summary (Run {next_run_num})", fill=(0,0,0), font=font_title)
        for i, (k, v) in enumerate(cfd_data.items()):
            d.text((150, 300 + i*80), f"{k}:", fill=(100,100,100), font=font_text)
            d.text((650, 300 + i*80), f"{v}", fill=(0,0,0), font=font_text)
        img.save(table_path)
        
        # Merge cover sheet table and screenshot sequence into PDF
        pdf_path = os.path.join(results_dir, f"Run_{next_run_num}.pdf")
        compiled = [Image.open(table_path).convert('RGB')] + [Image.open(p).convert('RGB') for p in all_generated_images]
        compiled[0].save(pdf_path, save_all=True, append_images=compiled[1:])
        
        # Cleanup temporary files
        os.remove(table_path)
        for p in all_generated_images: os.remove(p)
        print(f"\n[SUCCESS] Generated {pdf_path}")
    except Exception as e:
        print(f"\n[WARNING] PDF creation failed: {e}. Raw images kept.")