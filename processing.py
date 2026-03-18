from paraview.simple import *
import os
import sys
import re

# ================================================================
# 1. INTERACTIVE PROMPT & FOLDER SETUP
# ================================================================
print("="*60)
print("  MULTI-FORMAT CFD VISUALIZER (.encas, .foam, .simpleFoam)")
print("="*60)

raw_path = input("Drag and drop your .encas, .foam, or .simpleFoam file here > ")
input_file = raw_path.strip().replace('"', '').replace("'", "")

if not os.path.exists(input_file):
    print(f"\n[ERROR] File not found: {input_file}")
    sys.exit(1)

output_dir = os.path.dirname(input_file)
base_name = os.path.splitext(os.path.basename(input_file))[0]
file_extension = os.path.splitext(input_file)[1].lower()

results_dir = os.path.join(output_dir, "Images")
if not os.path.exists(results_dir):
    os.makedirs(results_dir)
    print(f"\n[INFO] Created new folder for images: {results_dir}")

existing_files = os.listdir(results_dir)
run_numbers = [0]
for f in existing_files:
    match = re.search(r'Run_(\d+)', f)
    if match:
        run_numbers.append(int(match.group(1)))
next_run_num = max(run_numbers) + 1

# ================================================================
# 2. LOAD FILE & SELECT REGIONS
# ================================================================
selected_regions = []

try:
    if file_extension in ['.encas', '.case']:
        print("\n1. Detected EnSight format. Loading data...")
        reader = OpenDataFile(input_file)
        reader.UpdatePipeline()
        merged_ensight = MergeBlocks(Input=reader)
        merged_ensight.UpdatePipeline()
        selected_regions = ['EnSight_Mesh'] 

    elif file_extension in ['.foam', '.simplefoam']:
        print("\n1. Detected OpenFOAM format. Reading metadata...")
        reader = OpenFOAMReader(FileName=input_file)
        reader.UpdatePipelineInformation() 
        
        available_regions = list(reader.MeshRegions.Available)
        
        print("\n--- MESH REGION SELECTION ---")
        for i, reg in enumerate(available_regions):
            print(f"  {i}: {reg}")
            
        print("\nWhich parts of the mesh do you want to analyze?")
        print(" - E.g., for the volume and the car, type: 0, 3")
        
        val = input("\nEnter the NUMBERS of the regions > ").strip()
        
        if val:
            for v in val.split(','):
                try:
                    idx = int(v.strip())
                    selected_regions.append(available_regions[idx])
                except:
                    print(f"  [WARNING] Invalid index '{v}', skipping.")
        
        if not selected_regions:
            print("  [WARNING] No regions selected, defaulting to 'internalMesh'")
            selected_regions = ['internalMesh']
            
        reader.MeshRegions = selected_regions
        reader.UpdatePipeline()
        temp_merged = MergeBlocks(Input=reader)
        temp_merged.UpdatePipeline()

    else:
        print(f"\n[ERROR] Unsupported format: {file_extension}")
        sys.exit(1)

except Exception as e:
    print(f"\n[CRITICAL ERROR] Failed during load phase. Details: {e}")
    sys.exit(1)

# ================================================================
# 3. DYNAMIC VARIABLE PROMPT
# ================================================================
print("\nScanning dataset for available variables...")

scan_source = temp_merged if file_extension in ['.foam', '.simplefoam'] else merged_ensight
point_vars = scan_source.PointData.keys()
cell_vars = scan_source.CellData.keys()
available_vars = list(set(point_vars + cell_vars))

if not available_vars:
    print("\n[WARNING] No variables found!")
    variables_to_plot = []
else:
    print("\nAvailable variables:")
    for i, var in enumerate(available_vars):
        print(f"  - {var}")

    user_input = input("\nEnter the variables to plot, separated by commas (or press Enter to skip): ")
    selected_vars = [v.strip() for v in user_input.split(',')]
    variables_to_plot = [v for v in selected_vars if v in available_vars]

# ================================================================
# 4. LOOP THROUGH EACH SELECTED MESH SEPARATELY
# ================================================================
renderView = GetActiveView()
if not renderView:
    renderView = CreateView('RenderView')
renderView.ViewSize = [1920, 1080]
renderView.Background = [1, 1, 1] 

