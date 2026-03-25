# Multi-Format CFD Visualizer

An automated, interactive Python script for generating standardized CFD reports from OpenFOAM (`.foam`, `.simpleFoam`) and ANSYS EnSight (`.encas`, `.case`) datasets. 

This script loads mesh data, prompts the user for specific regions and variables, generates standard orthographic and isometric screenshots, and compiles the results into a single PDF summary with a data table.

## 1. Prerequisites & Installation

This script relies on the ParaView Python API (`paraview.simple`). Because ParaView uses its own bundled version of Python, **you must run this script using ParaView's Python executable (`pvpython`), not your standard system Python.**

### Required Libraries
* `paraview.simple` (Included with ParaView)
* `Pillow` (Required for PDF compilation and drawing the data table)

### Installing Pillow for ParaView
To compile the PDF, you need to install `Pillow` into ParaView's specific Python environment. 
Open your command prompt or terminal and use the `pip` executable bundled inside your ParaView installation folder:

**Windows:**
```bash
"C:\Program Files\ParaView 5.x.x\bin\pvpython.exe" -m pip install Pillow
```
**Mac/Linux:**
```bash
/Applications/ParaView-5.x.x.app/Contents/bin/pvpython -m pip install Pillow
```
*(Note: Replace `5.x.x` with your actual ParaView version).*

##  2. How to Operate the Script

1. Open your terminal or command prompt.
2. Run the script using `pvpython`:
   ```bash
   pvpython cfd_visualizer.py
   ```
3. **File Prompt:** The script will ask you to drag and drop your `.encas` or `.foam` file into the terminal.
4. **Region Selection (OpenFOAM only):** Enter the comma-separated numbers of the mesh regions you want to process (e.g., `0, 3`).
5. **Variable Selection:** The script will scan the file and list available variables (e.g., `p`, `U`, `k`). Type the ones you want to plot, separated by commas.
6. **Slicing:** For 3D volumes, you will be prompted to either take a 2D slice (`x`, `y`, or `z` normal) or render the full 3D volume.
7. Let the script run. It will automatically take screenshots and compile the final PDF.

## 3. Expected File Structure

For the metadata parser to successfully extract Force Coefficients, Cell Counts, and Solve Times, your project folders should follow standard solver structures.

### OpenFOAM (`.foam` or `.simpleFoam`)
The script looks for standard OpenFOAM directories relative to the input file:
```text
📂 Case_Folder/
 ├── 📄 open.foam            <-- Drag this into the script
 ├── 📄 log.simpleFoam       <-- Read for solver version, date, and solve time
 ├── 📂 system/
 │    └── 📄 controlDict     <-- Read for Reference Area (Aref)
 └── 📂 postProcessing/
      └── 📂 forceCoeffs/    <-- Read (.dat files) for final C_D and C_L values

### ANSYS / EnSight (`.encas` or `.case`)
📂 Case_Folder/
 ├── 📄 results.encas        <-- Drag this into the script
 ├── 📄 results.geom
 └── 📄 results.0000.p       <-- Data files

## 4. Output Information

All outputs are saved in a new folder called `Images` created in the same directory as your input file.

* **`Run_X.pdf`:** The final compiled report containing the data table and all screenshots.
* **`Run_X_settings.txt`:** A text file logging the exact regions, variables, and slices used to generate this run for future reproducibility.
* **Raw PNGs:** The script automatically deletes the raw `.png` screenshots to save space after the PDF is created. *(If Pillow fails to load, the PDF creation is skipped, and the raw PNGs are kept).*

## 5. How to Modify Camera Views

Camera angles are defined in **Section 5** of the script. To add or change angles, locate the `views_to_take` list. 

Angles are defined as tuples: `("View_Name", [Camera_Position_Vector], [View_Up_Vector])`

```python
views_to_take = [
    ("front",     [1, 0, 0],   [0, 0, 1]),  # Looks down the X-axis, Z is up
    ("side",      [0, 1, 0],   [0, 0, 1]),  # Looks down the Y-axis, Z is up
    ("top",       [0, 0, 1],   [1, 0, 0]),  # Looks down the Z-axis, X is up
    ("front_iso", [1, 1, 1],   [0, 0, 1]),  # Isometric view
    ("rear_iso",  [-1, 1, 1],  [0, 0, 1])   # Reverse isometric
]
```
To create a custom view, simply add a new row. The vector `[1, 0, 0]` means the camera sits on the positive X-axis looking toward the origin `(0,0,0)`.