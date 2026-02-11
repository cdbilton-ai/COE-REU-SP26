# Geo Parameters

import pandas as pd
import os  # To check if files exist

# Set how many files you want to check (e.g., from 1 to 10)
start_num = 1
end_num = 20  

# Loop from start_num to end_num
for i in range(start_num, end_num + 1):
    
    # Construct the filename dynamically: geo_parameters_1.csv, geo_parameters_2.csv, etc.
    filename = f'geo_parameters_{i}.csv'
    
    # Check if the file actually exists to avoid crashing
    if os.path.exists(filename):
        print(f"Processing Run {i}\n")
       
        # Load the data
        df = pd.read_csv(filename)

        # Your existing logic to print columns
        for column_name in df.columns:
            print(f"{column_name}")
            
            for value in df[column_name]:
                print(value)
            print("\n")
            
    else:
        print(f"Warning: {filename} was not found.\n")


