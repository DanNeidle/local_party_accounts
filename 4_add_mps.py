# add_mps.py

import csv
import re
import os

# --- Configuration ---
ANALYSIS_RESULTS_IN = 'analysis_results_checked.csv'
MP_LIST_IN = 'list_of_mps.csv'
OUTPUT_CSV = 'analysis_results_checked2.csv'

# --- Helper Functions ---

def normalize_name(text):
    """
    Normalizes constituency/unit names for comparison.
    - Converts to lowercase
    - Removes 'and' / '&' as whole words
    - Replaces 'st.' or 'st ' with 'saint ' (handles St. Ives etc.)
    - Removes common punctuation (keeps letters, numbers, spaces)
    - Standardizes whitespace
    """
    if not isinstance(text, str):
        return ""
    text = text.lower()
    # Remove 'and', '&' as whole words
    text = re.sub(r'\b(and|&)\b', '', text, flags=re.IGNORECASE)
    # Replace variations of 'saint' abbreviation (st. or st followed by space)
    text = re.sub(r'\bst\.?\b', 'saint', text)
    # Remove characters that are NOT word characters (letters, numbers, underscore) or whitespace
    text = re.sub(r'[^\w\s]', '', text)
    # Standardize whitespace (multiple spaces to one, strip ends)
    text = ' '.join(text.split())
    return text.strip()

def create_canonical_key(text):
    """
    Normalizes, splits, sorts, and rejoins words to create a key
    that is independent of word order.
    """
    normalized = normalize_name(text)
    if not normalized:
        return ""
    words = normalized.split()
    words.sort() # Sort words alphabetically
    return ' '.join(words) # Join sorted words back

# --- Load MP Data into a Lookup Dictionary using Canonical Keys ---
mp_data_lookup = {}
print(f"Loading MP data from {MP_LIST_IN}...")
try:
    # Use os.path.join for better cross-platform compatibility
    mp_file_path = os.path.join(os.getcwd(), MP_LIST_IN) # Assumes file is in the same directory as script
    
    # Check if file exists before trying to open
    if not os.path.exists(mp_file_path):
         raise FileNotFoundError(f"MP list file not found at '{mp_file_path}'")

    with open(mp_file_path, mode='r', newline='', encoding='utf-8-sig') as mp_file: # utf-8-sig handles potential BOM
        # Specify comma delimiter
        reader = csv.DictReader(mp_file, delimiter=',')
        # Check for required headers
        mp_headers = ['Constituency', 'Name (Display as)', 'Email']
        if not reader.fieldnames:
             raise ValueError(f"MP list CSV '{MP_LIST_IN}' appears empty or has no headers.")
        if not all(h in reader.fieldnames for h in mp_headers):
             missing = [h for h in mp_headers if h not in reader.fieldnames]
             raise ValueError(f"MP list CSV '{MP_LIST_IN}' is missing required columns: {', '.join(missing)}")

        count = 0
        duplicates = 0
        skipped_no_constituency = 0
        for row in reader:
            constituency = row.get('Constituency')
            mp_name = row.get('Name (Display as)')
            mp_email = row.get('Email')

            if not constituency:
                skipped_no_constituency += 1
                continue # Skip if constituency name is missing

            # Create the canonical key based on sorted words
            canonical_key = create_canonical_key(constituency)

            if canonical_key: # Ensure key generation didn't result in empty string
                if canonical_key in mp_data_lookup:
                    print(f"Warning: Duplicate canonical key '{canonical_key}' found for constituency '{constituency}'. Overwriting previous entry.")
                    duplicates += 1
                # Store the relevant details using the canonical key
                mp_data_lookup[canonical_key] = {
                    'name': mp_name or '', # Use blank if name missing
                    'email': mp_email or '' # Use blank if email missing
                }
                count += 1
            else:
                 print(f"Warning: Could not generate canonical key for constituency: '{constituency}' (Row: {reader.line_num}). Skipping.")


        print(f"Loaded data for {count} MPs.")
        if duplicates > 0:
            print(f"Warning: Encountered {duplicates} duplicate canonical keys (check constituencies with same words).")
        if skipped_no_constituency > 0:
            print(f"Skipped {skipped_no_constituency} rows due to missing constituency names.")


