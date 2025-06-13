# Contract Parser

A Python-based tool for extracting structured information from contract documents using Google's Generative AI (Gemini). This tool can process both PDF and Markdown format contracts, extracting key information into a standardized JSON structure and CSV format.

## Overview

The Contract Parser analyzes legal contracts to automatically extract important details such as:
- Partner/Subscriber information
- Contract dates and terms
- User limits and eligibility
- Pricing details
- Data handling policies
- Trial period information
- Reconciliation terms
- And more...

## Project Structure

```
contract_parser/
├── utils.py              # Core processing functions and utilities
├── main.py              # Command-line interface for contract processing
├── contract_processor.ipynb  # Jupyter notebook for interactive processing
├── requirements.txt     # Project dependencies
└── .env                # Environment variables (API keys)
```

## Components

### utils.py
The core library containing all processing logic:
- Custom exception classes for error handling
- File reading functions for both PDF and text files
- LLM prompt construction
- Response parsing and JSON extraction
- Contract data processing orchestration

Key functions:
- `read_pdf(file_input)`: Reads and extracts text from PDF files
- `read_text_file(filepath)`: Reads text-based files (e.g., Markdown)
- `build_llm_prompt(contract_text)`: Constructs the LLM prompt with extraction instructions
- `parse_llm_response(response_text)`: Processes LLM output into structured data
- `get_contract_data(contract_text, api_key)`: Orchestrates the entire extraction process

### main.py
Command-line interface for batch processing:
- Reads contract files (PDF or Markdown)
- Processes them using the utils.py functions
- Outputs results in both JSON and CSV formats
- Saves results to files:
  - `contract_output.json`: Full JSON structure
  - `contract_output.csv`: Two-column format (Field, Value)

### contract_processor.ipynb
Jupyter notebook for interactive contract processing:
- Step-by-step execution of the extraction process
- Detailed visibility into intermediate results
- Useful for development and debugging

## Setup and Installation

1. Clone the repository:
```bash
git clone [repository-url]
cd contract_parser
```

2. Create and activate a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up your environment:
Create a `.env` file in the project root with your Google API key:
```
GOOGLE_API_KEY=your_api_key_here
```

## Usage

### Command Line Interface
Process a contract using the command-line interface:
```bash
python main.py
```
This will:
1. Read the contract file (default: "Lore SaaS Agreement and Order Form April 2025.md")
2. Process it using the Gemini API
3. Output the extracted data to:
   - Console (both JSON and CSV formats)
   - `contract_output.json`
   - `contract_output.csv`

### Jupyter Notebook
For interactive processing and development:
1. Start Jupyter:
```bash
jupyter notebook
```
2. Open `contract_processor.ipynb`
3. Follow the step-by-step cells to process your contract

## Output Formats

### JSON Structure
The tool extracts information into a structured JSON format with fields including:
- Partner Name
- Effective date
- Term length
- Termination date
- Active Lore User Pricing/month
- Eligible users
- Community Access
- Data deletion policy
- Trial period details
- And more...

### CSV Format
The same information is also provided in a two-column CSV format:
```csv
Field Name, Value
Partner Name, Example Corp
Effective date, 01/01/2024
...
```

## Dependencies
- `google-generativeai`: Google's Generative AI API
- `PyPDF2`: PDF file processing
- `python-dotenv`: Environment variable management
- `streamlit`: (Optional) For web interface
- `toml`: Configuration file handling

## Error Handling
The application includes robust error handling for:
- File reading issues
- API configuration problems
- LLM generation errors
- JSON parsing failures
- File writing errors

Each error type has its own custom exception class and appropriate logging.

## Development Notes

### Model Configuration
The application uses the Gemini 2.5 Pro Preview model (`models/gemini-2.5-pro-preview-03-25`). This model was chosen for its higher quota limits and better performance with contract analysis.

### Adding New Fields
To extract additional information:
1. Update the JSON structure in `build_llm_prompt()` in `utils.py`
2. Add appropriate field descriptions and value types
3. Test with sample contracts to ensure accurate extraction

## Troubleshooting

### Common Issues
1. **API Key Issues**: Ensure your Google API key is correctly set in the `.env` file
2. **Quota Limits**: If you hit API limits, wait a few minutes before retrying
3. **File Format Issues**: Ensure your contract files are properly formatted PDF or Markdown

### Debug Mode
For more detailed logging, adjust the logging level in your scripts:
```python
logging.basicConfig(level=logging.DEBUG)
```

## License
[Your License Information Here]

## Contributing
[Your Contribution Guidelines Here] 