import csv
import math
import html
import os

from accounts_secrets import server_destination

# --- Configuration ---
INPUT_CSV = 'analysis_results_checked.csv'
OUTPUT_HTML = 'party_accounts_table.html'
ACCOUNTS_URL_PREFIX = 'https://taxpolicy.org.uk/wp-content/assets/party_accounts/'

# This can be lowered to include include effective rates under x% in the data.
THRESHOLD_RATE = 1

# And let's ignore income below this amount
THRESHOLD_AMOUNT = 1

# Let's highlight all rows where the tax rate is less than this amount
HIGHLIGHT_THRESHOLD_RATE = 0.15

# for calculating the tax lost
EXPECTED_TAX_RATE = 0.15

# --- Helper Functions ---
def format_tax_rate(rate_str):
    """Formats the approx_tax_rate string into a percentage string.

    Returns:
        tuple: A tuple containing the formatted percentage string for display
               and the original float value for sorting. Returns empty string
               and original value if conversion fails or value is NaN/infinite.
    """
    try:
        rate_float = float(rate_str)
        if math.isnan(rate_float) or math.isinf(rate_float):
            return "", rate_str
        percentage = round(rate_float * 100)
        return f"{percentage}%", rate_float
    except (ValueError, TypeError):
        return "", rate_str

def format_rented_to_mp(value_str):
    """Formats the rented_to_mp string to 'Yes' or blank.

    Returns:
        str: "Yes" if the input string (case-insensitive and stripped) is 'true',
             otherwise an empty string.
    """
    return "Yes" if isinstance(value_str, str) and value_str.strip().lower() == 'true' else ""

def format_rental_income(value_str):
    """Formats rental income for display and provides a numeric value for sorting.

    Returns:
        tuple: A tuple containing the formatted income string (with £ and commas)
               for display and the original float value for sorting. Returns the
               original string and an empty string if conversion fails or value
               is NaN/infinite.
    """
    try:
        num_val = float(value_str)
        if math.isnan(num_val) or math.isinf(num_val):
            return value_str, ""
        return f"£{num_val:,.0f}", num_val
    except (ValueError, TypeError):
        return value_str, ""


# --- Sort Data Initially ---
def sort_key(row):
    rented_to_mp = row.get('rented_to_mp', '').strip().lower() == 'true'
    rental_income_str = row.get('rental_income')
    # Handle potential conversion errors during sorting key generation
    try:
        rental_income = float(rental_income_str) if rental_income_str else -float('inf')
        if math.isnan(rental_income) or math.isinf(rental_income):
            rental_income = -float('inf') # Treat NaN/Inf as lowest income for sorting
    except (ValueError, TypeError):
        rental_income = -float('inf') # Treat invalid strings as lowest income
    return not rented_to_mp, -rental_income # Sort 'Yes' first, then by highest income

# --- Read CSV Data ---
data_rows = []
try:
    with open(INPUT_CSV, mode='r', newline='', encoding='utf-8-sig') as infile:
        reader = csv.DictReader(infile)
        if not reader.fieldnames:
            raise ValueError(f"Could not read headers from {INPUT_CSV}. Is it empty or invalid?")
        print(f"Reading data from {INPUT_CSV}...")
        data_rows = list(reader)
    print(f"Read {len(data_rows)} data rows.")
except FileNotFoundError:
    print(f"Error: Input file '{INPUT_CSV}' not found.")
    exit(1)
except Exception as e:
    print(f"Error reading CSV: {e}")
    exit(1)


# --- Initial Sort ---
data_rows.sort(key=sort_key)


# --- Generate HTML ---


