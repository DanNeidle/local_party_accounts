
import pandas as pd
import numpy as np

# this retains only the most recent accounts from each accounting unit

# Define input and output filenames
# data is from https://search.electoralcommission.org.uk/Search/Accounts?currentPage=1&rows=10&sort=TotalIncome&order=desc&open=filter&et=pp&year=2025&year=2024&year=2023&year=2022&year=2021&year=2020&year=2019&year=2018&year=2017&year=2016&year=2015&year=2014&year=2013&year=2012&year=2011&year=2010&year=2009&year=2008&year=2007&year=2006&year=2005&year=2004&year=2003&year=2002&year=2001&register=gb&register=ni&register=none&regStatus=registered&rptBy=accountingunits&optCols=BandName
input_filename = 'accounting_units.csv'
output_filename = 'accounting_units2.csv'

# don't keep any accounts earlier than this date:
EARLIEST_ACCOUNTS = 2021

print(f"Starting filtering and de-duplication process for '{input_filename}'...")

try:
    # Read the CSV file into a pandas DataFrame
    # Specify dtype={'ECRef': str, 'ReportingPeriodDescription': str} to ensure correct initial reading
    df = pd.read_csv(input_filename, dtype={'ECRef': str, 'ReportingPeriodDescription': str})
    print(f"Read {len(df)} rows from '{input_filename}'.")
    initial_rows = len(df)

    # --- Data Cleaning and Preparation ---

    # Handle potential whitespace issues in key columns
    df['RegulatedEntityName'] = df['RegulatedEntityName'].str.strip()
    df['AccountingUnitName'] = df['AccountingUnitName'].str.strip()
    df['ECRef'] = df['ECRef'].str.strip()
    df['RegisterName'] = df['RegisterName'].str.strip()
    df['ReportingPeriodDescription'] = df['ReportingPeriodDescription'].str.strip()

    # --- Filtering Step 1: Reporting Period Description ---
    print("Filtering by ReportingPeriodDescription...")
    # Convert ReportingPeriodDescription to numeric (year), coercing errors to NaN
    # Using errors='coerce' handles cases where the value isn't a simple year number
    df['ReportingYear_Numeric'] = pd.to_numeric(df['ReportingPeriodDescription'], errors='coerce')

    # Keep rows where the numeric year is EARLIEST_ACCOUNTS or greater
    # This automatically handles/drops rows where conversion resulted in NaN
    rows_before_year_filter = len(df)
    df = df[df['ReportingYear_Numeric'] >= EARLIEST_ACCOUNTS]
    rows_after_year_filter = len(df)
    print(f"Filtered out {rows_before_year_filter - rows_after_year_filter} rows with ReportingPeriodDescription < 2021 or non-numeric.")

    # --- Filtering Step 2: Register Name ---
    print("Filtering by RegisterName...")
    rows_before_register_filter = len(df)
    # Keep rows where RegisterName is exactly 'Great Britain' (case-sensitive)
    df = df[df['RegisterName'] == 'Great Britain']
    rows_after_register_filter = len(df)
    print(f"Filtered out {rows_before_register_filter - rows_after_register_filter} rows where RegisterName was not 'Great Britain'.")


    # Check if DataFrame is empty after filtering, before proceeding
    if df.empty:
        print("DataFrame is empty after applying filters. No data to de-duplicate or save.")
    else:
        # --- De-duplication Preparation ---
        # Create a numeric version of ECRef for sorting (only for remaining rows)
        df['ECRef_Numeric'] = pd.to_numeric(
            df['ECRef'].str.replace('ST', '', case=False, regex=False),
            errors='coerce' # If conversion fails, set to NaN
        )

        invalid_ecr_count = df['ECRef_Numeric'].isna().sum()
        if invalid_ecr_count > 0:
            print(f"Warning: Within the filtered data, {invalid_ecr_count} rows had ECRef values that could not be converted to numeric after removing 'ST'. These might be treated unexpectedly during sorting.")
            # df['ECRef_Numeric'].fillna(-1, inplace=True) # Option to handle NaNs explicitly

        # --- Sorting ---
        print("Sorting filtered data...")
        df_sorted = df.sort_values(
            by=['RegulatedEntityName', 'AccountingUnitName', 'ECRef_Numeric'],
            ascending=[True, True, False], # Sort names ascending, ECRef descending
            na_position='last' # Place rows with invalid ECRefs last
        )

        # --- De-duplication ---
        print("Dropping duplicates...")
        df_deduplicated = df_sorted.drop_duplicates(
            subset=['RegulatedEntityName', 'AccountingUnitName'],
            keep='first' # Keeps the row with the highest ECRef_Numeric due to sorting
        )

        # --- Final Cleanup ---
        # Drop the temporary numeric columns
        df_final = df_deduplicated.drop(columns=['ECRef_Numeric', 'ReportingYear_Numeric'])

        # --- Saving Output ---
        df_final.to_csv(output_filename, index=False)

        print(f"\nProcess completed successfully.")
        print(f"Initial rows: {initial_rows}")
        print(f"Rows after filtering (Year >= 2021 & Register = 'Great Britain'): {rows_after_register_filter}")
        print(f"Rows after de-duplication: {len(df_final)}")
        print(f"Results saved to '{output_filename}'")

except FileNotFoundError:
    print(f"Error: Input file '{input_filename}' not found. Please make sure it's in the same directory as the script or provide the full path.")
except KeyError as e:
    print(f"Error: Column '{e}' not found in the CSV. Please check the header row in '{input_filename}'. Expected columns include 'RegulatedEntityName', 'AccountingUnitName', 'ECRef', 'ReportingPeriodDescription', and 'RegisterName'.")
except Exception as e:
    print(f"An unexpected error occurred: {e}")