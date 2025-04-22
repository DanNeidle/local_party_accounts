import csv
from collections import Counter, defaultdict
import re
import plotly.graph_objects as go
import os

from accounts_secrets import server_destination

# --- Constants ---
THRESHOLD_AMOUNT = 1
THRESHOLD_RATE = 0.15
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
        party_name = "Labour"
    elif party_name == "Labour Party":
        party_name = "Labour"
    elif party_name == "Plaid Cymru - The Party of Wales":
        party_name = "Plaid Cymru"
    elif party_name == "Scottish National Party (SNP)":
        party_name = "Scottish National Party"
    elif party_name == "Conservative and Unionist Party":
        party_name = "Conservative"
        
    return party_name

##########
# --- Data Processing Functions ---
# (safe_float_convert, get_combined_name, get_base_unit_counts, normalise_party remain the same)

def analyze_tax_categories(analysis_filename=ANALYSIS_RESULTS_FILE):
    """
    Reads analysis file, categorizes each unique unit found WITHIN THIS FILE,
    and counts units per category (overall and per party) for numerators.
    Also counts units specifically rented to MPs.
    """
    processed_units_in_analysis = set()
    analysis_counts = {'overall': Counter(), 'per_party': defaultdict(Counter)}
    
    # Dictionary to store counts for MP rentals only
    mp_rental_counts = {'overall': Counter(), 'per_party': defaultdict(Counter)}

    category_names_map = {
        1: "No rental income", 2: "Tax paid", 3: "Low tax paid", 4: "No tax paid",
    }
    category_print_order = [
        category_names_map[1], category_names_map[2], category_names_map[3], category_names_map[4]
    ]
    units_analyzed_count = 0
    units_analyzed_mp_rental_count = 0
    rows_read = 0
    units_skipped_count = 0
    try:
        with open(analysis_filename, mode='r', encoding='utf-8', newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            required_headers = ['unit_name', 'entity_name', 'rental_income', 'approx_tax_rate', 'rented_to_mp']
            if not reader.fieldnames or not all(h in reader.fieldnames for h in required_headers):
                 print(f"Warning: Analysis file '{analysis_filename}' is missing required headers {required_headers} or is empty. Analysis may be incomplete.")
                 # Allow continuation even if 'rented_to_mp' is missing, but MP chart might be empty

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
                
                rented_to_mp_value = row.get('rented_to_mp', '').strip() # Default to empty string

                category_num = None
                # (Categorization logic remains the same)
                if rental_income is None or rental_income <= THRESHOLD_AMOUNT:
                    category_num = 1
                elif rental_income > THRESHOLD_AMOUNT:
                    if tax_rate is not None and tax_rate >= THRESHOLD_RATE:
                        category_num = 2
                    elif tax_rate is not None and 0.005 < tax_rate < THRESHOLD_RATE:  # 0.005 is basically zero
                        category_num = 3
                    else:
                        category_num = 4

                if category_num is None:
                    units_analyzed_count -= 1
                    units_skipped_count += 1
                    processed_units_in_analysis.remove(combined_name)
                    continue

                cat_name = category_names_map[category_num]
                # Increment standard counts
                analysis_counts['overall'][cat_name] += 1
                analysis_counts['per_party'][party_name][cat_name] += 1

                # Check rented_to_mp and increment MP rental counts if "True"
                if rented_to_mp_value.lower() == "true":
                    units_analyzed_mp_rental_count += 1
                    mp_rental_counts['overall'][cat_name] += 1
                    mp_rental_counts['per_party'][party_name][cat_name] += 1

        print(f"Processed '{analysis_filename}': Read {rows_read} rows, skipped {units_skipped_count} (duplicates/invalid names/uncategorized), analyzed {units_analyzed_count} unique units.")
        print(f"Found {units_analyzed_mp_rental_count} unique units rented to MPs ('rented_to_mp' == 'True').")

        return analysis_counts, mp_rental_counts, category_names_map, category_print_order, units_analyzed_count, units_analyzed_mp_rental_count

    except FileNotFoundError:
        print(f"Error: Analysis file '{analysis_filename}' not found.")
        return {'overall': Counter(), 'per_party': defaultdict(Counter)}, {'overall': Counter(), 'per_party': defaultdict(Counter)}, category_names_map, category_print_order, 0, 0
    except Exception as e:
        print(f"An error occurred processing analysis file '{analysis_filename}': {e}")
        return {'overall': Counter(), 'per_party': defaultdict(Counter)}, {'overall': Counter(), 'per_party': defaultdict(Counter)}, category_names_map, category_print_order, 0, 0


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
                        text = f"{percentage_val:.1f}%<br>({absolute_count:,d} parties)"
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
                textfont_size=14
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
            size=14,
            color="black"
        ),
        legend=dict(
            traceorder="reversed",
            font=dict(
                family="Poppins, sans-serif",
                size=20,
                color="black"
            )
        ),
        margin=dict(l=50, r=40, t=80, b=40),
        uniformtext_minsize=10,
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



