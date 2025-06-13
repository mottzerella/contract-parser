import google.generativeai as genai
import PyPDF2
import os
import json
from datetime import datetime
import re
import io
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Configuration ---
MODEL_NAME = "models/gemini-2.5-pro-preview-03-25"

# --- Custom Exceptions ---
class PDFReadError(Exception):
    """Custom exception for errors during PDF reading."""
    pass

class JSONParsingError(Exception):
    """Custom exception for errors during JSON parsing."""
    pass

class LLMConfigurationError(Exception):
    """Custom exception for errors configuring the LLM."""
    pass

class LLMGenerationError(Exception):
    """Custom exception for errors during LLM content generation."""
    pass


# --- Helper Functions (Standalone) ---

def read_pdf(file_input):
    """
    Reads text content from a PDF file.

    Args:
        file_input: Either a string representing the file path or a file-like
                    object (e.g., io.BytesIO) containing the PDF data.

    Returns:
        A string containing the extracted text from the PDF.

    Raises:
        FileNotFoundError: If file_input is a path and the file doesn't exist.
        TypeError: If file_input is not a string path or a file-like object.
        PDFReadError: If there's an error reading or parsing the PDF content.
    """
    text = "" # Initialize as empty string
    file_stream = None
    is_path = isinstance(file_input, str)

    try:
        if is_path:
            if not os.path.exists(file_input):
                raise FileNotFoundError(f"Error: PDF file not found at '{file_input}'.")
            file_stream = open(file_input, 'rb')
        elif hasattr(file_input, 'read'):
            # Assume it's a file-like object (e.g., uploaded file bytes)
            # Ensure it's treated as bytes
            if isinstance(file_input, io.TextIOBase):
                 # If it's TextIO, try to get the underlying buffer if possible,
                 # otherwise, it might be problematic. Best if BytesIO is passed.
                 logging.warning("Received TextIOBase, attempting to use buffer. Pass BytesIO for reliability.")
                 if hasattr(file_input, 'buffer'):
                     file_stream = file_input.buffer
                 else:
                      raise TypeError("Cannot process TextIOBase without a byte buffer.")
            elif isinstance(file_input, io.BytesIO):
                 file_input.seek(0) # Reset position
                 file_stream = file_input # Use it directly
            else:
                 # Attempt to read bytes if it has a read method but isn't recognized BytesIO
                 try:
                     file_input.seek(0)
                     content_bytes = file_input.read()
                     if not isinstance(content_bytes, bytes):
                          raise TypeError("File-like object did not read bytes.")
                     file_stream = io.BytesIO(content_bytes)
                 except Exception as e:
                     raise TypeError(f"Unsupported file-like object type: {type(file_input)}. Error: {e}")

        else:
            raise TypeError("Invalid input type. Expected file path string or bytes file-like object.")

        if file_stream is None:
             raise ValueError("Could not obtain a valid byte stream from the input.")

        reader = PyPDF2.PdfReader(file_stream)
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n" # Add newline between pages

        return text

    except PyPDF2.errors.PdfReadError as e:
        logging.error(f"PyPDF2 error reading PDF: {e}")
        raise PDFReadError(f"Error reading PDF: Invalid PDF file or structure. Original error: {e}")
    except Exception as e:
        logging.error(f"Unexpected error reading PDF: {e}", exc_info=True)
        # Re-raise specific known errors or a general one
        if isinstance(e, (FileNotFoundError, TypeError)):
             raise e
        raise PDFReadError(f"An unexpected error occurred reading the PDF: {e}")
    finally:
        # Close the stream only if it was opened from a file path
        if is_path and file_stream and not file_stream.closed:
            file_stream.close()


def read_text_file(filepath):
    """
    Reads text content from a generic text file (e.g., .md, .txt).

    Args:
        filepath: The path to the text file.

    Returns:
        A string containing the content of the file.

    Raises:
        FileNotFoundError: If the file doesn't exist.
        IOError: If there's an error reading the file.
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        logging.error(f"Error: Text file not found at '{filepath}'.")
        raise
    except IOError as e:
        logging.error(f"Error reading text file '{filepath}': {e}")
        raise


def build_llm_prompt(contract_text):
    """
    Builds the LLM prompt with contract text and JSON instructions.
    This prompt is used to extract structured data from a contract.
    """
    prompt = f"""
Parse the following contract text into a JSON object. Adhere strictly to the specified fields, data types, formats, and accepted categorical values. If information for a field is not found, use null where allowed, or follow the specific instructions for that field.

Return ONLY the JSON object, without any introductory text, explanations, or markdown formatting.

JSON Structure and Instructions:

