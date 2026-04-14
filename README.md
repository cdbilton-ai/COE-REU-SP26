# Multi-Format CFD Visualizer

An automated, modular Python toolkit for generating standardized CFD visualization reports from **OpenFOAM** and **ANSYS EnSight** datasets. This project includes a primary visualizer script, batch processing utilities, file format converters, and geometry parameter extraction tools.

**Features:**
- ✅ Automated screenshot generation with 5 standard camera views (front, side, top, isometric)
- ✅ 2D slicing along X, Y, or Z axes with configurable slice counts and positions
- ✅ 3D isometric surface rendering with iso-surface contouring
- ✅ Dynamic PDF report generation with metadata table and image compilation
- ✅ JSON-based configuration for reproducible runs
- ✅ Zoom control with custom zoom center points
- ✅ Force coefficients graphing and metadata extraction
- ✅ Multi-region support for complex simulations
- ✅ Windows batch file automation (no command line needed)

---

## 📁 Repository Structure

COE-REU-SP26/ ├── 📄 README.md # This file ├── 📄 cfd_visualizer.py # Main visualization script (900+ lines, fully modular) ├── 📄 converter.py # File format converter (OpenFOAM ↔ EnSight) ├── 📄 processing.py # Post-processing utilities ├── 📄 Geo_Parameters.py # Geometry parameter extraction tool ├── 📂 Batch_Processing/ # Batch job scripts and templates ├── 📄 setup.json # Example config for OpenFOAM (motorBike case) ├── 📄 setup_ansys.json # Example config for ANSYS EnSight ├── 📄 run_visualizer.bat # Windows launcher (double-click to run) └── 📄 run_visualizer.sh # Linux/Mac launcher

Code

---

## 🚀 Quick Start (5 Minutes)

