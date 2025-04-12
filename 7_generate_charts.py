import csv
from collections import Counter, defaultdict
import re
import plotly.graph_objects as go
import os

from accounts_secrets import server_destination

# --- Constants ---
THRESHOLD_AMOUNT = 1
THRESHOLD_RATE = 0.10
ACCOUNTING_UNITS_FILE = "accounting_units.csv"
ANALYSIS_RESULTS_FILE = "analysis_results_checked.csv"

# --- Helper Functions ---
# (safe_float_convert and get_combined_name remain the same)
def safe_float_convert(value_str):
    """Safely converts string to float, handling common issues. Returns None on failure."""
    if value_str is None:
        return None
    cleaned_str = re.sub(r"[£,]", "", str(value_str)).strip()
    if not cleaned_str:
        return None
    try:
        return float(cleaned_str)
    except (ValueError, TypeError):
        return None

def get_combined_name(unit_name, entity_name):
    """Creates a standardized combined name. Returns None if inputs are invalid."""
    unit = str(unit_name).strip() if unit_name else ""
    entity = str(entity_name).strip() if entity_name else ""
    if not unit or not entity:
        return None
    return f"{unit} {entity}".lower()

# --- Data Processing Functions ---
# (get_base_unit_counts and analyze_tax_categories remain largely the same)
def get_base_unit_counts(filename=ACCOUNTING_UNITS_FILE):
    """
    Reads accounting units file SOLELY to count total unique units
    and unique units per party (for percentage denominators).
    """
    processed_units = set()
    unique_units_per_party = Counter()
    initial_rows = 0
    skipped_or_duplicates = 0
    try:
        with open(filename, mode='r', encoding='utf-8', newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            if not reader.fieldnames or not all(h in reader.fieldnames for h in ['AccountingUnitName', 'RegulatedEntityName']):
                print(f"Error: File '{filename}' is missing required headers or is empty.")
                return 0, Counter()
            for row in reader:
                initial_rows += 1
                combined_name = get_combined_name(row.get('AccountingUnitName'), row.get('RegulatedEntityName'))
                if combined_name and combined_name not in processed_units:
                    processed_units.add(combined_name)
                    party_name = row.get('RegulatedEntityName', 'Unknown Party').strip() # Get the original name and strip
                    party_name = normalise_party(party_name)
                    unique_units_per_party[party_name] += 1
                else:
                    skipped_or_duplicates += 1
        total_unique_units = len(processed_units)
        print(f"Processed '{filename}': Read {initial_rows} rows, found {total_unique_units} unique units.")
        return total_unique_units, unique_units_per_party
    except FileNotFoundError:
        print(f"Error: Base unit file '{filename}' not found.")
        return 0, Counter()
    except Exception as e:
        print(f"An error occurred processing base unit file '{filename}': {e}")
        return 0, Counter()
    
def normalise_party(party_name):
    if party_name == "Co-operative Party":
        party_name = "Labour Party"
    elif party_name == "Plaid Cymru - The Party of Wales":
        party_name = "Plaid Cymru"
    elif party_name == "Scottish National Party (SNP)":
        party_name = "Scottish National Party"
    elif party_name == "Conservative and Unionist Party":
        party_name = "Conservative"
        
    return party_name


def analyze_tax_categories(analysis_filename=ANALYSIS_RESULTS_FILE):
    """
    Reads analysis file, categorizes each unique unit found WITHIN THIS FILE,
    and counts units per category (overall and per party) for numerators.
    """
    processed_units_in_analysis = set()
    analysis_counts = {'overall': Counter(), 'per_party': defaultdict(Counter)}
    # Define categories and consistent print order
    category_names_map = {
        1: "No rental income",
        2: "Tax paid",
        3: "Low tax paid",
        4: "No tax paid",
        # 5: "Categorization Failed/Invalid Data" # Keep commented unless needed
    }
    # Define the order for stacks in the chart
    category_print_order = [
        category_names_map[1], category_names_map[2], category_names_map[3],
        category_names_map[4] # Add category_names_map[5] if using category 5
    ]
    units_analyzed_count = 0
    rows_read = 0
    units_skipped_count = 0
    try:
        with open(analysis_filename, mode='r', encoding='utf-8', newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            required_headers = ['unit_name', 'entity_name', 'rental_income', 'approx_tax_rate']
            if not reader.fieldnames or not all(h in reader.fieldnames for h in required_headers):
                 print(f"Warning: Analysis file '{analysis_filename}' is missing required headers {required_headers} or is empty. Analysis may be incomplete.")
            for row in reader:
                rows_read += 1
                combined_name = get_combined_name(row.get('unit_name'), row.get('entity_name'))
                if not combined_name or combined_name in processed_units_in_analysis:
                    units_skipped_count += 1
                    continue
                processed_units_in_analysis.add(combined_name)
                units_analyzed_count += 1
                party_name = row.get('entity_name', 'Unknown Party').strip()
                party_name = normalise_party(party_name)
                rental_income = safe_float_convert(row.get('rental_income'))
                tax_rate = safe_float_convert(row.get('approx_tax_rate'))
                category_num = None
                if rental_income is None or rental_income <= THRESHOLD_AMOUNT:
                    category_num = 1
                elif rental_income > THRESHOLD_AMOUNT:
                    if tax_rate is not None and tax_rate >= THRESHOLD_RATE:
                        category_num = 2
                    elif tax_rate is not None and 0 < tax_rate < THRESHOLD_RATE:
                        category_num = 3
                    elif tax_rate is None or tax_rate == 0:
                        category_num = 4
                if category_num is None:
                    # If you decide to handle uncategorized cases:
                    # category_num = 5
                    # print(f"Warning: Unit '{combined_name}' could not be categorized. Row: {row}")
                    # For now, skip units that don't fit categories 1-4 after passing name/duplicate checks
                    units_analyzed_count -= 1 # Decrement because we didn't actually categorize it
                    units_skipped_count += 1
                    processed_units_in_analysis.remove(combined_name) # Remove from processed set
                    continue # Skip to next row

                cat_name = category_names_map[category_num]
                analysis_counts['overall'][cat_name] += 1
                analysis_counts['per_party'][party_name][cat_name] += 1
        print(f"Processed '{analysis_filename}': Read {rows_read} rows, skipped {units_skipped_count} (duplicates/invalid names/uncategorized), analyzed {units_analyzed_count} unique units.")
        # Return category_names_map as well
        return analysis_counts, category_names_map, category_print_order, units_analyzed_count
    except FileNotFoundError:
        print(f"Error: Analysis file '{analysis_filename}' not found.")
        return {'overall': Counter(), 'per_party': defaultdict(Counter)}, category_names_map, category_print_order, 0
    except Exception as e:
        print(f"An error occurred processing analysis file '{analysis_filename}': {e}")
        return {'overall': Counter(), 'per_party': defaultdict(Counter)}, category_names_map, category_print_order, 0

# --- Charting Function ---
# Add text_label_counts_map=None to function signature
def create_stacked_bar_chart(x_labels, y_data_map, category_order, colors, title, y_axis_title, normalize=False, text_label_counts_map=None):
    """
    Creates a Plotly stacked bar chart with improved text and styling.
    Can handle complex labels using text_label_counts_map.
    """
    fig = go.Figure()

    for category_name in category_order:
        if category_name in y_data_map:
            y_values = y_data_map[category_name] # These are counts or percentages
            text_labels = [] # Initialize list for text labels

            # Iterate through y_values with index to access corresponding counts if needed
            for i, y_val in enumerate(y_values):
                text = '' # Default to empty text
                if text_label_counts_map and category_name in text_label_counts_map:
                    # --- Logic for Chart 2 (Percentage chart with counts in label) ---
                    absolute_count = text_label_counts_map[category_name][i]
                    percentage_val = y_val # y_val is the percentage here
                    # Show label only if percentage is >= 1.0% AND count > 0
                    if percentage_val >= 1.0 and absolute_count > 0:
                        # Format: X.X%<newline>(Y,YYY units)
                        text = f"{percentage_val:.1f}%<br>({absolute_count:,d} units)"
                    # else: text remains '' (empty)

                elif not normalize:
                    # --- Logic for Chart 1 (Absolute counts chart) ---
                    absolute_count = y_val # y_val is the count here
                    # Show label only if count > 0
                    if absolute_count > 0:
                        text = f"{int(absolute_count):,d}"
                    # else: text remains '' (empty)

                else:
                    # --- Fallback (Simple percentage label if counts map not provided) ---
                    percentage_val = y_val
                    if percentage_val >= 1.0:
                         text = f"{percentage_val:.1f}%"
                    # else: text remains '' (empty)

                text_labels.append(text) # Add the generated text (or '') to the list

            # Add the trace with potentially complex labels
            fig.add_trace(go.Bar(
                name=category_name,
                x=x_labels,
                y=y_values,
                marker_color=colors.get(category_name, '#808080'),
                text=text_labels, # Use the generated text_labels list
                textposition='inside',
                insidetextanchor='middle', # Center text horizontally
                textfont_size=12
            ))


    fig.update_layout(
        title=dict(
            text=title,
            font=dict(size=20)
        ),
        template="plotly_white",  # Force light mode template
        plot_bgcolor='white',     # Or a specific color instead of transparent
        paper_bgcolor='white',     # Ditto for paper background
        xaxis_title="",
        barmode='stack',
        font=dict(
            family="Poppins, sans-serif",
            size=12,
            color="black"
        ),
        legend=dict(
            traceorder="reversed"
        ),
        margin=dict(l=50, r=40, t=80, b=40),
        uniformtext_minsize=8,
        uniformtext_mode='hide'
    )
    fig.update_yaxes(
        title_text=y_axis_title,
        title_font=dict(size=16)
    )
    if normalize:
        fig.update_yaxes(
            ticksuffix='%',
            range=[0, 100]
       )
    # --- End Layout updates ---

    return fig

# --- Main Execution ---
if __name__ == "__main__":

    print(f"--- Step 1: Calculating Base Unit Counts ({ACCOUNTING_UNITS_FILE}) ---")
    total_units_base, units_per_party_base = get_base_unit_counts(ACCOUNTING_UNITS_FILE)

    if total_units_base == 0:
        print("Could not get base unit counts. Exiting.")
    else:
        print(f"\nTotal Unique Accounting Units (Base): {total_units_base}")
        print("Unique Units Per Party (Base):")
        # Ensure Labour is present if Co-op was merged, even if count is 0 in base
        if "Labour Party" not in units_per_party_base and any("co-operative party" in k.lower() for k in units_per_party_base.keys()):
             print("Note: Co-operative Party merged into Labour Party.")
        
        
        sorted_base_parties_print = sorted(units_per_party_base.items())
        if sorted_base_parties_print:
             for party, count in sorted_base_parties_print:
                 print(f"- {party}: {count}")
        else:
             print("  No party data found in base file.")


        print(f"\n--- Step 2: Analyzing Tax Categories ({ANALYSIS_RESULTS_FILE}) ---")
        print(f"Using Rental Income Threshold: £{THRESHOLD_AMOUNT:.2f}")
        print(f"Using Tax Rate Threshold: {THRESHOLD_RATE:.2f} (10%)")

        # Get initial analysis counts, category map, print order, and analyzed count
        analysis_counts, cat_map, cat_order, num_analyzed = analyze_tax_categories(ANALYSIS_RESULTS_FILE)

        # --- Step 3: Adjust Category 1 counts ---
        print("\n--- Step 3: Adjusting 'No rental income' count to match base totals ---")
        cat1_name = cat_map.get(1, "No rental income")
        current_overall_sum = sum(analysis_counts['overall'].values())
        overall_difference = total_units_base - current_overall_sum
        if overall_difference > 0:
            print(f"Overall: Adding {overall_difference} to '{cat1_name}'.")
            analysis_counts['overall'][cat1_name] = analysis_counts['overall'].get(cat1_name, 0) + overall_difference
        elif overall_difference < 0:
             print(f"Warning: Overall sum analyzed > base total.")
        adjusted_parties = 0
        parties_with_issues = 0
        for party, base_party_count in units_per_party_base.items():
            party_analysis_counts = analysis_counts['per_party'].get(party, Counter())
            current_party_sum = sum(party_analysis_counts.values())
            party_difference = base_party_count - current_party_sum
            if party_difference > 0:
                analysis_counts['per_party'][party][cat1_name] = analysis_counts['per_party'][party].get(cat1_name, 0) + party_difference
                adjusted_parties += 1
            elif party_difference < 0:
                print(f"Warning: Party '{party}' analyzed sum > base total.")
                parties_with_issues += 1
        print(f"Per-Party: Adjusted counts for {adjusted_parties} parties.")
        if parties_with_issues > 0: print(f"Per-Party: Found {parties_with_issues} parties with issues.")
        # --- End Adjustment ---


        # --- Step 4: Prepare Data for Plotting ---
        print("\n--- Step 4: Preparing data for charts ---")

        # Sort parties by count (value) in descending order
        sorted_parties_by_count = sorted(units_per_party_base.items(), key=lambda item: item[1], reverse=True)
        # Extract just the party names in the new order
        sorted_base_parties = [party for party, count in sorted_parties_by_count]

        x_axis_labels = ['Overall'] + sorted_base_parties

        # Prepare data maps
        y_values_numbers = defaultdict(list) # For Chart 1 (Absolute Nums, All Cats)
        y_values_percentages_rental_only = defaultdict(list) # For Chart 2 (Normalized %, Excl Cat 1)
        y_values_counts_for_labels = defaultdict(list) # Absolute counts for Chart 2 labels

        # Define category order for Chart 2 (excluding Category 1)
        # Assumes cat_map has keys 1, 2, 3, 4
        cat_order_rental_only = [cat_map[i] for i in [2, 3, 4] if i in cat_map]
        # Original category order for chart 1 (used later)
        cat_order_all = [cat_map[i] for i in [1, 2, 3, 4] if i in cat_map]


        # Define colors (ensure all needed categories are present)
        infographic_colors = {
            cat_map.get(1, "No rental income"): "#AEC6CF", # Pastel Blue
            cat_map.get(2, "Tax paid"): "#77DD77",         # Pastel Green
            cat_map.get(3, "Low tax paid"): "#FFB347",     # Pastel Orange
            cat_map.get(4, "No tax paid"): "#FF6961",      # Pastel Red
        }

        # Populate the data maps
        for i, x_label in enumerate(x_axis_labels): # Use enumerate to get index i
            if x_label == 'Overall':
                # Use the final adjusted counts (adjustment only affects Cat 1 anyway)
                current_counts = analysis_counts['overall']
                # Base denominator for Chart 1 percentages (though chart 1 is numbers)
                # denominator_base = total_units_base
            else:
                current_counts = analysis_counts['per_party'].get(x_label, Counter())
                # denominator_base = units_per_party_base.get(x_label, 0)

            # --- Data for Chart 1 (Numbers, All Categories) ---
            for category_name in cat_order_all: # Use order including Cat 1
                count = current_counts.get(category_name, 0)
                y_values_numbers[category_name].append(count)

            # --- Data for Chart 2 (Percentages, Rental Income Only) ---
            # Calculate new denominator: sum of counts in categories 2, 3, 4
            denominator_rental_only = sum(current_counts.get(cat_map[cat_key], 0) for cat_key in [2, 3, 4])

            for category_name in cat_order_rental_only: # Use rental-only order (Cats 2, 3, 4)
                # Get the absolute count for this category (for label and percentage calc)
                count = current_counts.get(category_name, 0)
                y_values_counts_for_labels[category_name].append(count) # Store count for label

                # Calculate percentage relative to units *with* rental income
                if denominator_rental_only > 0:
                    percentage = (count / denominator_rental_only) * 100
                else:
                    # If no units have rental income for this party/overall, percentage is 0
                    percentage = 0.0
                y_values_percentages_rental_only[category_name].append(percentage)

        # --- Step 5: Create and Save Charts --- # Changed "Show" to "Save"
print("\n--- Step 5: Generating and saving charts ---")

# Chart 1: Absolute Numbers (using y_values_numbers and cat_order_all)
fig_numbers = create_stacked_bar_chart(
    x_labels=x_axis_labels,
    y_data_map=y_values_numbers,
    category_order=cat_order_all, # Use order including Cat 1
    colors=infographic_colors,
    title="Local parties' rental income and tax",
    y_axis_title='Number of Accounting Units',
    normalize=False # It's counts, not normalized
    # text_label_counts_map is omitted, function uses count logic
)
chart1_filename = "party_accounts_chart_counts.html" # Specific filename
fig_numbers.write_html(chart1_filename)
print(f"Saved counts chart to {chart1_filename}")
 

# Chart 2: Percentages (Normalized, Rental Income Only)
fig_percentages = create_stacked_bar_chart(
    x_labels=x_axis_labels,
    y_data_map=y_values_percentages_rental_only, # Use rental-only % data
    category_order=cat_order_rental_only,      # Use rental-only cat order
    colors=infographic_colors,                 # Reuse colors map
    title="Local parties rental income and tax - percentages where rent received",
    y_axis_title='Percentage of Units with Rental Income (%)', # New axis title
    normalize=True,                            # For y-axis suffix/range
    text_label_counts_map=y_values_counts_for_labels # Pass counts for labels
)
chart2_filename = "party_accounts_chart_percents.html"
fig_percentages.write_html(chart2_filename)
print(f"Saved rental-income-only percentage chart to {chart2_filename}")


print("\n--- Analysis Complete ---")

# --- Step 6: SCP Command ---
# Update scp command to include both files
command = f'scp {chart1_filename} {chart2_filename} {server_destination}'
print(f"Executing: {command}")
os.system(command)