except FileNotFoundError as fnf:
    print(f"Error: {fnf}")
    exit(1)
except ValueError as ve:
    print(f"Error reading {MP_LIST_IN}: {ve}")
    exit(1)
except Exception as e:
    print(f"An unexpected error occurred reading {MP_LIST_IN}: {e}")
    exit(1)

if not mp_data_lookup:
    print("Warning: No MP data was loaded. Output file will not have MP details.")
    # Consider exiting if MP data is essential
    # exit(1)

# --- Process Analysis Results and Merge MP Data ---
print(f"\nProcessing {ANALYSIS_RESULTS_IN} and writing to {OUTPUT_CSV}...")
processed_rows = 0
matched_rows = 0

try:
    # Use os.path.join for better cross-platform compatibility
    analysis_file_path = os.path.join(os.getcwd(), ANALYSIS_RESULTS_IN)
    output_file_path = os.path.join(os.getcwd(), OUTPUT_CSV)

    # Check if input file exists
    if not os.path.exists(analysis_file_path):
         raise FileNotFoundError(f"Analysis results file not found at '{analysis_file_path}'")

    # Open the input analysis results file
    with open(analysis_file_path, mode='r', newline='', encoding='utf-8') as infile:
        reader = csv.DictReader(infile)
        analysis_fieldnames = reader.fieldnames

        # Check if analysis file has content and required 'unit_name' column
        if not analysis_fieldnames:
             raise ValueError(f"Input file '{ANALYSIS_RESULTS_IN}' seems empty or is not a valid CSV.")
        if 'unit_name' not in analysis_fieldnames:
             raise ValueError(f"Input file '{ANALYSIS_RESULTS_IN}' is missing the required 'unit_name' column.")

        # Define output headers: original headers + new MP headers
        output_fieldnames = analysis_fieldnames + ['mp_name', 'mp_email']

        # Open the output file for writing
        with open(output_file_path, mode='w', newline='', encoding='utf-8') as outfile:
            writer = csv.DictWriter(outfile, fieldnames=output_fieldnames)

            # Write the header row to the new file
            writer.writeheader()

            # Iterate through analysis results rows
            for row in reader:
                processed_rows += 1
                unit_name = row.get('unit_name', '')

                # Create the canonical key for the unit name for matching
                canonical_key_from_analysis = create_canonical_key(unit_name)

                # Look for a match in the MP data lookup using the canonical key
                mp_info = mp_data_lookup.get(canonical_key_from_analysis) # Use .get for safe lookup

                if mp_info:
                    # Match found - add MP details to the row
                    row['mp_name'] = mp_info['name']
                    row['mp_email'] = mp_info['email']
                    matched_rows += 1
                else:
                    # No match found - add blank MP details
                    row['mp_name'] = ''
                    row['mp_email'] = ''
                    # Optional: Log unmatched unit names for investigation
                    # if unit_name and canonical_key_from_analysis: # Only log if there was something to match
                    #    print(f"Debug: No match found for unit '{unit_name}' (key: '{canonical_key_from_analysis}')")


                # Write the enriched/original row to the output file
                writer.writerow(row)

except FileNotFoundError as fnf:
    print(f"Error: {fnf}")
    exit(1)
except ValueError as ve:
    print(f"Error processing {ANALYSIS_RESULTS_IN}: {ve}")
    exit(1)
except Exception as e:
    print(f"An unexpected error occurred processing {ANALYSIS_RESULTS_IN}: {e}")
    exit(1)

print(f"\nProcessing complete.")
print(f" - Processed {processed_rows} rows from {ANALYSIS_RESULTS_IN}.")
print(f" - Found MP matches for {matched_rows} rows using canonical keys.")
print(f" - Output written to {OUTPUT_CSV}.")