#!/usr/bin/env python

# downloads all the most recent local party accounts by scraping the Electoral Commission website
# scraping is a bit rude - ideally they'd make all the accounts available for bulk download

import csv
import requests

import time
import os
import time
import requests # For making HTTP requests
from urllib.parse import urljoin, urlparse # For constructing absolute URLs
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# note constructed url specifies account years. Will need changing in the future.


def download_accounts_document(url: str) -> bytes | None:
    """
    Navigates to a given URL using Selenium, finds a specific "Download" link
    pointing to '/Api/Accounts/Documents/...', constructs the full URL,
    downloads the linked document directly using HTTP request, and returns its content.

    Args:
        url: The URL of the webpage containing the download link.

    Returns:
        The content of the downloaded document as bytes if successful,
        otherwise None. Returns None if the link isn't found or the download fails.
    """
    driver = None
    # --- WebDriver Setup ---
    try:
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument("--window-size=1920,1080") 
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36")
        # Add any other necessary options
        driver = webdriver.Chrome(options=options)

        # print(f"Navigating to: {url}")
        driver.get(url)
        time.sleep(2) # Add a small fixed wait for dynamic content if needed, though explicit wait is better

        # --- Define Link Locator (More Specific based on HTML) ---
        # Find an <a> tag with the exact text "Download" AND
        # whose href attribute starts with '/Api/Accounts/Documents/'
        xpath_locator = "//a[text()='Download' and starts-with(@href, '/Api/Accounts/Documents/')]"
        link_locator_tuple = (By.XPATH, xpath_locator)

        # --- Wait for the Link and Extract href ---
        try:
            # Wait up to 15 seconds for the link to be present and clickable
            wait = WebDriverWait(driver, 15)
            # Using presence_of_element_located is often enough to get the href
            link_element = wait.until(EC.presence_of_element_located(link_locator_tuple))
            # Alternative: wait until clickable if interaction is needed later
            # link_element = wait.until(EC.element_to_be_clickable(link_locator_tuple))

            relative_href = link_element.get_attribute('href')
            print(f"Found link with relative href: {relative_href}")

            if not relative_href:
                 print("Error: Found link element but href attribute is empty.")
                 return None

            # --- Construct Full URL ---
            # Use the current URL from the browser after navigation as the base
            # This handles potential redirects from the initial 'url'
            current_page_url = driver.current_url
            full_document_url = urljoin(current_page_url, relative_href)
            # print(f"Constructed full document URL: {full_document_url}")

            # --- Download using Requests ---
            # print("Attempting to download document directly...")
            try:
                # It's good practice to use a session if multiple requests might be needed,
                # or if the site relies on cookies set by Selenium's navigation.
                # We can try transferring cookies from Selenium to requests.
                selenium_cookies = driver.get_cookies()
                request_session = requests.Session()
                for cookie in selenium_cookies:
                    request_session.cookies.set(cookie['name'], cookie['value'], domain=cookie['domain'])

                # Make the GET request using the session
                # Set a reasonable timeout (e.g., 30 seconds)
                headers = { # Mimic browser headers if needed
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
                response = request_session.get(full_document_url, timeout=60, headers=headers) # Increased timeout for potentially large files

                # Check if the request was successful (status code 2xx)
                response.raise_for_status()

                print(f"Download successful (Status Code: {response.status_code}). Content length: {len(response.content)} bytes.")
                # Return the raw byte content of the response
                return response.content

            except requests.exceptions.RequestException as req_err:
                print(f"Error downloading document via requests: {req_err}")
                # Potentially log response.status_code and response.text for debugging
                # print(f"Response status: {response.status_code if 'response' in locals() else 'N/A'}")
                # print(f"Response text: {response.text[:500] if 'response' in locals() else 'N/A'}") # Print first 500 chars
                return None
            except Exception as e:
                 print(f"An unexpected error occurred during download: {e}")
                 return None


        except TimeoutException:
            print(f"Error: Timed out waiting for the Download link using XPath: {xpath_locator}")
            return None
        except NoSuchElementException:
             print(f"Error: Could not find the Download link using XPath: {xpath_locator}")
             return None
        except Exception as e:
            print(f"An unexpected error occurred while finding/processing the link: {e}")
            return None

    except Exception as e:
        print(f"An error occurred during WebDriver setup or navigation: {e}")
        return None

    finally:
        # --- Cleanup ---
        if driver:
            # print("Closing browser.")
            driver.quit()




units = {}

# Open the CSV file
with open('accounting_units.csv', newline='', encoding='utf-8-sig') as csvfile:
    reader = csv.DictReader(csvfile)
    
    # Iterate through each row and print the ECRef column
    for row in reader:
        units[row['ECRef']] = f"{row['AccountingUnitName']} {row['RegulatedEntityName']}"
        
for number, name  in units.items():
    
    filename = f"accounts/{number}.pdf"
        
    print(f"\n{number}: {name}")
    
    if os.path.exists(filename):
        print("Already exists")
        continue

    search_url = f"https://search.electoralcommission.org.uk/Search/Accounts?currentPage=1&rows=1&query={number}&sort=PublishedDate&order=desc&open=filter&et=pp&et=ppm&et=tp&et=perpar&et=rd&year=2025&year=2023&year=2024&year=2022&year=2021&year=2020&register=gb&regStatus=registered&rptBy=accountingunits&optCols=PublishedDate&optCols=FinancialYearEnd&optCols=BandName&optCols=SoaType"
    accounts = download_accounts_document(search_url)
    
    if accounts:
        with open(filename, "wb") as file:
            file.write(accounts)
        print(f"Saved")
        
    else:
        print(f"Nothing found")
        
    time.sleep(1)
        
print("Completed! You may want to run a second time to catch any that errored\n")
print("Now ocr using command:\n")
print("for file in *.pdf; do")
print('   ocrmypdf "$file" "ocr/$file"')
print("done")
    
    