{{
  "Partner Name": {{
    "description": "The name of the partner per the contract denoted as 'Subscriber'",
    "type": "String",
    "value": "Extract from contract"
  }},
  "Effective date": {{
    "description": "The effective date of the contract",
    "type": "MM/DD/YYYY",
    "value": "Find the date in the contract (e.g., 'Month DD, YYYY', 'MM/DD/YYYY', etc.) and convert it to MM/DD/YYYY format. Use null if not found."
  }},
  "Term length (days)": {{
    "description": "The length of the contract in days",
    "type": "Integer",
    "value": "Calculate or extract integer, null if not specified"
  }},
  "Termination date": {{
    "description": "The end date of the contract",
    "type": "MM/DD/YYYY",
    "value": "Find the date in the contract (e.g., 'Month DD, YYYY', 'MM/DD/YYYY', etc.) and convert it to MM/DD/YYYY format. Use null if not found."
  }},
  "Active Lore User Pricing/month": {{
    "description": "The price Lore is charging per user, per month",
    "type": "$ Integer",
    "value": "Extract integer value, null if not specified"
  }},
  "Eligible users": {{
    "description": "Number of eligible users",
    "type": "Integer",
    "value": 0
  }},
  "Lore users": {{
    "description": "Number of Lore users",
    "type": "Integer",
    "value": 0
  }},
  "Total Monthly Active Users": {{
    "description": "Total MAU",
    "type": "Integer",
    "value": 0
  }},
  "Community Access": {{
    "description": "Whether the signing Partner will provide access to the Lore community",
    "type": "Boolean",
    "value": "Extract True/False, null if not specified"
  }},
  "Data deletion policy (lorebot)": {{
    "description": "Does the contract explicitly stipulate a requirement for Lore to routinely delete user personal data upon request or after a certain period? This must be a specific term. Set to True only if this specific policy is mentioned, otherwise False.",
    "type": "Boolean",
    "value": "Extract True/False"
  }},
  "Timeframe (hours)": {{
    "description": "If 'Data deletion policy (lorebot)' is True, extract the timeframe (in hours) within which data must be deleted. Use null if no timeframe is specified.",
    "type": "Integer",
    "value": "Extract integer, null if no policy or not specified"
  }},
  "Dependents allowed": {{
    "description": "Are dependents included in the list of eligible users?",
    "type": "Boolean",
    "value": "Extract True/False, null if not specified"
  }},
  "Eligibility": {{
    "description": "Whether all employees are included or only those on insurance ('all' or 'only_insured')",
    "type": "String",
    "accepted_values": ["all", "only_insured"],
    "value": "Extract value or null"
  }},
  "Reconciliation Start Date": {{
    "description": "Calculate and provide the estimated start date for financial reconciliation based on other contract dates and terms (e.g., 'Effective Date' + 'Term Length'). If it's a condition, state the condition (e.g., 'After 12 months of Phase 2'). Use null if not mentioned.",
    "type": "MM/DD/YYYY or String",
    "value": "Calculate or extract condition, null if not applicable"
  }},
  "Reconciliation entity and cost": {{
    "description": "The entity responsible for reconciliation and any associated costs, if specified. This may be TBD. Use null if not mentioned or if no reconciliation.",
    "type": "String",
    "value": "Extract entity and cost details or TBD, null if not applicable"
  }},
  "Population of eligible users": {{
    "description": "Categorize the eligible user population based on the contract description.",
    "type": "String",
    "accepted_values": ["Employees Only", "Employees and Dependents", "Medicare", "Medicare Advantage", "Other"],
    "value": "Categorize and select one value from accepted_values"
  }},
  "Limit on number of users": {{
    "description": "The maximum number of users for the main contract term (ignore any limits specific only to a trial period). Use 0 if no limit is explicitly stated for the full agreement.",
    "type": "Integer",
    "value": "Extract number, or 0 if unlimited/not specified"
  }},
  "Data sharing agreement or business associate agreement": {{
    "description": "Specify if a 'Data sharing agreement' or 'Business associate agreement' (BAA) is mentioned. Should be one or the other if applicable, not both. Use null if neither is mentioned.",
    "type": "String",
    "accepted_values": ["Data sharing agreement", "Business associate agreement", null],
    "value": "Extract agreement type, or null"
  }},
  "Performance Reports Frequency": {{
    "description": "The frequency of performance reports provided to the partner (e.g., monthly, quarterly).",
    "type": "String",
    "value": "Extract frequency (e.g., monthly), null if not specified"
  }},
  "Users permitted to convert Lore points to money": {{
    "description": "Can users convert points to money (e.g., gift cards)? Set to True or False.",
    "type": "Boolean",
    "value": "Extract True/False, null if not specified"
  }},
  "Trial period": {{
    "description": "If a trial period is offered, extract its duration in days as an integer (e.g., 90). If no trial period is mentioned, use the boolean value false.",
    "type": "Integer or Boolean",
    "value": "Extract integer days, or the boolean value false if not specified"
  }}
}}

Contract Text:
--- START CONTRACT ---
{contract_text}
--- END CONTRACT ---

