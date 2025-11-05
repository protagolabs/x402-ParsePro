# MCP Server

A simple MCP server implementation using the fastmcp framework that parses PDF documents to JSON or Markdown format.

## Features

- Parse PDF document to json or markdown with x402 payment handling

## Installation

```bash
pip install -r requirements.txt
```

## Running the Server

```bash
python x402_parsepro/app.py
```

Or install and run:

```bash
pip install -e .
x402-parsepro
```

## Using Justfile

This project includes a [Justfile](https://github.com/casey/just) for easy automation:

```bash
just install    # Install dependencies
just develop    # Install in development mode
just run        # Run the server
just help       # Show available commands
```

## Tools

- `parse_pdf` - Parse PDF document to json or markdown with x402 payment handling.

## License

MIT
