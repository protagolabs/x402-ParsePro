#!/usr/bin/env python3
"""
MCP Server using fastmcp framework
"""
from fastmcp import FastMCP
from x402.clients.httpx import x402HttpxClient
from x402.clients.base import (
    decode_x_payment_response,
    x402Client,
    PaymentSelectorCallable,
    PaymentError,
    MissingRequestConfigError,
)
from pydantic.alias_generators import to_camel
from eth_account import Account
from httpx._config import Timeout
import logging
import os
from typing import Optional, Dict, List, Any
from httpx import Request, Response, AsyncClient
from pydantic import BaseModel, ConfigDict, field_validator


logger = logging.getLogger(__name__)

# Create the MCP application
app = FastMCP()

httpx_default_timeout = os.getenv("HTTPX_DEFAULT_TIMEOUT", "60")
base_url = "https://x402.api.netmind.ai"
endpoint = "/inference-api/agent/v1/parse-pdf"


class PaymentRequirements(BaseModel):
    scheme: str
    network: str
    max_amount_required: str
    resource: str
    description: str
    mime_type: str
    output_schema: Optional[Any] = None
    pay_to: str
    max_timeout_seconds: int
    asset: str
    extra: Optional[dict[str, Any]] = None

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )

    @field_validator("max_amount_required")
    def validate_max_amount_required(cls, v):
        try:
            0 if len(v) == 0 else int(v)
        except ValueError:
            raise ValueError(
                "max_amount_required must be an integer encoded as a string"
            )
        return v

    @field_validator("network")
    def validate_network(cls, v):
        return "base" if v == "eip155:8453" else v

class x402PaymentRequiredResponse(BaseModel):
    x402_version: int
    accepts: list[PaymentRequirements]
    error: str

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )

class HttpxHooks:
    def __init__(self, client: x402Client):
        self.client = client
        self._is_retry = False

    async def on_request(self, request: Request):
        """Handle request before it is sent."""
        pass

    async def on_response(self, response: Response) -> Response:
        """Handle response after it is received."""

        # If this is not a 402, just return the response
        if response.status_code != 402:
            return response

        # If this is a retry response, just return it
        if self._is_retry:
            return response

        try:
            if not response.request:
                raise MissingRequestConfigError("Missing request configuration")

            # Read the response content before parsing
            await response.aread()

            data = response.json()

            payment_response = x402PaymentRequiredResponse(**data)

            # Select payment requirements
            selected_requirements = self.client.select_payment_requirements(
                payment_response.accepts
            )

            # Create payment header
            payment_header = self.client.create_payment_header(
                selected_requirements, payment_response.x402_version
            )

            # Mark as retry and add payment header
            self._is_retry = True
            request = response.request

            request.headers["X-Payment"] = payment_header
            request.headers["Access-Control-Expose-Headers"] = "X-Payment-Response"

            from httpx._config import Timeout

            # Retry the request
            async with AsyncClient(timeout=Timeout(timeout=None)) as client:
                retry_response = await client.send(request)

                # Copy the retry response data to the original response
                response.status_code = retry_response.status_code
                response.headers = retry_response.headers
                response._content = retry_response._content
                return response

        except PaymentError as e:
            self._is_retry = False
            raise e
        except Exception as e:
            self._is_retry = False
            raise PaymentError(f"Failed to handle payment: {str(e)}") from e


def x402_payment_hooks(
    account: Account,
    max_value: Optional[int] = None,
    payment_requirements_selector: Optional[PaymentSelectorCallable] = None,
) -> Dict[str, List]:
    """Create httpx event hooks dictionary for handling 402 Payment Required responses.

    Args:
        account: eth_account.Account instance for signing payments
        max_value: Optional maximum allowed payment amount in base units
        payment_requirements_selector: Optional custom selector for payment requirements.
            Should be a callable that takes (accepts, network_filter, scheme_filter, max_value)
            and returns a PaymentRequirements object.

    Returns:
        Dictionary of event hooks that can be directly assigned to client.event_hooks
    """
    # Create x402Client
    client = x402Client(
        account,
        max_value=max_value,
        payment_requirements_selector=payment_requirements_selector,
    )

    # Create hooks
    hooks = HttpxHooks(client)

    # Return event hooks dictionary
    return {
        "request": [hooks.on_request],
        "response": [hooks.on_response],
    }


class _x402HttpxClient(AsyncClient):
    """AsyncClient with built-in x402 payment handling."""

    def __init__(
        self,
        account: Account,
        max_value: Optional[int] = None,
        payment_requirements_selector: Optional[PaymentSelectorCallable] = None,
        **kwargs,
    ):
        """Initialize an AsyncClient with x402 payment handling.

        Args:
            account: eth_account.Account instance for signing payments
            max_value: Optional maximum allowed payment amount in base units
            payment_requirements_selector: Optional custom selector for payment requirements.
                Should be a callable that takes (accepts, network_filter, scheme_filter, max_value)
                and returns a PaymentRequirements object.
            **kwargs: Additional arguments to pass to AsyncClient
        """
        super().__init__(**kwargs)
        self.event_hooks = x402_payment_hooks(
            account, max_value, payment_requirements_selector
        )


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

    async with _x402HttpxClient(
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
