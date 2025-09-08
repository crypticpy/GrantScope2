import requests
import time
import json
import os
from typing import Tuple, Sequence, Optional
from tqdm import tqdm

# Prefer centralized config for secrets (works when run via package or as script)
try:
    from GrantScope import config  # when executed via package context
except Exception:
    try:
        import config  # fallback when executed inside GrantScope/ directly
    except Exception:
        config = None  # type: ignore

def get_grants_transactions(
    page_number,
    year_range,
    dollar_range,
    subjects,
    populations,
    locations,
    transaction_types,
    retries: int = 3,
    backoff: float = 1.5,
    timeout: int = 30,
):
    """
    Fetch a page of grants transactions from Candid API with basic backoff/validation.

    Args:
        page_number: 1-based page index to request.
        year_range: tuple(start_year, end_year) inclusive.
        dollar_range: tuple(min_amount, max_amount).
        subjects, populations, locations, transaction_types: sequences of strings for filters.
        retries: number of retry attempts for transient errors (e.g., 429).
        backoff: base backoff seconds; multiplied exponentially per attempt.
        timeout: HTTP request timeout in seconds.

    Raises:
        RuntimeError for missing/invalid API key or unrecoverable HTTP errors.
        Exception for non-HTTP request issues after retries are exhausted.

    Returns:
        Parsed JSON dict from the API response.
    """
    start_year, end_year = year_range
    min_amt, max_amt = dollar_range

    url = (
        f"https://api.candid.org/grants/v1/transactions?"
        f"page={page_number}"
        f"&location={','.join(locations)}"
        f"&geo_id_type=geonameid"
        f"&location_type=area_served"
        f"&year={','.join(map(str, range(start_year, end_year + 1)))}"
        f"&subject={','.join(subjects)}"
        f"&population={','.join(populations)}"
        f"&support="
        f"&transaction={','.join(transaction_types)}"
        f"&recip_id=&funder_id=&include_gov=yes"
        f"&min_amt={min_amt}&max_amt={max_amt}"
        f"&sort_by=year_issued&sort_order=desc&format=json"
    )

    # Resolve API key with precedence via centralized config (st.secrets > env > .env)
    candid_key: Optional[str] = None
    if config is not None:
        try:
            candid_key = config.get_candid_key()
        except Exception:
            candid_key = None
    # Fallback to environment if config is unavailable
    if not candid_key:
        candid_key = os.getenv("CANDID_API_KEY")

    if not candid_key:
        raise RuntimeError(
            "Missing required configuration: CANDID_API_KEY. "
            "Set st.secrets['CANDID_API_KEY'] (Streamlit) or environment variable CANDID_API_KEY."
        )

    headers = {
        "accept": "application/json",
        "Subscription-Key": candid_key,
    }

    # Normalize retry count
    retries = max(0, int(retries))
    attempt = 0
    while True:
        try:
            response = requests.get(url, headers=headers, timeout=timeout)

            # Explicit handling for common failures
            if response.status_code == 401:
                raise RuntimeError(
                    "Unauthorized (401) from Candid API. Verify that CANDID_API_KEY is valid."
                )

            if response.status_code == 429:
                if attempt < retries:
                    # Exponential backoff with jitter-free simple growth
                    sleep_s = backoff * (2 ** attempt)
                    time.sleep(sleep_s)
                    attempt += 1
                    continue
                raise RuntimeError(
                    "Rate limited (429) by Candid API after retries. "
                    "Reduce request rate or try again later."
                )

            # Raise for other HTTP errors
            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            if attempt < retries:
                sleep_s = backoff * (2 ** attempt)
                time.sleep(sleep_s)
                attempt += 1
                continue
            raise Exception(f"Error getting grants transactions after retries: {e}")

def validate_input(value, value_type, min_value=None, max_value=None):
    try:
        parsed_value = value_type(value)
        if min_value is not None and parsed_value < min_value:
            raise ValueError(f"Value should be greater than or equal to {min_value}")
        if max_value is not None and parsed_value > max_value:
            raise ValueError(f"Value should be less than or equal to {max_value}")
        return parsed_value
    except ValueError as e:
        raise ValueError(f"Invalid input: {e}")

def get_unique_file_name(file_name):
    base_name, extension = os.path.splitext(file_name)
    counter = 1
    while os.path.exists(file_name):
        file_name = f"{base_name}_{counter}{extension}"
        counter += 1
    return file_name

def main():
    calls_per_minute = 9
    delay = 60 / calls_per_minute

    print("Welcome to the Candid API Grants Data Fetcher!")
    print("This tool will guide you through the process of fetching grants data from the Candid API.")

    try:
        start_year = validate_input(input("Enter the start year: "), int, min_value=1900, max_value=2100)
        end_year = validate_input(input("Enter the end year: "), int, min_value=start_year, max_value=2100)
        year_range = (start_year, end_year)

        min_amt = validate_input(input("Enter the minimum dollar amount (e.g., 25000): "), int, min_value=0)
        max_amt = validate_input(input("Enter the maximum dollar amount (e.g., 10000000): "), int, min_value=min_amt)
        dollar_range = (min_amt, max_amt)

        subjects = input("Enter the subjects (comma-separated, e.g., SJ02,SJ05): ").split(",")
        populations = input("Enter the populations (comma-separated, e.g., PA010000,PC040000): ").split(",")
        locations = input("Enter the locations (comma-separated geonameid, e.g., 4671654,4736286): ").split(",")
        transaction_types = input("Enter the transaction types (comma-separated, e.g., TA,TG): ").split(",")

        num_pages = input("Enter the number of pages to retrieve (or 'all' for all pages): ")
        if num_pages.lower() == 'all':
            num_pages = None
        else:
            num_pages = validate_input(num_pages, int, min_value=1)

        output_file = input("Enter the output file name (e.g., grants_data.json): ")
        output_file = get_unique_file_name(output_file)

        all_grants = []
        page_number = 1

        print("Fetching grants data...")
        while True:
            grants_data = get_grants_transactions(page_number, year_range, dollar_range, subjects, populations, locations, transaction_types)
            all_grants.extend(grants_data["grants"])

            total_pages = grants_data["total_pages"]
            progress_bar = tqdm(total=total_pages, unit='page', desc='Progress', initial=page_number)

            if num_pages is None and total_pages == page_number:
                break
            elif num_pages is not None and page_number == num_pages:
                break

            page_number += 1
            progress_bar.update(1)
            time.sleep(delay)  # Pause for required delay time

        progress_bar.close()

        with open(output_file, "w") as f:
            json.dump({"grants": all_grants}, f, indent=2)

        print(f"Grants data saved to {output_file}")
        print("Thank you for using the Candid API Grants Data Fetcher!")

    except ValueError as e:
        print(f"Error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()