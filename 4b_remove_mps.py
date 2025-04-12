import pandas as pd

# Read the original CSV file
df = pd.read_csv("analysis_results_checked.csv")

# Set all values in the 'mp_name' column to empty strings
df['mp_name'] = ""

# Write the modified DataFrame to a new CSV file without the index
df.to_csv("analysis_results_checked2.csv", index=False)

print("Created analysis_results_checked2.csv with 'mp_name' entries cleared.")