html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Political Parties and corporation tax</title>
  <link rel="icon" href="https://taxpolicy.org.uk/wp-content/assets/logo_emblem_on_blue.jpg" type="image/jpeg">
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;600&display=swap');
    body {{ font-family: 'Poppins', sans-serif; }}

    /* Style for the search filter container */
    .filter-container {{
      text-align: right; /* Align input to the right */
      margin-bottom: 10px; /* Space below the filter */
    }}

    /* Style for the search input */
    #searchInput {{
      padding: 6px 10px;
      font-family: 'Poppins', sans-serif; /* Match body font */
      font-size: 0.9em; /* Match table font size */
      border: 1px solid #D3D3D3; /* Match table border */
      border-radius: 4px; /* Slightly rounded corners */

      /* --- Responsive Width --- */
      width: 50vw;       /* Mobile First: Default to 50% of viewport width */
      min-width: 280px;  /* Minimum width to ensure placeholder fits */
      box-sizing: border-box; /* Include padding/border in the width */
    }}

    /* Media Query for larger screens (tablets and desktops) */
    /* Adjust 768px breakpoint if needed */
    @media (min-width: 768px) {{
      #searchInput {{
        width: 20vw;       /* On screens 768px wide or larger, use 20% viewport width */
        /* max-width: 500px; */ /* Optional: Uncomment and adjust to limit max width on very wide screens */
        /* min-width: 280px from the base rule still applies */
      }}
    }}
    
    /* --- Header Container for Logo and Search --- */
    .header-container {{
      display: flex; /* Enable Flexbox */
      justify-content: space-between; /* Push logo left, search right */
      align-items: center; /* Vertically align items in the middle */
      margin-bottom: 20px; /* Space below the header, adjust as needed */
      flex-wrap: wrap; /* Allow wrapping on very small screens */
      gap: 10px; /* Add gap between items if they wrap */
    }}

    /* --- Logo Styling --- */
    .logo-link {{
      display: block; /* Treat the link as a block for sizing */
      width: 40vw; /* Mobile First: Default logo width */
      min-width: 100px; /* Ensure minimum logo size */
      max-width: 180px; /* Prevent logo getting too large on mobile */
      flex-shrink: 0; /* Prevent logo from shrinking too easily */
    }}
    .logo-link img {{
      width: 100%; /* Make image fill the link container */
      height: auto; /* Maintain aspect ratio */
      display: block; /* Remove extra space below image */
    }}

    /* --- Adjust Filter Container --- */
    .filter-container {{
      /* text-align: right; */ /* Already set */
      margin-bottom: 0px; /* Remove bottom margin, now handled by header-container */
    }}

    /* --- Media Query for Larger Screens (Logo Size) --- */
    @media (min-width: 768px) {{
      .logo-link {{
        width: 20vw; /* Desktop logo width */
        max-width: 200px; /* Optional: Max logo width on desktop */
      }}
      /* Make sure your existing @media query for #searchInput is also present */
      /* If you added it previously, it might look like this: */
      #searchInput {{
         width: 20vw;
         /* max-width: 500px; */
       }}
    }}

    table#resultsTable {{
      border-collapse: collapse;
      width: 100%;
      font-size: 0.9em;
      border: 1px solid #D3D3D3;
    }}
    table#resultsTable th, table#resultsTable td {{
      border: 1px solid #D3D3D3;
      padding: 8px 12px;
      text-align: left;
      vertical-align: top; /* Align content to top */
    }}
    table#resultsTable thead th {{
      background-color: #1133AF; /* Primary color */
      color: white;
      font-weight: 600;
      cursor: pointer; /* Indicate sortable */
      position: relative; /* For sorting icons */
    }}
    /* Sorting indicator styles (simple arrows) */
    table#resultsTable thead th::after {{
      content: '\\2195'; /* Up/Down arrow */
      opacity: 0.3;
      padding-left: 5px;
    }}
    table#resultsTable thead th.sort-asc::after {{ content: '\\2191'; opacity: 1; }} /* Up arrow */
    table#resultsTable thead th.sort-desc::after {{ content: '\\2193'; opacity: 1; }} /* Down arrow */

    table#resultsTable tbody tr:nth-child(even) {{
      /* background-color: #f2f2f2; */ /* Optional: Light grey zebra stripe */
    }}
    table#resultsTable tbody tr:hover {{
      /* background-color: #e0e0e0; */ /* Optional: Hover effect */
    }}
    table#resultsTable td a {{
      color: #1133AF; /* Primary color for links */
      text-decoration: none;
    }}
    table#resultsTable td a:hover {{
      text-decoration: underline;
    }}
    /* Align numeric columns to the right */
    table#resultsTable td:nth-child(3), table#resultsTable td:nth-child(4) {{
      text-align: right;
    }}
    
    /* Very light red for highlighting */
    .highlight-no-tax {{
        background-color: #ffecec; 
    }}
    
    /* Very light amber for highlighting */
    .highlight-low-tax {{
        background-color: #fef1c9; 
    }}
    
    /* Very green for highlighting */
    .highlight-good-tax {{
        background-color: #e2f7ea; 
    }}
    
  </style>
</head>
<body>

  <div class="header-container">
    <a href="https://taxpolicy.org.uk/2025/04/13/local-parties-not-paying-tax/" class="logo-link" target="_blank" rel="noopener noreferrer">
      <img src="https://taxpolicy.org.uk/wp-content/assets/logo_standard.jpg" alt="Tax Policy Associates Logo">
    </a>
    <div class="filter-container">
      <input type="text" id="searchInput" onkeyup="filterTable()" placeholder="Search for MP or constituency...">
    </div>
  </div>

  <table id="resultsTable">
    <thead>
      <tr>
        <th onclick="sortTable(0)">National party</th>
        <th onclick="sortTable(1)">Local party</th>
        <th onclick="sortTable(2, true)">Rental income</th>
        <th onclick="sortTable(3, true)">Tax as a % of rental income</th>
        <th onclick="sortTable(4)">Rented to MP?</th>
        <th onclick="sortTable(5)">MP</th>
      </tr>
    </thead>
    <tbody>
