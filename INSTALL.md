# Installation and Usage

## Prerequisites

- Python 3.7 or higher
- pip

## Installation

1. Clone or download this repository
2. Navigate to the project directory:
   ```bash
   cd mcp-server
   ```

3. Install the dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Install the package in development mode:
   ```bash
   pip install -e .
   ```

## Running the Server

To run the MCP server:

```bash
python app.py
```

Or if installed in development mode:

```bash
mcp-server
```

## Testing

The server can be tested by importing it in Python:

```bash
python -c "import app; from app import app; print('Server imported successfully'); print(f'Tools: {len(app._tool_manager.list_tools())}')"
```

This should output:
```
Server imported successfully
Tools: 2
```

## Project Structure

- `app.py` - Main server application with tools
- `requirements.txt` - Python dependencies
- `setup.py` - Package setup
- `README.md` - Project documentation
- `test_server.py` - Test script