### Step 1: Install ParaView (if not already installed)
Download from [paraview.org](https://www.paraview.org/download/) and install normally.

### Step 2: Install Pillow for ParaView
**Windows:**
```bash
"C:\Program Files\ParaView 5.x.x\bin\pvpython.exe" -m pip install Pillow
Mac/Linux:
```

```bash
/Applications/ParaView-5.x.x.app/Contents/bin/pvpython -m pip install Pillow
(Replace 5.x.x with your ParaView version)
```

Step 3: Clone or Download This Repository
```bash
git clone https://github.com/cdbilton-ai/COE-REU-SP26.git
cd COE-REU-SP26
Step 4: Run Using Batch File (Easiest)
Windows: Double-click run_visualizer.bat
Linux/Mac: Run ./run_visualizer.sh
```
Or manually:

```bash
pvpython cfd_visualizer.py setup.json
```
📋 Prerequisites & Installation
System Requirements
ParaView 5.8+ (with bundled Python 3.6+)
Python 3.6+ (ParaView's bundled version)
4GB RAM minimum (8GB+ recommended for 4K resolution)
1GB free disk space (per simulation output)
Required Python Libraries
Library	Purpose	Installation
paraview.simple	3D visualization & rendering	Included with ParaView
Pillow (PIL)	PDF creation & image processing	See Step 2 above
matplotlib	Force coefficient graphing (optional)	pvpython -m pip install matplotlib
Verify Installation
```bash
pvpython -c "from paraview.simple import *; from PIL import Image; print('✓ All libraries installed')"
```
💻 Usage Guide
Method 1: Interactive Mode (No Config File)
```bash
pvpython cfd_visualizer.py
```
The script will prompt you for:

CFD file path - Drag and drop your .foam, .simpleFoam, or .encas file
Regions (OpenFOAM only) - Enter region numbers to analyze (e.g., 0, 3)
Variables - Select which fields to visualize (e.g., p, U, k)
Slicing - Choose slice axis (x, y, z) or render 3D
Method 2: Automated Mode with JSON Config (Recommended)
Create or modify a JSON configuration file:
```JSON
JSON
{
    "input_file": "/path/to/case/motor_bike.foam",
    "resolution": [3840, 2160],
    "pdf_resolution": [816, 1056],
    "zoom_factor": 1.0,
    "zoom_center": [0.0, 0.0, 0.0],
    
    "regions": ["internalMesh"],
    "variables": ["p", "U"],
    
    "slices": {
        "internalMesh": {
            "axis": "y",
            "min": -2.0,
            "max": 5.0,
            "count": 8
        }
    },
    
    "iso_surfaces": [
        {
            "create": true,
            "variable": "p",
            "value": 0.0,
            "color_by": "U"
        }
    ]
}
```
Run with config:

```bash
pvpython cfd_visualizer.py setup.json
```
Or use the batch file:

```bash
run_visualizer.bat
```
JSON Configuration Parameters


input_file    string	Path to CFD data file	/path/to/case.foam

resolution    [int, int]    Screenshot resolution (width × height)	[3840, 2160]

pdf_resolution    [int, int]	PDF page size in pixels	[816, 1056] (letter size)

zoom_factor    float	Camera zoom (>1 = zoom in)	1.0 (default), 1.5 (zoomed)

zoom_center    [x, y, z]	Custom zoom focal point	[0.0, 0.0, 0.0]

regions    [string]	Mesh regions to analyze	["internalMesh"]

variables	[string]	Variables to visualize	["p", "U", "k"]

Slicing Configuration:

```JSON
"slices": {
    "internalMesh": {
        "axis": "y",           // x, y, or z
        "min": -2.0,           // Min position on axis
        "max": 5.0,            // Max position on axis
        "count": 8             // Number of slices
    }
}
```
Iso-Surface Configuration:

```JSON
"iso_surfaces": [
    {
        "create": true,
        "variable": "p",       // Variable to contour
        "value": 0.0,          // Iso-value
        "color_by": "U"        // Optional coloring variable
    }
]
```
📂 Expected File Structure
OpenFOAM Case Folder
For metadata extraction (Force Coefficients, Cell Count, Solver Info), organize as:

Code
motorBike/
├── motorBike.foam                 ← Main file (drag into script)
├── log.simpleFoam                 ← Log file (solver version, date)
├── system/
│   ├── controlDict                ← Reference Area (Aref)
│   └── forceCoeffs                ← Force settings
└── postProcessing/
    └── forceCoeffs/
        ├── 0/
        │   └── coefficient.dat    ← Force data (for graphing)
        └── constant/
            └── coefficient.dat
ANSYS EnSight Case Folder
Code
simulation/
├── results.encas                  ← Main file (drag into script)
├── results.geom                   ← Geometry file
└── results.0000.p                 ← Pressure data
    results.0000.u                 ← Velocity data
    results.0000.k                 ← Turbulence data (if available)
📊 Output Files
All outputs are saved in {case_directory}/Images/Run_{N}/:

File	Description
Run_X_Report.pdf	Final report - Cover page with metadata + all screenshots
Run_X_state.pvsm	ParaView state file (can be opened to recreate visualization)
Run_X_*_summary.pvd	Region data export in ParaView format
Run_X_IsoSurface_*.pvd	Iso-surface data export
Run_X_ForceCoeffs.png	Force coefficient history graph (OpenFOAM only)
Example Output Directory
Code
Images/
├── Run_1/
│   ├── Run_1_Report.pdf
│   ├── Run_1_state.pvsm
│   ├── Run_1_internalMesh_summary.pvd
│   └── Run_1_IsoSurface_p_0.0.pvd
├── Run_2/
└── Run_3/
🎥 Customizing Camera Views
The script renders 5 standard camera angles by default. To modify or add views, edit the views_to_take list in the rendering sections:

```Python
views_to_take = [
    ("front",     [1, 0, 0],   [0, 0, 1]),  # X-axis view, Z up
    ("side",      [0, 1, 0],   [0, 0, 1]),  # Y-axis view, Z up
    ("top",       [0, 0, 1],   [1, 0, 0]),  # Z-axis view, X up
    ("front_iso", [1, 1, 1],   [0, 0, 1]),  # Isometric
    ("rear_iso",  [-1, 1, 1],  [0, 0, 1])   # Reverse isometric
]
```
Adding a Custom View:

```Python
("bottom_iso", [-1, -1, -1], [0, 0, 1])  # Bottom isometric view
```
The format is: ("view_name", [camera_direction], [up_vector])

📜 Code Architecture
Main Script: cfd_visualizer.py (900+ lines)
The script is organized into 7 modular sections:

Section	Functions	Purpose
1. Config & Setup	load_config(), get_zoom_settings(), setup_output_directories()	Load settings, setup folders
2. Helper Functions	flatten_pvd(), add_iso_info_overlay(), get_available_variables()	Utility functions
3. Metadata Extraction	extract_openfoam_metadata()	Parse force coefficients, solver info
4. Mesh Loading	load_and_select_regions(), select_variables(), select_iso_surfaces()	Load CFD data
5. Rendering	snap_view(), process_region()	Generate screenshots
6. PDF Generation	create_pdf_cover_page(), generate_pdf_report()	Compile final report
7. Main Execution	main()	Orchestrate workflow
Supporting Scripts
converter.py - Convert between OpenFOAM and EnSight formats
processing.py - Post-processing utilities (field operations, data extraction)
Geo_Parameters.py - Extract geometric properties from CFD data
run_visualizer.bat - Windows batch launcher with menu options
🔧 Advanced Usage
Multi-Region Analysis
```JSON
{
    "regions": ["internalMesh", "motorBike_body", "motorBike_wheels"],
    "variables": ["p", "U", "nuT"]
}
```
Multiple Iso-Surfaces
```JSON
{
    "iso_surfaces": [
        {"create": true, "variable": "p", "value": 0.0, "color_by": "U"},
        {"create": true, "variable": "k", "value": 1.0, "color_by": "p"},
        {"create": true, "variable": "nuT", "value": 0.5, "color_by": null}
    ]
}
```
High-Resolution Output
```JSON
{
    "resolution": [7680, 4320],        // 8K screenshots
    "pdf_resolution": [1200, 1600]     // Large PDF pages
}
```
Batch Processing Multiple Cases
Create a Python script:

```Python
import json
import subprocess
import os

cases = ["case1", "case2", "case3"]

for case in cases:
    config = {
        "input_file": f"/data/{case}/{case}.foam",
        "variables": ["p", "U"],
        "regions": ["internalMesh"]
    }
    
    with open(f"{case}_config.json", "w") as f:
        json.dump(config, f)
    
    subprocess.run(["pvpython", "cfd_visualizer.py", f"{case}_config.json"])
```
🐛 Troubleshooting
Issue	Solution
"Pillow not found" error	Run: pvpython -m pip install Pillow
"File not found" error	Use full absolute path to CFD file
Slow rendering	Reduce resolution parameter or use smaller pdf_resolution
PDF not generating	Check that Pillow is installed; raw PNGs will remain if PDF fails
OpenFOAM metadata missing	Ensure log.*, system/controlDict, and postProcessing/ exist
Memory issues	Reduce screenshot resolution or process smaller regions separately
📝 Examples
Example 1: Quick Visualization (Interactive)
```bash
pvpython cfd_visualizer.py
```
# Follow prompts to select file, regions, and variables
Example 2: MotorBike Case (with Config)
```bash
pvpython cfd_visualizer.py setup.json
```
Example 3: ANSYS Case with Custom Zoom
```JSON
{
    "input_file": "/data/simulation/results.encas",
    "zoom_factor": 1.5,
    "zoom_center": [5.0, 2.5, 0.0],
    "variables": ["pressure", "velocity"]
}
```
📚 Resources
ParaView Documentation: https://www.paraview.org/documentation/
OpenFOAM User Guide: https://cfd.direct/openfoam/user-guide/
ANSYS EnSight: https://www.ansys.com/products/visualization
Pillow Documentation: https://python-pillow.org/
📄 License
This project is part of the College of Engineering REU - Summer 2026 program.

👤 Author
cashb (cdbilton-ai)
Michigan Technological University
College of Engineering REU - SP26

For questions or issues, open an issue on GitHub.
