
from paraview.simple import *
import os
import sys
import ensightreader

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
    print("\n[ERROR] File not found!")
    print(f"Looked for: {input_file}")
    sys.exit(1)

# 3. Determine Output Directory automatically
# If input is 'C:/Users/data/run_1/car.stl', output becomes 'C:/Users/data/run_1'
output_dir = os.path.dirname(input_file)
print(f"\nTarget File:   {os.path.basename(input_file)}")
print(f"Saving Images: {output_dir}")
print("-" * 60)

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

# Get/Create View
renderView = GetActiveView()
if not renderView:
    renderView = CreateView('RenderView')

# Clear old data (safety)
HideAll(renderView)

# Show new data
display = Show(source, renderView)
display.Representation = 'Surface'

# Visual Settings
renderView.ViewSize = [1920, 1080]
renderView.Background = [1, 1, 1] # White Background

# Optional: Add faint axis grid or color if needed
# display.DiffuseColor = [0.8, 0.8, 0.8] # Light gray for STLs

# ================================================================
# 3. SNAPSHOT LOGIC
# ================================================================

def snap_view(view_name, camera_pos, view_up):
    print(f"  - Capturing {view_name}...")
    
    ResetCamera()
    center = renderView.CameraFocalPoint
    dist = 100 
    
    # Calculate Camera Position
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
    
    # Construct filename
    # e.g. drivaer_front.png
    base_name = os.path.splitext(os.path.basename(input_file))[0]
    filename = f"{base_name}_{view_name}.png"
    full_path = os.path.join(output_dir, filename)
    
    SaveScreenshot(full_path, renderView)

# ================================================================
# 4. EXECUTE
# ================================================================

print("Starting Capture...")

# Front View
snap_view("front",     [-1, 0, 0],   [1, 0, 1])

# Side View
snap_view("side",      [0, -1, 0],   [0, 0, 0])

# Top View
snap_view("top",       [0, 0, 1],   [0, 0, 0])

# Front ISO
snap_view("front_iso", [-1, 1, 1],   [0, 0, 1])

# Rear ISO
snap_view("rear_iso",  [1, 1, 1], [0, 0, 1])

print("="*60)
print("DONE! Check your folder for the images.")
print("="*60)