import streamlit as st
import google.generativeai as genai
import PyPDF2
import os
import json
from datetime import datetime
import re
import io # Import io for handling uploaded file bytes

# --- Configuration ---
# PDF_PATH is removed, we use file uploader now
MODEL_NAME = "gemini-2.5-pro-exp-03-25" # Using latest available model, adjust if needed
# It's best practice to set the API key as an environment variable
# For local testing, you might uncomment the line below and paste your key
# os.environ['GEMINI_API_KEY'] = "YOUR_API_KEY_HERE" 
# --- WARNING: Do not commit your API key directly into the code ---

# --- Helper Functions ---

def get_api_key():
    """Retrieves the Gemini API key from Streamlit secrets."""
    # Use session state to cache the API key check result
    if 'api_key' not in st.session_state:
        try:
            api_key = st.secrets["GEMINI_API_KEY"]
            if not api_key: # Check if the key exists but is empty
                 st.error("GEMINI_API_KEY found in secrets but it is empty.")
                 st.stop()
            st.session_state.api_key = api_key
        except KeyError:
            st.error("GEMINI_API_KEY not found in Streamlit secrets (.streamlit/secrets.toml).")
            st.info("Please ensure the file exists and the key is defined, e.g., GEMINI_API_KEY = \"your_key_here\"")
            st.stop()
        except Exception as e:
             st.error(f"An error occurred reading secrets: {e}")
             st.stop()

    return st.session_state.api_key

def read_pdf(file_input):
    """Reads text content from a PDF file (path or uploaded file object)."""
    text = ""
    try:
        # Check if input is a file path (string) or an uploaded file object
        if isinstance(file_input, str): # File path
            if not os.path.exists(file_input):
                 st.error(f"Error: PDF file not found at '{file_input}'.")
                 return None
            file_stream = open(file_input, 'rb')
        elif hasattr(file_input, 'read'): # Uploaded file object (has read method)
            # Use io.BytesIO to wrap the bytes from the uploaded file
            # Reset position just in case it was read before
            file_input.seek(0)
            file_stream = io.BytesIO(file_input.read())
        else:
            st.error("Invalid input type for read_pdf. Expected file path or uploaded file object.")
            return None

        reader = PyPDF2.PdfReader(file_stream)
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\\n" # Add newline between pages

        # Close the stream if it was opened from a file path
        if isinstance(file_input, str):
            file_stream.close()

        return text

    except FileNotFoundError: # Should be caught by os.path.exists for path case
        st.error(f"Error: PDF file not found at '{file_input}'.")
        return None
    except PyPDF2.errors.PdfReadError:
        st.error("Error reading PDF: Invalid PDF file. It might be corrupted or password-protected.")
        return None
    except Exception as e:
        st.error(f"Error reading PDF: {e}")
        return None

