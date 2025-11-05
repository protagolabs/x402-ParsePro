#!/usr/bin/env python3
"""
MCP Server using fastmcp framework
"""
from fastmcp import FastMCP
from x402.clients.httpx import x402HttpxClient
from x402.clients.base import decode_x_payment_response, x402Client
from eth_account import Account
from httpx._config import Timeout
import logging
import os

logger = logging.getLogger(__name__)

# Create the MCP application
app = FastMCP()

httpx_default_timeout = os.getenv("HTTPX_DEFAULT_TIMEOUT", "60")
base_url = "https://x402.api.netmind.ai"
endpoint = "/inference-api/agent/v1/parse-pdf"


@app.tool(name="parse_pdf", description="Parse PDF document to json or markdown")
async def parse_pdf(
    private_key: str,
    url: str,
    format: str,
    vlm: bool,
    custom_network_filter: str = None,
) -> dict:
    """Call x402 service

    Args:
        private_key (str): User's private key to sign payments
        url (str): URL of the PDF document to parse
        format (str): Desired output format, "json" or "markdown"
        vlm (bool): Whether to use VLM model
        custom_network_filter (str, optional): Custom network filter for payment requirements. Defaults to None.

    Returns:
        dict: Response from the x402 service
    """
    account = Account.from_key(private_key)
    logger.info(f"Initialized account: {account.address}")
    # check pdf_url
    if not url.startswith("http"):
        raise ValueError("PDF URL must be a valid URL starting with http or https")

    if format not in ["json", "markdown"]:
        raise ValueError("Format must be either 'json' or 'markdown'")
    
    def custom_payment_selector(
        accepts, network_filter=None, scheme_filter=None, max_value=None
    ):
        """Custom payment selector that filters by network."""

        # NOTE: In a real application, you'd want to dynamically choose the most
        # appropriate payment requirement based on user preferences, available funds,
        # network conditions, or other business logic rather than hardcoding a network.

        if custom_network_filter:
            network_filter = custom_network_filter

        return x402Client.default_payment_requirements_selector(
            accepts,
            network_filter=network_filter,
            scheme_filter=scheme_filter,
            max_value=max_value,
        )

    async with x402HttpxClient(
        account=account,
        base_url=base_url,
        payment_requirements_selector=custom_payment_selector,
        timeout=Timeout(int(httpx_default_timeout)),
    ) as client:
        # Make request - payment handling is automatic
        try:

            response = await client.post(
                endpoint, json={"url": url, "format": format, "vlm": vlm}
            )

            # Read the response content
            content = await response.aread()
            logger.debug(f"Response: {content.decode()}")

            # Check for payment response header
            payment_response = None
            if "X-Payment-Response" in response.headers:
                payment_response = decode_x_payment_response(
                    response.headers["X-Payment-Response"]
                )
                logger.info(
                    f"Payment response transaction hash: {payment_response['transaction']}"
                )
            else:
                logger.warning("No payment response header found")

            return {
                "result": content.decode(),
                "hash": payment_response["transaction"] if payment_response else None,
            }

        except Exception as e:
            logger.exception(e)

    return {"error": "Request failed"}


def main():
    """Main function to run the MCP server"""
    logger.info("Starting MCP Server...")
    # Run with stdio transport (default)
    app.run(transport="stdio")


if __name__ == "__main__":
    main()