for region_name in selected_regions:
    safe_region_name = region_name.replace('/', '_')
    generated_images = []
    
    print(f"\n{'='*50}")
    print(f" PROCESSING: {region_name}")
    print(f"{'='*50}")
    
    if file_extension in ['.foam', '.simplefoam']:
        reader.MeshRegions = [region_name]
        reader.UpdatePipeline()
        region_data = MergeBlocks(Input=reader)
        region_data.UpdatePipeline()
        is_boundary = 'patch' in region_name.lower()
    else:
        region_data = merged_ensight
        is_boundary = False

    data_to_render = region_data
    
    if is_boundary:
        print(f"\n[INFO] '{region_name}' is a surface patch. Skipping 2D slice prompt.")
    else:
        bounds = region_data.GetDataInformation().GetBounds()
        cx = (bounds[0] + bounds[1]) / 2.0
        cy = (bounds[2] + bounds[3]) / 2.0
        cz = (bounds[4] + bounds[5]) / 2.0

        print(f"\nWould you like to take a 2D slice of '{region_name}'?")
        slice_axis = input("Enter 'x', 'y', 'z', or press Enter for full 3D mesh: ").strip().lower()

        if slice_axis in ['x', 'y', 'z']:
            print(f"Creating a slice normal to the {slice_axis.upper()}-axis...")
            slice_filter = Slice(Input=region_data)
            slice_filter.SliceType = 'Plane'
            slice_filter.SliceType.Origin = [cx, cy, cz]
            
            if slice_axis == 'x': slice_filter.SliceType.Normal = [1.0, 0.0, 0.0]
            elif slice_axis == 'y': slice_filter.SliceType.Normal = [0.0, 1.0, 0.0]
            elif slice_axis == 'z': slice_filter.SliceType.Normal = [0.0, 0.0, 1.0]
                
            slice_filter.UpdatePipeline()
            data_to_render = slice_filter 

    HideAll(renderView)
    display = Show(data_to_render, renderView)
    display.Representation = 'Surface'

    def snap_view(file_suffix, camera_pos, view_up):
        print(f"   - Capturing {file_suffix}...")
        ResetCamera()
        center = renderView.CameraFocalPoint
        dist = 100 
        new_pos = [center[0] + camera_pos[0]*dist, center[1] + camera_pos[1]*dist, center[2] + camera_pos[2]*dist]
        renderView.CameraPosition = new_pos
        renderView.CameraFocalPoint = center
        renderView.CameraViewUp = view_up
        ResetCamera()
        Render()
        filename = f"Run_{next_run_num}_{safe_region_name}_{file_suffix}.png"
        full_path = os.path.join(results_dir, filename)
        SaveScreenshot(full_path, renderView)
        generated_images.append(full_path)

    print("\nGenerating screenshots...")
    ColorBy(display, None)
    display.DiffuseColor = [0.8, 0.8, 0.8]
    display.SetScalarBarVisibility(renderView, False)

    snap_view("Gray_front",     [0, 0, 1],   [0, 1, 0])
    snap_view("Gray_side",      [1, 0, 0],   [0, 1, 0])
    snap_view("Gray_front_iso", [1, 1, 1],   [0, 1, 0])

    for var in variables_to_plot:
        print(f"  > Variable: {var}")
        try:
            region_point_vars = data_to_render.PointData.keys()
            region_cell_vars = data_to_render.CellData.keys()
            
            if var in region_point_vars: ColorBy(display, ('POINTS', var))
            elif var in region_cell_vars: ColorBy(display, ('CELLS', var))
            else:
                print(f"    [SKIP] '{var}' does not exist on {region_name}.")
                continue
            
            display.RescaleTransferFunctionToDataRange(True, False)
            display.SetScalarBarVisibility(renderView, True)
            
            snap_view(f"{var}_front",     [0, 0, 1],   [0, 1, 0])
            snap_view(f"{var}_side",      [1, 0, 0],   [0, 1, 0])
            snap_view(f"{var}_top",       [0, 1, 0],   [0, 0, -1])
            snap_view(f"{var}_front_iso", [1, 1, 1],   [0, 1, 0])
            snap_view(f"{var}_rear_iso",  [-1, 1, -1], [0, 1, 0])
            
            display.SetScalarBarVisibility(renderView, False)
        except Exception as e:
            print(f"    [WARNING] Failed on '{var}': {e}")

    if generated_images:
        print(f"\nCompiling PDF report for {region_name}...")
        try:
            from PIL import Image
            pdf_filename = f"Run_{next_run_num}_{safe_region_name}.pdf"
            pdf_path = os.path.join(results_dir, pdf_filename)
            images = [Image.open(img).convert('RGB') for img in generated_images]
            images[0].save(pdf_path, save_all=True, append_images=images[1:])
            print(f"   [SUCCESS] Saved: {pdf_filename}")
            for img in generated_images: os.remove(img)
            print("   [CLEANUP] Deleted raw .png files.")
        except ImportError:
            print("   [WARNING] Pillow library missing. PDF not created, but .png files were kept.")


