import os
import json
import csv
import io
import logging
from dotenv import load_dotenv
from utils import (
    read_text_file, 
    get_contract_data,
    PDFReadError, 
    JSONParsingError, 
    LLMConfigurationError, 
    LLMGenerationError
)

# --- Configuration ---
CONTRACT_FILE_PATH = "Lore SaaS Agreement and Order Form April 2025.md"  # Hardcoded path to the test contract
OUTPUT_JSON_FILE = "contract_output.json"
OUTPUT_CSV_FILE = "contract_output.csv"

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load environment variables from .env file
load_dotenv()

def main():
    logging.info("Starting contract processing...")

    # --- API Key Configuration ---
    api_key = os.getenv('GOOGLE_API_KEY')
    if not api_key:
        logging.error("GOOGLE_API_KEY environment variable not set. Please set it to run the application.")
        print("Error: GOOGLE_API_KEY environment variable not set.")
        return

    # --- Read Contract File ---
    contract_text = None
    try:
        logging.info(f"Reading contract file: {CONTRACT_FILE_PATH}")
        if not os.path.exists(CONTRACT_FILE_PATH):
            logging.error(f"Contract file not found: {CONTRACT_FILE_PATH}")
            print(f"Error: Contract file not found at {CONTRACT_FILE_PATH}")
            return
        contract_text = read_text_file(CONTRACT_FILE_PATH)
        logging.info(f"Successfully read contract file. Length: {len(contract_text)} characters.")
    except FileNotFoundError:
        # This is already handled by the os.path.exists check, but good for robustness
        logging.error(f"File not found: {CONTRACT_FILE_PATH}")
        print(f"Error: File not found at {CONTRACT_FILE_PATH}")
        return
    except IOError as e:
        logging.error(f"IOError reading file {CONTRACT_FILE_PATH}: {e}")
        print(f"Error reading file: {e}")
        return
    except Exception as e:
        logging.error(f"An unexpected error occurred reading the contract file: {e}", exc_info=True)
        print(f"An unexpected error occurred during file reading: {e}")
        return

    if not contract_text:
        logging.warning("Contract text is empty. Aborting.")
        print("Contract text could not be read or is empty. Cannot proceed.")
        return

    # --- Process Contract with LLM ---
    extracted_data = None
    try:
        logging.info("Extracting data from contract using LLM...")
        extracted_data = get_contract_data(contract_text, api_key)
        logging.info("Successfully extracted data from contract.")

        # --- Output JSON --- 
        print("\n--- Extracted Contract Data (JSON) ---")
        formatted_json = json.dumps(extracted_data, indent=2)
        print(formatted_json)
        print("--- End JSON Data ---")

        # Save JSON to file
        try:
            with open(OUTPUT_JSON_FILE, 'w', encoding='utf-8') as f_json:
                f_json.write(formatted_json)
            logging.info(f"JSON output saved to {OUTPUT_JSON_FILE}")
        except IOError as e:
            logging.error(f"Error writing JSON to file {OUTPUT_JSON_FILE}: {e}")
            print(f"Error saving JSON output: {e}")

        # --- Convert and Output CSV (Transposed) --- 
        if extracted_data:
            try:
                # In-memory string for printing to console
                output_csv_string = io.StringIO()
                writer = csv.writer(output_csv_string)
                # Write key-value pairs, one per row
                for key, value in extracted_data.items():
                    writer.writerow([key, value])
                
                csv_content = output_csv_string.getvalue()
                output_csv_string.close()
                
                print("\n--- Extracted Contract Data (CSV) ---")
                print(csv_content.strip())
                print("--- End CSV Data ---")

                # Save transposed CSV to file
                with open(OUTPUT_CSV_FILE, 'w', encoding='utf-8', newline='') as f_csv:
                    file_writer = csv.writer(f_csv)
                    for key, value in extracted_data.items():
                        file_writer.writerow([key, value])
                logging.info(f"Transposed CSV output saved to {OUTPUT_CSV_FILE}")

            except (IOError, TypeError) as e:
                logging.error(f"Error generating or writing CSV: {e}")
                print(f"\nCould not convert or save data to CSV format: {e}")
        else:
            logging.info("No data extracted, skipping CSV generation.")

    except LLMConfigurationError as e:
        logging.error(f"LLM Configuration Error: {e}")
        print(f"LLM Configuration Error: {e}")
    except LLMGenerationError as e:
        logging.error(f"LLM Generation Error: {e}")
        print(f"LLM Generation Error: {e}")
    except JSONParsingError as e:
        logging.error(f"JSON Parsing Error: {e}")
        print(f"JSON Parsing Error: {e}")
    except ValueError as e: # Catch ValueErrors from get_contract_data (empty text/key)
        logging.error(f"ValueError during processing: {e}")
        print(f"Error: {e}")
    except Exception as e:
        logging.error(f"An unexpected error occurred during contract processing: {e}", exc_info=True)
        print(f"An unexpected error occurred: {e}")

    logging.info("Contract processing finished.")

if __name__ == "__main__":
    main() 