JSON Output:
"""
    return prompt

def parse_llm_response(response_text):
    """
    Parses the LLM response string to extract the JSON object.

    Args:
        response_text: The raw string response from the LLM.

    Returns:
        A dictionary containing the extracted 'value' for each field defined
        in the expected JSON structure.

    Raises:
        JSONParsingError: If valid JSON cannot be found or decoded, or if the
                          structure doesn't match expectations (e.g., missing 'value').
    """
    if not response_text or not isinstance(response_text, str):
        raise JSONParsingError("Invalid or empty response text received.")

    json_str = None
    # Attempt to extract JSON, handling markdown fences or raw JSON
    match = re.search(r"```json\s*({.*?})\s*```", response_text, re.DOTALL | re.IGNORECASE)
    if match:
        json_str = match.group(1).strip()
    else:
        # If no markdown fences, find the outermost curly braces
        start = response_text.find('{')
        end = response_text.rfind('}')
        if start != -1 and end != -1 and end > start:
            json_str = response_text[start:end+1].strip()

    if not json_str:
        logging.error(f"Could not find JSON block in response. Raw response: {response_text[:500]}...")
        raise JSONParsingError("Could not find valid JSON structure in the LLM response.")

    try:
        # Load the JSON string into a Python dictionary
        parsed_json = json.loads(json_str)

        # Basic validation: Check if it's a dictionary
        if not isinstance(parsed_json, dict):
             raise JSONParsingError(f"Parsed JSON is not a dictionary. Found type: {type(parsed_json)}")

        # Extract the 'value' from each field, be robust to missing 'value' key
        extracted_data = {}
        for k, v in parsed_json.items():
             if isinstance(v, dict):
                 extracted_data[k] = v.get('value', None) # Use None if 'value' key is missing
             else:
                  # Handle cases where the value might not be a dict as expected by the prompt
                  logging.warning(f"Unexpected structure for key '{k}' in parsed JSON. Expected dict, got {type(v)}. Using raw value: {v}")
                  extracted_data[k] = v # Assign the value directly, might need downstream handling

        return extracted_data

    except json.JSONDecodeError as e:
        logging.error(f"JSONDecodeError: {e}. Raw string: {json_str[:500]}...")
        raise JSONParsingError(f"Error decoding JSON from LLM response: {e}. Check response format.")
    except Exception as e:
        logging.error(f"Unexpected error during JSON parsing: {e}", exc_info=True)
        raise JSONParsingError(f"An unexpected error occurred during JSON parsing: {e}")


def get_contract_data(contract_text, api_key):
    """
    Sends the contract text to the Gemini LLM and parses the structured data response.

    Args:
        contract_text: The string content of the contract.
        api_key: The Gemini API key.

    Returns:
        A dictionary containing the parsed contract data.

    Raises:
        ValueError: If contract_text or api_key is empty.
        LLMConfigurationError: If the API key is invalid or the model cannot be initialized.
        LLMGenerationError: If the API call fails or returns an error (e.g., blocked prompt).
        JSONParsingError: If the LLM response cannot be parsed into the expected JSON structure.
    """
    if not contract_text:
        raise ValueError("Contract text cannot be empty.")
    if not api_key:
        raise ValueError("API key must be provided.")

    try:
        # Configure the API key (important to do before initializing model)
        genai.configure(api_key=api_key)
        # Initialize the model
        model = genai.GenerativeModel(MODEL_NAME)
    except Exception as e:
        logging.error(f"Error initializing Gemini model ({MODEL_NAME}): {e}", exc_info=True)
        raise LLMConfigurationError(f"Error initializing Gemini model ({MODEL_NAME}): {e}. Check API key and model name.")

    prompt = build_llm_prompt(contract_text)

    try:
        response = model.generate_content(prompt)
        response_text = None

        # Safely access response text, handling different potential structures/errors
        if hasattr(response, 'text'):
            response_text = response.text
        elif hasattr(response, 'prompt_feedback') and response.prompt_feedback.block_reason:
            block_reason = response.prompt_feedback.block_reason
            safety_ratings = response.prompt_feedback.safety_ratings
            logging.error(f"LLM content generation blocked. Reason: {block_reason}. Ratings: {safety_ratings}")
            raise LLMGenerationError(f"Content generation blocked due to safety settings. Reason: {block_reason}")
        elif isinstance(response, str): # Some APIs might return string directly
             response_text = response
        else:
            # Log unexpected structure and raise error
            response_type = type(response)
            logging.error(f"Unexpected response structure from LLM: {response_type}. Response: {response}")
            raise LLMGenerationError(f"Could not extract text from LLM response. Unexpected type: {response_type}")

        if response_text is None:
             raise LLMGenerationError("Extracted response text is None after generation.")

        return parse_llm_response(response_text)

    except Exception as e:
        # Catch-all for other potential API errors during generate_content
        logging.error(f"Error calling Gemini API or parsing response: {e}", exc_info=True)
        # Re-raise specific errors if they are already the correct type
        if isinstance(e, (LLMGenerationError, JSONParsingError)):
            raise e
        # Wrap other exceptions
        raise LLMGenerationError(f"An unexpected error occurred during LLM interaction: {e}") 