# ================================================================
# 5. BONUS: COMBINED STREAMLINE SCENE
# ================================================================
# Check if we have both a volume (for math) and a boundary (for context)
has_internal = 'internalMesh' in selected_regions
has_boundary = any('patch' in r for r in selected_regions) or any('group' in r for r in selected_regions)
has_velocity = 'U' in available_vars

if has_internal and has_boundary and has_velocity:
    print("\n" + "="*60)
    print("  STREAMLINE VISUALIZATION")
    print("="*60)
    do_stream = input("Would you like to generate a combined streamline scene? (y/n) > ").strip().lower()
    
    if do_stream == 'y':
        print("\nSetting up the Streamline Scene...")
        HideAll(renderView)
        generated_stream_images = []
        
        # 1. Show the boundary patches as solid dark gray
        for region in selected_regions:
            if 'patch' in region.lower():
                # Use isolated readers to avoid crossing data pipelines
                patch_reader = OpenFOAMReader(FileName=input_file)
                patch_reader.MeshRegions = [region]
                patch_reader.UpdatePipeline()
                p_data = MergeBlocks(Input=patch_reader)
                
                p_disp = Show(p_data, renderView)
                ColorBy(p_disp, None)
                p_disp.DiffuseColor = [0.3, 0.3, 0.3] # Darker gray provides better contrast
        
        # 2. Get the volume data for the streamlines
        vol_reader = OpenFOAMReader(FileName=input_file)
        vol_reader.MeshRegions = ['internalMesh']
        vol_reader.UpdatePipeline()
        vol_data = MergeBlocks(Input=vol_reader)
        
        bounds = vol_data.GetDataInformation().GetBounds()
        cx, cy, cz = (bounds[0]+bounds[1])/2.0, (bounds[2]+bounds[3])/2.0, (bounds[4]+bounds[5])/2.0
        
        print("Calculating stream traces (this might take a moment)...")
        streamlines = StreamTracer(Input=vol_data, SeedType='Point Cloud')
        streamlines.Vectors = ['POINTS', 'U']
        streamlines.MaximumStreamlineLength = (bounds[1] - bounds[0]) * 2.0
        streamlines.SeedType.Center = [cx, cy, cz]
        # Radius big enough to cover the car, 250 seed points
        streamlines.SeedType.Radius = (bounds[1] - bounds[0]) / 2.5 
        streamlines.SeedType.NumberOfPoints = 250
        
        # Convert raw lines to 3D tubes so they look professional
        tubes = Tube(Input=streamlines)
        tubes.Radius = (bounds[1] - bounds[0]) / 800.0 
        
        stream_disp = Show(tubes, renderView)
        ColorBy(stream_disp, ('POINTS', 'U'))
        stream_disp.RescaleTransferFunctionToDataRange(True, False)
        stream_disp.SetScalarBarVisibility(renderView, True)
        
        # 3. Snap Photos
        def snap_stream(file_suffix, camera_pos, view_up):
            print(f"   - Capturing {file_suffix}...")
            ResetCamera()
            dist = 100 
            renderView.CameraPosition = [cx + camera_pos[0]*dist, cy + camera_pos[1]*dist, cz + camera_pos[2]*dist]
            renderView.CameraFocalPoint = [cx, cy, cz]
            renderView.CameraViewUp = view_up
            ResetCamera()
            Render()
            filename = f"Run_{next_run_num}_Streamlines_{file_suffix}.png"
            full_path = os.path.join(results_dir, filename)
            SaveScreenshot(full_path, renderView)
            generated_stream_images.append(full_path)
            
        snap_stream("side",      [1, 0, 0],   [0, 1, 0])
        snap_stream("front_iso", [1, 1, 1],   [0, 1, 0])
        snap_stream("rear_iso",  [-1, 1, -1], [0, 1, 0])
        
        # 4. Compile PDF
        if generated_stream_images:
            try:
                from PIL import Image
                pdf_filename = f"Run_{next_run_num}_Streamlines.pdf"
                pdf_path = os.path.join(results_dir, pdf_filename)
                images = [Image.open(img).convert('RGB') for img in generated_stream_images]
                images[0].save(pdf_path, save_all=True, append_images=images[1:])
                print(f"   [SUCCESS] Streamline PDF Saved: {pdf_filename}")
                for img in generated_stream_images: os.remove(img)
            except ImportError:
                pass

print("\n" + "="*60)
print("ALL PROCESSING COMPLETE!")
print("="*60)