"""
Multi-Format CFD Visualizer - DEBUG VERSION
Extensive logging to identify where PDF generation fails
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

# Create debug log file
DEBUG_LOG = open("cfd_visualizer_debug.log", "w")

def debug_log(msg):
    """Log debug messages to both console and file"""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_msg = f"[{timestamp}] {msg}"
    print(log_msg)
    DEBUG_LOG.write(log_msg + "\n")
    DEBUG_LOG.flush()

# ================================================================
# CONFIG & SETUP
# ================================================================

debug_log("=== CFD VISUALIZER DEBUG SESSION STARTED ===")

raw_path = input("Drag and drop your CFD file OR a .json config file here > ").strip(' "\'')
initial_path = os.path.abspath(raw_path)
debug_log(f"Input path: {initial_path}")

config = None
output_resolution = [1920, 1080]
iso_configs = []

if initial_path.lower().endswith('.json'):
    debug_log(f"Loading JSON config: {initial_path}")
    try:
        with open(initial_path, 'r') as f:
            config = json.load(f)
        debug_log(f"Config loaded successfully: {config}")
        input_file = os.path.abspath(config.get("input_file", ""))
        output_resolution = config.get("resolution", [3840, 2160])
        debug_log(f"Resolution: {output_resolution}")
    except Exception as e:
        debug_log(f"ERROR loading JSON: {e}")
        sys.exit(1)
else:
    input_file = initial_path
    debug_log(f"Direct file input: {input_file}")

if not os.path.exists(input_file):
    debug_log(f"ERROR: Input file not found: {input_file}")
    sys.exit(1)

debug_log(f"Input file exists: {input_file}")

case_dir = os.path.dirname(input_file)
file_extension = os.path.splitext(input_file)[1].lower()
debug_log(f"File extension: {file_extension}")

results_dir = os.path.join(case_dir, "Images")
os.makedirs(results_dir, exist_ok=True)
debug_log(f"Results directory: {results_dir}")

run_numbers = [0]
for f in os.listdir(results_dir):
    match = re.search(r'Run_(\d+)', f)
    if match:
        run_numbers.append(int(match.group(1)))

next_run_num = max(run_numbers) + 1
run_dir = os.path.join(results_dir, f"Run_{next_run_num}")
os.makedirs(run_dir, exist_ok=True)
debug_log(f"Run directory: {run_dir}")

run_settings = {"Input File": input_file, "Regions": [], "Variables": [],
               "Region_Slices": {}, "Iso_Surfaces": []}
cfd_data = {
    "C_D": "N/A", "C_L": "N/A", "Reference Area": "N/A",
    "Iterations / Time": "N/A", "Solver Version": "N/A",
    "Run Date": "N/A", "Cell Count": "N/A"
}
all_generated_images = []

debug_log(f"Data structures initialized. Images list: {len(all_generated_images)}")

# ================================================================
# LOAD MESH
# ================================================================

debug_log("Loading mesh...")
is_openfoam = file_extension in ['.foam', '.openfoam', '.simplefoam']
debug_log(f"Is OpenFOAM: {is_openfoam}")

selected_regions = []
if is_openfoam:
    debug_log("Creating OpenFOAMReader...")
    reader = OpenFOAMReader(FileName=input_file)
    reader.UpdatePipelineInformation()
    available_regions = list(reader.MeshRegions.Available)
    debug_log(f"Available regions: {available_regions}")
    
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
    debug_log(f"Selected regions: {selected_regions}")
else:
    debug_log("Creating OpenDataFile reader (ANSYS)...")
    try:
        reader = OpenDataFile(input_file)
        reader.UpdatePipelineInformation()
        debug_log("ANSYS reader created successfully")
    except Exception as e:
        debug_log(f"ERROR creating ANSYS reader: {e}")
        sys.exit(1)
    selected_regions = ['Imported_Domain']
    debug_log(f"ANSYS regions: {selected_regions}")

run_settings["Regions"] = selected_regions

# ================================================================
# GET VARIABLES
# ================================================================

debug_log("Getting available variables...")
try:
    reader.UpdatePipeline()
    debug_log("Reader pipeline updated")
    
    temp_merged = MergeBlocks(Input=reader)
    temp_merged.UpdatePipeline()
    debug_log("Blocks merged and pipeline updated")
    
    avail_points = list(temp_merged.PointData.keys())
    avail_cells = list(temp_merged.CellData.keys())
    available_vars = list(set(avail_points + avail_cells))
    
    debug_log(f"Point variables: {avail_points}")
    debug_log(f"Cell variables: {avail_cells}")
    debug_log(f"All variables: {available_vars}")
    
    raw_vars = []
    if available_vars:
        if config and "variables" in config:
            raw_vars = config["variables"]
            debug_log(f"Using variables from config: {raw_vars}")
        else:
            print("\nAvailable variables:")
            for var in sorted(available_vars):
                print(f"  - {var}")
            raw_vars = [v.strip() for v in input("\nEnter variables to plot (comma-separated) > ").split(',')]
    
    variables_to_plot = [v for v in raw_vars if v in available_vars]
    debug_log(f"Variables to plot: {variables_to_plot}")
    
except Exception as e:
    debug_log(f"ERROR getting variables: {e}")
    import traceback
    debug_log(traceback.format_exc())
    sys.exit(1)

run_settings["Variables"] = variables_to_plot

# ================================================================
# SETUP RENDER VIEW
# ================================================================

debug_log("Setting up render view...")
try:
    renderView = GetActiveView() or CreateView('RenderView')
    renderView.ViewSize = output_resolution
    renderView.Background = [.4, .4, .4]
    renderView.UseColorPaletteForBackground = 0
    debug_log(f"Render view created with resolution: {output_resolution}")
except Exception as e:
    debug_log(f"ERROR setting up render view: {e}")
    import traceback
    debug_log(traceback.format_exc())

# ================================================================
# SNAPSHOT FUNCTION WITH LOGGING
# ================================================================

def snap_view_debug(file_suffix, camera_pos, view_up, prefix_name, focal_point, cam_dist):
    """Take a screenshot with debug logging"""
    try:
        debug_log(f"Snapping view: {file_suffix}")
        
        renderView.CameraFocalPoint = focal_point
        renderView.CameraPosition = [
            focal_point[0] + camera_pos[0] * cam_dist,
            focal_point[1] + camera_pos[1] * cam_dist,
            focal_point[2] + camera_pos[2] * cam_dist
        ]
        renderView.CameraViewUp = view_up
        ResetCamera()
        
        Render()
        f_path = os.path.join(run_dir, f"Run_{next_run_num}_{prefix_name.replace('/', '_')}_{file_suffix}.png")
        SaveScreenshot(f_path, renderView, ImageResolution=output_resolution, TransparentBackground=0)
        
        if os.path.exists(f_path):
            debug_log(f"Screenshot saved: {f_path} ({os.path.getsize(f_path)} bytes)")
            all_generated_images.append(f_path)
            debug_log(f"Total images: {len(all_generated_images)}")
            return True
        else:
            debug_log(f"ERROR: Screenshot file not created: {f_path}")
            return False
            
    except Exception as e:
        debug_log(f"ERROR in snap_view: {e}")
        import traceback
        debug_log(traceback.format_exc())
        return False

# ================================================================
# RENDER REGIONS
# ================================================================

debug_log("Starting region rendering...")

for region_name in selected_regions:
    debug_log(f"\n=== RENDERING REGION: {region_name} ===")
    
    if is_openfoam:
        reader.MeshRegions = [region_name]
        reader.UpdatePipeline()
        region_data = MergeBlocks(Input=reader)
        region_data.UpdatePipeline()
    else:
        region_data = temp_merged
    
    bounds = region_data.GetDataInformation().GetBounds()
    cx, cy, cz = ((bounds[0] + bounds[1]) / 2.0, (bounds[2] + bounds[3]) / 2.0, (bounds[4] + bounds[5]) / 2.0)
    debug_log(f"Bounds: X[{bounds[0]:.2f}, {bounds[1]:.2f}], Y[{bounds[2]:.2f}, {bounds[3]:.2f}], Z[{bounds[4]:.2f}, {bounds[5]:.2f}]")
    
    domain_diagonal = math.sqrt((bounds[1] - bounds[0]) ** 2 + (bounds[3] - bounds[2]) ** 2 + (bounds[5] - bounds[4]) ** 2)
    cam_dist = max(domain_diagonal * 2.5, 0.1)
    debug_log(f"Camera distance: {cam_dist:.2f}")
    
    # Test: Generate 3D views for each variable
    HideAll(renderView)
    display = Show(region_data, renderView)
    display.Representation = 'Surface'
    
    region_point_vars = list(region_data.PointData.keys())
    region_cell_vars = list(region_data.CellData.keys())
    debug_log(f"Available variables - Point: {region_point_vars}, Cell: {region_cell_vars}")
    
    for var in variables_to_plot:
        debug_log(f"\nProcessing variable: {var}")
        
        if var in region_point_vars:
            ColorBy(display, ('POINTS', var))
            debug_log(f"Colored by POINTS: {var}")
        elif var in region_cell_vars:
            ColorBy(display, ('CELLS', var))
            debug_log(f"Colored by CELLS: {var}")
        else:
            debug_log(f"WARNING: Variable not found: {var}")
            continue
        
        display.RescaleTransferFunctionToDataRange(True, False)
        display.SetScalarBarVisibility(renderView, True)
        
        # Test: Take front view only
        debug_log(f"Taking test snapshot for {var}...")
        success = snap_view_debug(f"{var}_front_TEST", [1, 0, 0], [0, 0, 1], region_name, [cx, cy, cz], cam_dist)
        if not success:
            debug_log(f"ERROR: Failed to take snapshot for {var}")
        
        display.SetScalarBarVisibility(renderView, False)

# ================================================================
# PDF GENERATION
# ================================================================

debug_log(f"\n=== PDF GENERATION ===")
debug_log(f"Total images collected: {len(all_generated_images)}")
debug_log(f"Images: {all_generated_images}")

if len(all_generated_images) == 0:
    debug_log("ERROR: No images were generated!")
else:
    try:
        debug_log("Creating PDF cover page...")
        pdf_path = os.path.join(run_dir, f"Run_{next_run_num}_Report.pdf")
        
        pdf_resolution = config.get("pdf_resolution", [816, 1056]) if config else [816, 1056]
        PDF_WIDTH, PDF_HEIGHT = pdf_resolution[0], pdf_resolution[1]
        debug_log(f"PDF resolution: {PDF_WIDTH}x{PDF_HEIGHT}")
        
        # Create cover page
        cover_img = Image.new('RGB', (PDF_WIDTH, PDF_HEIGHT), 'white')
        draw = ImageDraw.Draw(cover_img)
        
        try:
            title_font = ImageFont.truetype("arial.ttf", 28)
            text_font = ImageFont.truetype("arial.ttf", 12)
        except:
            title_font = ImageFont.load_default()
            text_font = ImageFont.load_default()
        
        draw.text((30, 30), f"CFD Visualization Report - Run {next_run_num}", fill="black", font=title_font)
        debug_log("Cover page created")
        
        # Process images
        debug_log("Processing images for PDF...")
        pdf_pages = []
        for i, img_path in enumerate(all_generated_images):
            debug_log(f"Processing image {i+1}/{len(all_generated_images)}: {img_path}")
            if os.path.exists(img_path):
                try:
                    with Image.open(img_path) as img:
                        img_rgb = img.convert('RGB')
                        img_rgb.thumbnail((PDF_WIDTH, PDF_HEIGHT), Image.Resampling.LANCZOS)
                        
                        page = Image.new('RGB', (PDF_WIDTH, PDF_HEIGHT), 'white')
                        x_offset = (PDF_WIDTH - img_rgb.width) // 2
                        y_offset = (PDF_HEIGHT - img_rgb.height) // 2
                        page.paste(img_rgb, (x_offset, y_offset))
                        
                        pdf_pages.append(page)
                        debug_log(f"  Added to PDF: {img_path}")
                except Exception as e:
                    debug_log(f"  ERROR processing image: {e}")
            else:
                debug_log(f"  WARNING: Image file not found: {img_path}")
        
        # Save PDF
        if pdf_pages:
            debug_log(f"Saving PDF with {len(pdf_pages)} pages...")
            cover_img.save(pdf_path, save_all=True, append_images=pdf_pages)
            debug_log(f"PDF saved: {pdf_path}")
            
            if os.path.exists(pdf_path):
                debug_log(f"PDF file size: {os.path.getsize(pdf_path)} bytes")
                debug_log("[SUCCESS] PDF report generated!")
            else:
                debug_log("ERROR: PDF file was not created")
        else:
            debug_log("ERROR: No pages to add to PDF")
            
    except Exception as e:
        debug_log(f"ERROR during PDF generation: {e}")
        import traceback
        debug_log(traceback.format_exc())

debug_log("=== DEBUG SESSION ENDED ===")
DEBUG_LOG.close()