"""

checked = set()
missing_tax = 0
missing_ipsa_tax_single_year = 0
missing_ipsa_tax_all_years = 0
rows_added = 0 # Keep track of rows actually added to the HTML table

for row in data_rows:
    rental_income_str = row.get('rental_income')
    tax_rate_str = row.get('approx_tax_rate')

    # Attempt to convert rental income and handle errors/invalid values early
    try:
        # Use 0 if conversion fails or value is empty/NaN/Inf
        rental_income_float = float(rental_income_str) if rental_income_str else 0.0
        if math.isnan(rental_income_float) or math.isinf(rental_income_float):
            rental_income_float = 0.0
    except (ValueError, TypeError):
        rental_income_float = 0.0 # Default to 0 if conversion fails

    # Skip if rental income is below the threshold
    if rental_income_float < THRESHOLD_AMOUNT:
        continue

    # Attempt to convert tax rate and handle errors/invalid values
    tax_rate_float = None
    if tax_rate_str:
        try:
            tax_rate_float = float(tax_rate_str)
            if math.isnan(tax_rate_float) or math.isinf(tax_rate_float):
                tax_rate_float = None # Treat NaN/Inf as missing tax rate
        except (ValueError, TypeError):
            tax_rate_float = None # Treat invalid strings as missing tax rate

    # Skip if tax rate exists and is above the threshold
    if tax_rate_float is not None and tax_rate_float > THRESHOLD_RATE:
        continue 

    # Calculate missing tax only for rows we are including
    effective_tax_rate = tax_rate_float if tax_rate_float is not None else 0.0
    missing_tax += rental_income_float * max(0, max(0, (EXPECTED_TAX_RATE - effective_tax_rate)))
    if row.get('rented_to_mp') == "TRUE":
        missing_ipsa_tax = rental_income_float * max(0, max(0, (EXPECTED_TAX_RATE - effective_tax_rate)))
        missing_ipsa_tax_single_year += missing_ipsa_tax
        
        years_rented = float(row.get('years_rented_to_mp') or 1)
        missing_ipsa_tax_all_years += missing_ipsa_tax * years_rented


    # Prepare data for HTML row
    party = html.escape(row.get('entity_name', ''))
    constituency = html.escape(row.get('unit_name', ''))
    number = row.get('number', '')
    pdf_url = f"{ACCOUNTS_URL_PREFIX}{html.escape(number)}.pdf" if number else "#"
    link_target = "_blank" if number else ""
    income_display, income_sort_val = format_rental_income(str(rental_income_float)) # Use the validated float
    rate_display, rate_sort_val = format_tax_rate(str(tax_rate_float) if tax_rate_float is not None else "") # Pass valid rate or empty
    rented_mp_display = format_rented_to_mp(row.get('rented_to_mp', ''))
    mp_name = html.escape(row.get('mp_name', ''))

    # Determine if the row should be highlighted
    if tax_rate_float is None or tax_rate_float < 0.005:   # basically zero
        highlight_class_attr = ' class="highlight-no-tax"'
    elif tax_rate_float < HIGHLIGHT_THRESHOLD_RATE:
        highlight_class_attr = ' class="highlight-low-tax"'
    else:
        highlight_class_attr = ' class="highlight-good-tax"'


    # Check for duplicates based on constituency and party
    row_identifier = f"{constituency} {party}"
    if row_identifier in checked:
        print(f"WARNING: Duplicate row identifier skipped: {row_identifier}")
        continue # Skip adding this duplicate row to the HTML
    else:
        checked.add(row_identifier)

    # Add the row to the HTML content
    html_content += f"""\
      <tr{highlight_class_attr}  data-search-content="{party.lower()} {constituency.lower()} {income_display} {rate_display} {rented_mp_display.lower()} {mp_name.lower()}">
        <td>{party}</td>
        <td><a href="{pdf_url}" target="{link_target}">{constituency}</a></td>
        <td data-sort="{income_sort_val}">{income_display}</td>
        <td data-sort="{rate_sort_val}">{rate_display}</td>
        <td>{rented_mp_display}</td>
        <td>{mp_name}</td>
      </tr>
"""
    rows_added += 1 # Increment count of rows added to HTML

html_content += """\
    </tbody>
  </table>
  <script>
let sortDirections = []; // Store direction for each column

