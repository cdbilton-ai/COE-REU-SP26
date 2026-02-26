
from paraview.simple import *
import os
import sys

# ================================================================
# 1. INTERACTIVE PROMPT
# ================================================================
print("="*60)
print("  PARAVIEW BATCH SCREENSHOT TOOL")
print("="*60)
print("Instruction: Drag and drop your .stl or .vtu file here and press Enter.")
print("")

# 1. Get the file path from the user
# We use .strip() to remove the quotes ("") that Windows adds when dragging files
raw_path = input("File Path > ")
input_file = raw_path.strip().replace('"', '').replace("'", "")

# 2. Verify file existence
if not os.path.exists(input_file):
    print(f"\n[ERROR] File not found: {input_file}")
    sys.exit(1)
output_dir = os.path.dirname(input_file)
base_name = os.path.splitext(os.path.basename(input_file))[0]
output_vtk = os.path.join(output_dir, f"{base_name}_converted.vtk")
results_dir = os.path.join(output_dir, "Results")

if not os.path.exists(results_dir):
    os.makedirs(results_dir)
    print(f"\n[INFO] Created new folder for images: {results_dir}")

# ================================================================
# 2. LOAD & PREPARE
# ================================================================

try:
    # OpenDataFile automatically handles .stl, .vtu, .foam, etc.
    source = OpenDataFile(input_file)
    if not source:
        raise RuntimeError("Load failed.")
    source.UpdatePipeline()
    print("STATUS: File loaded successfully.")
except Exception as e:
    print(f"[ERROR] Could not open file. Details: {e}")
    sys.exit(1)

# ================================================================
# 3. VARIABLES TO PLOT 
# ================================================================
# EDIT THIS LIST: Add or remove the exact variable names from your simulation
variables_to_plot = ["pressure", "rel_velocity_magnitude", "pressure_coefficient"]

# ================================================================
# 4. VISUALIZATION SETUP
# ================================================================
print("\n4. Setting up the 3D Scene...")

renderView = GetActiveView()
if not renderView:
    renderView = CreateView('RenderView')

HideAll(renderView)
display = Show(source, renderView)
display.Representation = 'Surface'

renderView.ViewSize = [1920, 1080]
renderView.Background = [1, 1, 1] 

# ================================================================
# 5. SCREENSHOT LOGIC
# ================================================================
def snap_view(file_suffix, camera_pos, view_up):
    print(f"   - Capturing {file_suffix}...")
    
    ResetCamera()
    center = renderView.CameraFocalPoint
    dist = 100 
    
    new_pos = [
        center[0] + camera_pos[0] * dist,
        center[1] + camera_pos[1] * dist,
        center[2] + camera_pos[2] * dist
    ]
    
    renderView.CameraPosition = new_pos
    renderView.CameraFocalPoint = center
    renderView.CameraViewUp = view_up
    
    ResetCamera()
    Render()
    
    filename = f"{base_name}_{file_suffix}.png"
    full_path = os.path.join(results_dir, filename)
    SaveScreenshot(full_path, renderView)

# ================================================================
# 6. LOOP THROUGH VARIABLES & TAKE PHOTOS
# ================================================================
print("\n5. Generating colored screenshots...")

# First, take the solid gray baseline photos just in case
print("\n--- Processing Baseline (Solid Gray) ---")
ColorBy(display, None)
display.DiffuseColor = [0.8, 0.8, 0.8]
display.SetScalarBarVisibility(renderView, False)

snap_view("Gray_front",     [0, 0, 1],   [0, 1, 0])
snap_view("Gray_side",      [1, 0, 0],   [0, 1, 0])
snap_view("Gray_front_iso", [1, 1, 1],   [0, 1, 0])

# Now loop through the CFD variables
for var in variables_to_plot:
    print(f"\n--- Processing Variable: {var} ---")
    
    try:
        # 1. Color by the variable. 
        # ('POINTS', var) is standard for most CFD nodes. 
        # If your data is element-based, change 'POINTS' to 'CELLS'
        ColorBy(display, ('POINTS', var))
        
        # 2. Rescale the color map to fit the actual min/max of this variable
        display.RescaleTransferFunctionToDataRange(True, False)
        
        # 3. Turn on the Color Legend (Scalar Bar)
        display.SetScalarBarVisibility(renderView, True)
        
        # 4. Take the pictures
        snap_view(f"{var}_front",     [0, 0, 1],   [0, 1, 0])
        snap_view(f"{var}_side",      [1, 0, 0],   [0, 1, 0])
        snap_view(f"{var}_top",       [0, 1, 0],   [0, 0, -1])
        snap_view(f"{var}_front_iso", [1, 1, 1],   [0, 1, 0])
        snap_view(f"{var}_rear_iso",  [-1, 1, -1], [0, 1, 0])
        
        # 5. Hide the legend before moving to the next variable
        display.SetScalarBarVisibility(renderView, False)
        
    except Exception as e:
        print(f"   [WARNING] Could not process '{var}'. Is it spelled correctly in the EnSight file? Skipping...")
        print(f"   Details: {e}")

print("="*60)
print("SUCCESS! All conversions and variable images are done.")
print("="*60)