def build_llm_prompt(contract_text):
    """Builds the LLM prompt with contract text and JSON instructions."""
    # Ensure contract_text is properly escaped for JSON within the prompt if necessary
    # For simple text insertion, direct formatting is usually fine.
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
  "Reconciliation start date": {{
    "description": "The start date for reconciling Lore's pricing model.",
    "type": "MM/DD/YYYY",
    "value": "First, look for an explicitly stated Reconciliation Start Date and convert it to MM/DD/YYYY format. If not found, perform the following calculation: 1. Find the Effective Date. 2. Add 12 months to the Effective Date (end of Benchmark Period). 3. Add 4 months to the result from step 2. 4. Format this final calculated date as MM/DD/YYYY. If the Effective Date cannot be found for calculation, return null."
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
    "description": "Whether a data deletion policy is specifically stipulated",
    "type": "Boolean",
    "value": "Extract True/False, null if not specified" 
  }},
  "Timeframe (hours)": {{
    "description": "Timeframe in hours for Lore to delete personal data per policy",
    "type": "Integer",
    "value": "Extract integer, null if no policy or not specified"
  }},
  "Data covered by HIPAA": {{
    "description": "Contingent upon whether there is a business associate agreement",
    "type": "Boolean",
    "value": "Determine True/False based on BAA presence, null if unclear"
  }},
  "Business Associate Agreement": {{
    "description": "Required by health plan/self-funded employer if covered entity under HIPAA",
    "type": "Boolean",
    "value": "Extract True/False, null if not mentioned"
  }},
  "Data Sharing Agreement": {{
    "description": "An agreement to share HIPAA data",
    "type": "Boolean",
    "value": "Extract True/False, null if not mentioned"
  }},
  "Reconciliation Method": {{
    "description": "Method for reconciling payments (monthly_Fee or reconciliation_statement)",
    "type": "String",
    "accepted_values": ["monthly_Fee", "reconciliation_statement"],
    "value": "Extract value or null"
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
    """Parses the LLM response to extract the JSON object."""
    # Remove potential markdown fences and surrounding whitespace
    match = re.search(r"```json\s*({.*?})\s*```", response_text, re.DOTALL | re.IGNORECASE)
    if match:
        json_str = match.group(1)
    else:
        # If no markdown fences, assume the response is the JSON object itself
        # Find the first '{' and the last '}'
        start = response_text.find('{')
        end = response_text.rfind('}')
        if start != -1 and end != -1 and end > start:
             json_str = response_text[start:end+1]
        else:
            st.error("Could not find valid JSON in the LLM response.")
            st.code(response_text) # Show the raw response for debugging
            return None

    try:
        # Load the JSON string into a Python dictionary
        parsed_json = json.loads(json_str)
        # Extract the 'value' from each field
        extracted_data = {k: v.get('value', None) for k, v in parsed_json.items()}
        return extracted_data
    except json.JSONDecodeError as e:
        st.error(f"Error decoding JSON from LLM response: {e}")
        st.text("Raw JSON string received:")
        st.code(json_str) # Show the string that failed parsing
        return None
    except Exception as e:
        st.error(f"An unexpected error occurred during JSON parsing: {e}")
        st.code(response_text)
        return None


@st.cache_data(show_spinner="Parsing contract with AI...") # Cache the result based on text content
def get_contract_data(contract_text, api_key):
    """Sends prompt to Gemini and parses the response."""
    # Ensure API key is configured (it should be from get_api_key())
    genai.configure(api_key=api_key)
    # Use a try-except block for model initialization as well
    try:
        model = genai.GenerativeModel(MODEL_NAME)
    except Exception as e:
        st.error(f"Error initializing Gemini model ({MODEL_NAME}): {e}")
        st.error("Please ensure the model name is correct and you have access.")
        return None

    prompt = build_llm_prompt(contract_text)
    try:
        response = model.generate_content(prompt)
        # Accessing the text part correctly based on the library's structure
        if hasattr(response, 'text'):
             response_text = response.text
        # Add handling for potential BlockedPromptException or other safety issues
        elif hasattr(response, 'prompt_feedback') and response.prompt_feedback.block_reason:
             st.error(f"Content generation blocked. Reason: {response.prompt_feedback.block_reason}")
             st.write(response.prompt_feedback)
             return None
        elif isinstance(response, str):
             response_text = response
        else:
            # Handle potential variations in response structure if necessary
            st.warning(f"Unexpected response structure from Gemini: {type(response)}")
            st.write(response) # Uncomment to debug response structure
            st.error("Could not extract text from Gemini response.")
            return None

        return parse_llm_response(response_text)
    except Exception as e:
        st.error(f"Error calling Gemini API: {e}")
        # Consider logging the full exception details here if needed
        return None

# --- Streamlit App UI ---

st.set_page_config(layout="wide")
st.title("📄 Contract Parser")

# Initialize session state variables if they don't exist
if 'uploaded_file' not in st.session_state:
    st.session_state.uploaded_file = None
if 'parsed_data' not in st.session_state:
    st.session_state.parsed_data = None
if 'edited_data' not in st.session_state:
    st.session_state.edited_data = None

# --- Load API Key ---
# Do this early, but it won't halt execution here anymore due to session state caching
api_key = get_api_key()


# --- File Uploader ---
uploaded_file = st.file_uploader(
    "Choose a PDF contract file",
    type="pdf",
    key="file_uploader", # Use a key to manage state
    on_change=lambda: st.session_state.update(parsed_data=None, edited_data=None) # Reset parse results on new file upload
)

# --- Process Uploaded File ---
if uploaded_file is not None:
    # Store the uploaded file object in session state
    st.session_state.uploaded_file = uploaded_file

    # Display info about the uploaded file
    st.markdown(f"**Uploaded:** `{uploaded_file.name}`")
    st.button("Parse Contract", key="parse_button")

# --- Parsing Logic (Triggered by Button) ---
# Check if the button was clicked in this run *and* we have a file
if st.session_state.get("parse_button") and st.session_state.uploaded_file:
    # Read the PDF content from the uploaded file in session state
    contract_text = read_pdf(st.session_state.uploaded_file)

    if contract_text:
        # Get Parsed Data from LLM (will use cache if text is identical)
        # Pass API key explicitly as it might not be in scope otherwise depending on execution flow
        parsed_data = get_contract_data(contract_text, api_key)
        st.session_state.parsed_data = parsed_data
        # Initialize edited_data when new data is parsed
        if parsed_data:
             st.session_state.edited_data = parsed_data.copy()
        else:
             st.session_state.edited_data = None # Reset if parsing failed
    else:
        st.error("Could not extract text from the uploaded PDF.")
        st.session_state.parsed_data = None
        st.session_state.edited_data = None

# --- Display Editable Form ---
# Display only if parsing has been successful (data exists in session state)
if st.session_state.edited_data:
    parsed_data = st.session_state.parsed_data # Retrieve for potential reset
    edited_data = st.session_state.edited_data # Work with the editable version

    st.header("Parsed Contract Details (Editable)")
    st.info("Review and edit the parsed details below.")

    # Reset button - Copies the initially parsed data back to the editable state
    if st.button("Reset to Parsed Values"):
        if parsed_data:
            st.session_state.edited_data = parsed_data.copy()
            edited_data = st.session_state.edited_data # Update local variable
            st.rerun() # Rerun to reflect the reset values in widgets
        else:
            st.warning("No parsed data available to reset to.")


    cols = st.columns(2) # Create two columns for better layout

    field_definitions = { # Define types and options for widgets
        "Partner Name": {"type": "text"},
        "Effective date": {"type": "date"},
        "Term length (days)": {"type": "number", "min": 0},
        "Termination date": {"type": "date"},
        "Reconciliation start date": {"type": "date"},
        "Active Lore User Pricing/month": {"type": "number", "min": 0, "format": "%d"}, # Removed '$' from format
        "Eligible users": {"type": "number", "min": 0, "step": 1},
        "Lore users": {"type": "number", "min": 0, "step": 1},
        "Total Monthly Active Users": {"type": "number", "min": 0, "step": 1},
        "Community Access": {"type": "boolean"},
        "Data deletion policy (lorebot)": {"type": "boolean"},
        "Timeframe (hours)": {"type": "number", "min": 0, "step": 1},
        "Data covered by HIPAA": {"type": "boolean"},
        "Business Associate Agreement": {"type": "boolean"},
        "Data Sharing Agreement": {"type": "boolean"},
        "Reconciliation Method": {"type": "select", "options": ["monthly_Fee", "reconciliation_statement", None]},
        "Dependents allowed": {"type": "boolean"},
        "Eligibility": {"type": "select", "options": ["all", "only_insured", None]}
    }

    # Determine column for each item
    items_per_col = (len(edited_data) + 1) // 2
    current_col_index = 0

    for i, (key, value) in enumerate(edited_data.items()):
        col = cols[current_col_index]
        field_def = field_definitions.get(key, {"type": "text"}) # Default to text input

        # Use a unique key for each widget based on the field name
        widget_key = f"widget_{key.replace(' ', '_').lower()}"

        with col:
            if field_def["type"] == "text":
                 edited_data[key] = st.text_input(key, value=value if value is not None else "", key=widget_key)
            elif field_def["type"] == "number":
                 # Handle potential '$' prefix in value if LLM includes it despite instructions
                 current_value_num = value # Keep track of original for int conversion attempt
                 if isinstance(value, str) and value.startswith('$'):
                     try:
                         current_value_num = int(value[1:])
                     except (ValueError, TypeError):
                         current_value_num = None # Mark as None if conversion fails
                 
                 # Attempt conversion to int, handle None/errors gracefully
                 try:
                     final_value = int(current_value_num) if current_value_num is not None else field_def.get("min", 0)
                 except (ValueError, TypeError):
                      st.warning(f"Could not convert value for '{key}' to integer: {value}. Using default.")
                      final_value = field_def.get("min", 0)

                 edited_data[key] = st.number_input(
                    key,
                    value=final_value,
                    min_value=field_def.get("min"),
                    step=field_def.get("step", 1),
                    format=field_def.get("format", "%d"),
                    key=widget_key
                 )
            elif field_def["type"] == "date":
                current_value_date = None
                if value:
                    try:
                        # Attempt to parse MM/DD/YYYY (updated from DD/MM/YYYY)
                        current_value_date = datetime.strptime(str(value), "%m/%d/%Y").date()
                    except (ValueError, TypeError):
                        try:
                             # Fallback for other common formats if needed (e.g., YYYY-MM-DD)
                             # Handle potential timestamp like 'YYYY-MM-DD HH:MM:SS'
                             date_str = str(value).split()[0]
                             current_value_date = datetime.fromisoformat(date_str).date()
                        except Exception: # Catch broader exceptions during fallback
                             st.warning(f"Could not parse date for '{key}': {value}. Please select manually.")
                             current_value_date = None # Set to None if parsing fails

                # Allow None as a valid value for date input
                # Update widget display format to MM/DD/YYYY
                edited_data[key] = st.date_input(key, value=current_value_date, format="MM/DD/YYYY", key=widget_key)

                # Convert back to MM/DD/YYYY string *only if a date is selected*
                if edited_data[key]:
                    edited_data[key] = edited_data[key].strftime("%m/%d/%Y")
                else:
                     edited_data[key] = None # Ensure it stays None if cleared

            elif field_def["type"] == "boolean":
                # Handle potential string "True"/"False" or actual boolean
                bool_value = None
                if isinstance(value, bool):
                     bool_value = value
                elif isinstance(value, str):
                     val_lower = value.lower()
                     if val_lower == 'true':
                         bool_value = True
                     elif val_lower == 'false':
                         bool_value = False
                     # Keep bool_value as None if string is something else or empty

                options = [True, False, None] # Allow 'None' option explicitly
                try:
                    current_index = options.index(bool_value)
                except ValueError:
                    current_index = 2 # Default to None index if value is unexpected or None

                selected_option = st.selectbox(
                    key,
                    options=options,
                    index=current_index,
                    format_func=lambda x: str(x) if x is not None else "Not Specified",
                    key=widget_key
                )
                edited_data[key] = selected_option

            elif field_def["type"] == "select":
                options = field_def.get("options", [])
                # Ensure value from LLM is actually in the allowed options
                current_value_select = value if value in options else None

                try:
                     # Ensure None is handled correctly if value is None or not in options
                     current_index = options.index(current_value_select) if current_value_select is not None else options.index(None) if None in options else 0
                except ValueError:
                      # Fallback if None isn't an option but value was invalid
                     current_index = 0

                selected_option = st.selectbox(
                     key,
                     options=options,
                     index=current_index,
                     format_func=lambda x: str(x) if x is not None else "Not Specified",
                     key=widget_key
                )
                edited_data[key] = selected_option


        # Switch column after half the items
        if i == items_per_col - 1:
            current_col_index = 1

    st.divider()
    st.subheader("Current Edited Data (JSON)")
    # Display the session state which reflects live edits
    st.json(st.session_state.edited_data)

# Add a message if parsing failed after button click
elif st.session_state.get("parse_button") and not st.session_state.edited_data:
     st.error("Failed to parse contract data. Please check the contract content or API key/model access.")

# Add initial instruction
if not st.session_state.uploaded_file:
    st.info("Upload a PDF contract file above to begin.")

st.caption("Ensure the GEMINI_API_KEY environment variable is set (e.g., in a .env file).") 