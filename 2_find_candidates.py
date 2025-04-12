import os
import PyPDF2 
import re 
import csv

# reduces LLM load by finding accounts containing the word "rent"
# this wasn't actually very useful - only eliminated 300 out of the 1,300

def find_keyword_pages(filename):
    """
    Searches a PDF file for case-insensitive occurrences of "tax" and "rent"
    and returns the page numbers where they are found.

    Args:
        filename (str): The path to the PDF file.

    Returns:
        tuple: A tuple containing two sets: 
               (set_of_tax_pages, set_of_rent_pages).
               Page numbers are 1-based.
               Returns (set(), set()) if the file cannot be read or text extraction fails.
    """
    tax_pages = set()
    rent_pages = set()
    
    try:
        # Open the PDF file
        with open(filename, 'rb') as pdf_file:
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            
            # Iterate through all pages
            for page_num in range(len(pdf_reader.pages)):
                try:
                    page = pdf_reader.pages[page_num]
                    text = page.extract_text()
                    
                    if text:
                        # Use regex for case-insensitive partial matching with word boundaries
                        # Add page_num + 1 (to make it 1-based) to the set if found
                        if re.search(r"\btax(es)?\b", text, re.IGNORECASE): # Check for tax or taxes
                            tax_pages.add(page_num + 1)
                            
                        if re.search(r"\brent(al)?\b", text, re.IGNORECASE): # Check for rent or rental
                            rent_pages.add(page_num + 1)
                            
                except Exception as page_error:
                    # Handle potential issues with specific pages (e.g., encrypted, corrupted)
                    print(f"Warning: Could not process page {page_num + 1} in {filename}. Error: {page_error}")
                    continue # Continue to the next page
                    
    except FileNotFoundError:
        print(f"Error: File not found - {filename}")
        return set(), set() # Return empty sets if file doesn't exist
    except PyPDF2.errors.PdfReadError as pdf_error:
        print(f"Error: Could not read PDF - {filename}. Error: {pdf_error}")
        return set(), set() # Return empty sets if PDF is invalid/corrupted
    except Exception as e:
        print(f"An unexpected error occurred while processing {filename}: {e}")
        return set(), set() # Return empty sets for other errors

    # Return the sets of page numbers
    return tax_pages, rent_pages
                    

# --- Main Script ---

input_csv_filename = 'accounting_units.csv'
output_csv_filename = 'text_search_results.csv'
pdf_directory = 'accounts' # Specify the directory where PDFs are stored

units = {}

# Read the input CSV
try:
    with open(input_csv_filename, mode='r', newline='', encoding='utf-8-sig') as csvfile:
        reader = csv.DictReader(csvfile)
        # Check if required columns exist
        if not all(col in reader.fieldnames for col in ['ECRef', 'AccountingUnitName', 'RegulatedEntityName']):
             raise ValueError("Input CSV must contain 'ECRef', 'AccountingUnitName', and 'RegulatedEntityName' columns.")

        # Iterate through each row and store the data
        for row in reader:
             # Basic check for empty ECRef
            if row['ECRef']:
                units[row['ECRef']] = (row['AccountingUnitName'], row['RegulatedEntityName'])
            else:
                print(f"Warning: Skipping row with missing ECRef: {row}")

except FileNotFoundError:
    print(f"Error: Input CSV file not found - {input_csv_filename}")
    exit() # Exit if the input file is essential and missing
except ValueError as ve:
     print(f"Error: {ve}")
     exit()
except Exception as e:
    print(f"An error occurred reading {input_csv_filename}: {e}")
    exit()


# Open the output CSV file for writing
try:
    with open(output_csv_filename, mode='w', newline='', encoding='utf-8') as outfile:
        # Define column headers for the output CSV
        fieldnames = ['number', 'unit_name', 'entity_name', 'tax_pages', 'rent_pages']
        writer = csv.writer(outfile)
        
        # Write the header row
        writer.writerow(fieldnames)
        
        print(f"Processing {len(units)} units...")
        
        # Iterate through the units, process PDFs, and write to output CSV
        count = 0
        for number, names in units.items():
            count += 1
            unit_name, entity_name = names
            
            # Construct the full path to the PDF file
            filename = os.path.join(pdf_directory, f"{number}.pdf")
            
            print(f"Processing {count}/{len(units)}: {filename} for unit {number}...")

            # Initialize page number strings as empty
            tax_pages_str = ""
            rent_pages_str = ""

            # Check if the PDF file exists before attempting to process
            if os.path.exists(filename):
                # Find pages where keywords appear
                tax_pages_set, rent_pages_set = find_keyword_pages(filename)
                
                # Format the page numbers for the CSV output
                # Sort the page numbers numerically before joining
                if tax_pages_set:
                    tax_pages_str = ", ".join(map(str, sorted(list(tax_pages_set))))
                if rent_pages_set:
                    rent_pages_str = ", ".join(map(str, sorted(list(rent_pages_set))))
                
                # Write the data row to the CSV
                writer.writerow([number, unit_name, entity_name, tax_pages_str, rent_pages_str])
                # Optional: print status to console
                # print(f"  -> Results for {number}: Tax Pages='{tax_pages_str}', Rent Pages='{rent_pages_str}'")

            else:
                # Handle case where PDF file doesn't exist for a unit
                print(f"  -> Warning: PDF file not found for unit {number} at {filename}. Skipping.")
                # Write a row indicating the file was missing, with empty page strings
                writer.writerow([number, unit_name, entity_name, "PDF not found", "PDF not found"])
                

        print(f"\nProcessing complete. Results written to {output_csv_filename}")

except IOError as e:
    print(f"Error writing to output CSV file {output_csv_filename}: {e}")
except Exception as e:
    print(f"An unexpected error occurred during processing: {e}")