// --- Filter Function ---
function filterTable() {
  // Declare variables
  let input, filter, table, tbody, tr, td, i, txtValue;
  input = document.getElementById("searchInput");
  filter = input.value.toLowerCase(); // Case-insensitive filter
  table = document.getElementById("resultsTable");
  tbody = table.getElementsByTagName("tbody")[0];
  tr = tbody.getElementsByTagName("tr");

  // Loop through all table rows, and hide those who don't match the search query
  for (i = 0; i < tr.length; i++) {
    // Check the pre-compiled search content in the data attribute for efficiency
    const searchContent = tr[i].getAttribute('data-search-content') || '';

    if (searchContent.indexOf(filter) > -1) {
        tr[i].style.display = ""; // Show row
    } else {
        tr[i].style.display = "none"; // Hide row
    }

    /* // Alternative: Check all cells (less efficient for many columns)
    let found = false;
    td = tr[i].getElementsByTagName("td");
    for (let j = 0; j < td.length; j++) {
        if (td[j]) {
            txtValue = td[j].textContent || td[j].innerText;
            if (txtValue.toLowerCase().indexOf(filter) > -1) {
                found = true;
                break; // Found a match in this row, no need to check other cells
            }
        }
    }
    if (found) {
        tr[i].style.display = "";
    } else {
        tr[i].style.display = "none";
    }
    */
  }
}


// --- Sort Function ---
function sortTable(columnIndex, isNumeric = false) {
  const table = document.getElementById("resultsTable");
  const tbody = table.tBodies[0];
  const rows = Array.from(tbody.rows);
  const headerCell = table.tHead.rows[0].cells[columnIndex];

  // Determine sort direction (asc, desc, or initial asc)
  const currentDirection = sortDirections[columnIndex];
  let direction = 'asc';
  if (currentDirection === 'asc') {
    direction = 'desc';
  }
  sortDirections = []; // Reset all directions visually first
  sortDirections[columnIndex] = direction;

  // --- Sorting Logic ---
  rows.sort((rowA, rowB) => {
    const cellA = rowA.cells[columnIndex];
    const cellB = rowB.cells[columnIndex];
    let valA, valB;

    if (isNumeric) {
      // Use data-sort attribute for numeric comparison
      valA = parseFloat(cellA.getAttribute('data-sort') || '-Infinity'); // Treat blanks/errors as very small
      valB = parseFloat(cellB.getAttribute('data-sort') || '-Infinity');
       // Handle potential NaN values from parseFloat
      if (isNaN(valA)) valA = -Infinity;
      if (isNaN(valB)) valB = -Infinity;

    } else {
      // Use textContent for string comparison
      valA = cellA.textContent.trim().toLowerCase();
      valB = cellB.textContent.trim().toLowerCase();
    }

    // Comparison logic
    if (valA < valB) {
      return direction === 'asc' ? -1 : 1;
    }
    if (valA > valB) {
      return direction === 'asc' ? 1 : -1;
    }
    return 0; // Values are equal
  });

  // --- Update Table Display ---
  // Detach tbody temporarily for performance during reordering
  const parent = tbody.parentNode;
  parent.removeChild(tbody);

  // Append sorted rows back to the tbody
  rows.forEach(row => tbody.appendChild(row));

  // Re-attach tbody to the table
  parent.appendChild(tbody);


  // Update header visual indicators
  table.tHead.rows[0].querySelectorAll('th').forEach(th => {
    th.classList.remove('sort-asc', 'sort-desc');
  });
  headerCell.classList.add(direction === 'asc' ? 'sort-asc' : 'sort-desc');
}
</script>
</body>
</html>
"""

# --- Write HTML to File ---
try:
    with open(OUTPUT_HTML, 'w', encoding='utf-8') as f:
        f.write(html_content)
    print(f"\nSuccessfully generated HTML table with search filter: {OUTPUT_HTML}")
    print(f"Included {rows_added} rows in the table.")
except Exception as e:
    print(f"\nError writing HTML file: {e}")

print(f"Total approx missing tax: £{missing_tax:,.0f}")
print(f"Approx missing ipsa tax for one year: £{missing_ipsa_tax_single_year:,.0f}")
print(f"Approx missing ipsa tax for all years: £{missing_ipsa_tax_all_years:,.0f}")

# --- SCP Command (Optional) ---
# Check if server_destination is defined and not empty before running scp
if 'server_destination' in locals() and server_destination:
    command = f'scp "{OUTPUT_HTML}" "{server_destination}"' # Quote paths for safety
    print(f"Executing: {command}")
    # Consider adding error handling for the scp command if needed
    exit_code = os.system(command)
    if exit_code == 0:
        print("File successfully transferred.")
    else:
        print(f"Warning: scp command failed with exit code {exit_code}.")
else:
    print("Skipping scp command as server_destination is not configured.")