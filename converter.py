from paraview.simple import *
import os
import sys

# ================================================================
# 1. INTERACTIVE PROMPT
# ================================================================
print("="*60)
print("  ENSIGHT (.encas) TO VTK CONVERTER")
print("="*60)
print("Instruction: Drag and drop your .encas file here and press Enter.")
print("")

raw_path = input("File Path > ")
input_file = raw_path.strip().replace('"', '').replace("'", "")

if not os.path.exists(input_file):
    print(f"\n[ERROR] File not found: {input_file}")
    sys.exit(1)

if not input_file.lower().endswith('.encas'):
    print("\n[WARNING] This file does not end in .encas. Attempting to proceed anyway...")

# Automatically figure out where to save the .vtk file
output_dir = os.path.dirname(input_file)
base_name = os.path.splitext(os.path.basename(input_file))[0]
output_file = os.path.join(output_dir, f"{base_name}_converted.vtk")

print("-" * 60)
print(f"Target File: {os.path.basename(input_file)}")
print(f"Output File: {os.path.basename(output_file)}")
print("-" * 60)

# ================================================================
# 2. CONVERSION PIPELINE
# ================================================================

try:
    print("1. Loading EnSight data")
    # OpenDataFile handles .encas natively
    reader = OpenDataFile(input_file)
    if not reader:
        raise RuntimeError("ParaView failed to initialize the EnSight reader.")
    reader.UpdatePipeline()

    print("2. Merging")
    # EnSight data MUST be merged before saving to a standard .vtk
    merged_data = MergeBlocks(Input=reader)
    merged_data.UpdatePipeline()

    print("3. Writing to .vtk format...")
    # SaveData automatically chooses the Legacy VTK Writer based on the .vtk extension
    SaveData(output_file, proxy=merged_data)

    print("="*60)
    print(f"Converted file saved to:\n{output_file}")
    print("="*60)

except Exception as e:
    print(f"\n[ERROR] The conversion failed. Details: {e}")
    sys.exit(1)