if __name__ == "__main__":

    print(f"--- Step 1: Calculating Base Unit Counts ({ACCOUNTING_UNITS_FILE}) ---")
    total_units_base, units_per_party_base = get_base_unit_counts(ACCOUNTING_UNITS_FILE)

    if total_units_base == 0:
        print("Could not get base unit counts. Exiting.")
        exit(1)
        

    print(f"\nTotal Unique Accounting Units (Base): {total_units_base}")
    # (Print base counts logic remains the same)
    # ...

    print(f"\n--- Step 2: Analyzing Tax Categories ({ANALYSIS_RESULTS_FILE}) ---")
    print(f"Using Rental Income Threshold: £{THRESHOLD_AMOUNT:.2f}")
    print(f"Using Tax Rate Threshold: {THRESHOLD_RATE:.2f} (10%)")

    analysis_counts, mp_rental_counts, cat_map, cat_order_all, num_analyzed, num_analyzed_mp = analyze_tax_categories(ANALYSIS_RESULTS_FILE)

    # --- Step 3: Adjust Category 1 counts (ONLY for the main analysis_counts) ---
    print("\n--- Step 3: Adjusting 'No rental income' count (main analysis) to match base totals ---")
    # (Adjustment logic remains the same, operating *only* on analysis_counts)
    # ...
    cat1_name = cat_map.get(1, "No rental income")
    current_overall_sum = sum(analysis_counts['overall'].values())
    overall_difference = total_units_base - current_overall_sum
    if overall_difference > 0:
        print(f"Overall: Adding {overall_difference} to '{cat1_name}'.")
        analysis_counts['overall'][cat1_name] = analysis_counts['overall'].get(cat1_name, 0) + overall_difference
    # ... (rest of adjustment logic for analysis_counts['per_party']) ...

    # --- Step 4: Prepare Data for Plotting ---
    print("\n--- Step 4: Preparing data for charts ---")

    # (Sorting parties logic remains the same)
    sorted_parties_by_count = sorted(units_per_party_base.items(), key=lambda item: item[1], reverse=True)
    sorted_base_parties = [party for party, count in sorted_parties_by_count]
    x_axis_labels = ['Overall'] + sorted_base_parties

    # Prepare data maps
    y_values_numbers = defaultdict(list)                # For Chart 1 (Adjusted Nums, All Cats)
    y_values_percentages_rental_only = defaultdict(list) # For Chart 2 (Normalized %, Excl Cat 1)
    y_values_counts_for_labels = defaultdict(list)       # Absolute counts for Chart 2 labels
    y_values_numbers_mp_rental = defaultdict(list)

    # (Define category orders and colors - remains the same)
    cat_order_rental_only = [cat_map[i] for i in [2, 3, 4] if i in cat_map]
    # cat_order_all already defined from analyze_tax_categories return

    infographic_colors = {
        cat_map.get(1, "No rental income"): "#AEC6CF", # Pastel Blue
        cat_map.get(2, "Tax paid"): "#77DD77",         # Pastel Green
        cat_map.get(3, "Low tax paid"): "#FFB347",     # Pastel Orange
        cat_map.get(4, "No tax paid"): "#FF6961",      # Pastel Red
    }

    # Populate the data maps
    for x_label in x_axis_labels:
        if x_label == 'Overall':
            current_counts = analysis_counts['overall'] # Adjusted counts for chart 1 & 2 base
            current_mp_counts = mp_rental_counts['overall']
        else:
            current_counts = analysis_counts['per_party'].get(x_label, Counter()) # Adjusted
            current_mp_counts = mp_rental_counts['per_party'].get(x_label, Counter()) # Unadjusted

        # --- Data for Chart 1 (Adjusted Numbers, All Categories) ---
        for category_name in cat_order_all:
            count = current_counts.get(category_name, 0)
            y_values_numbers[category_name].append(count)

        # --- Data for Chart 2 (Percentages, Rental Income Only - based on Adjusted counts) ---
        denominator_rental_only = sum(current_counts.get(cat_map[cat_key], 0) for cat_key in [2, 3, 4])
        for category_name in cat_order_rental_only:
            count = current_counts.get(category_name, 0)
            y_values_counts_for_labels[category_name].append(count)
            percentage = (count / denominator_rental_only) * 100 if denominator_rental_only > 0 else 0.0
            y_values_percentages_rental_only[category_name].append(percentage)

        for category_name in cat_order_all:
            # Use the unadjusted mp_rental counts directly
            count_mp = current_mp_counts.get(category_name, 0)
            y_values_numbers_mp_rental[category_name].append(count_mp)


    # --- Step 5: Create and Save Charts ---
    print("\n--- Step 5: Generating and saving charts ---")

    # Chart 1: Absolute Numbers (Adjusted)
    fig_numbers = create_stacked_bar_chart(
        x_labels=x_axis_labels,
        y_data_map=y_values_numbers, # Uses adjusted counts
        category_order=cat_order_all,
        colors=infographic_colors,
        title="Local parties' rental income and tax",
        y_axis_title='Number of local parties',
        normalize=False
    )
    chart1_filename = "party_accounts_chart_counts.html"
    fig_numbers.write_html(chart1_filename)
    print(f"Saved counts chart to {chart1_filename}")

    # Chart 2: Percentages (Normalized, Rental Income Only - based on Adjusted counts)
    fig_percentages = create_stacked_bar_chart(
        x_labels=x_axis_labels,
        y_data_map=y_values_percentages_rental_only,
        category_order=cat_order_rental_only,
        colors=infographic_colors,
        title="Local parties rental income and tax - percentages where rent received",
        y_axis_title="% of local parties with rental income",
        normalize=True,
        text_label_counts_map=y_values_counts_for_labels
    )
    chart2_filename = "party_accounts_chart_percents.html"
    fig_percentages.write_html(chart2_filename)
    print(f"Saved rental-income-only percentage chart to {chart2_filename}")

    # --- Chart 3: Absolute Numbers (MP Rentals Only, Unadjusted) ---
    fig_numbers_mp = create_stacked_bar_chart(
        x_labels=x_axis_labels,
        y_data_map=y_values_numbers_mp_rental,
        category_order=cat_order_rental_only,
        colors=infographic_colors,
        title="Local parties' rental income and tax where rented to local MP", # New title
        y_axis_title='Number of local parties', # Same y-axis as chart 1
        normalize=False # Display absolute counts
        # No text_label_counts_map needed as normalize=False handles simple count labels
    )
    chart3_filename = "party_accounts_chart_counts_mp_rentals.html" # New filename
    fig_numbers_mp.write_html(chart3_filename)
    print(f"Saved MP rental counts chart to {chart3_filename}")


    print("\n--- Analysis Complete ---")

    # --- Step 6: SCP Command ---
    command = f'scp {chart1_filename} {chart2_filename} {chart3_filename} {server_destination}'
    print(f"Executing: {command}")
    os.system(command)
    print("\nAll done!")