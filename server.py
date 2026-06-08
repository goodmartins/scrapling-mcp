#!/usr/bin/env python3
"""MCP server for Scrapling web scraping framework."""

import asyncio
import json
from typing import Any
from pathlib import Path
from mcp.server import Server
from mcp.types import Tool, TextContent, ToolResult
import mcp.types as types
from pydantic import BaseModel, Field

try:
    from scrapling.fetchers import Fetcher
    from scrapling.spiders import Spider
except ImportError:
    raise ImportError("Scrapling not installed. Run: pip install scrapling[fetchers]")


# Global state for crawl jobs
CRAWL_JOBS = {}
JOB_COUNTER = 0


class ScraplingError(Exception):
    """Scrapling-specific error."""
    pass


class ScrapePage(BaseModel):
    """Response from scraping a page."""
    url: str
    status: str
    content: str = Field(default="", description="Extracted text content")
    html: str = Field(default="", description="Raw HTML if requested")
    error: str = Field(default="", description="Error message if failed")


async def scrape_single_url(
    url: str,
    use_stealth: bool = False,
    include_html: bool = False,
    timeout: int = 30,
) -> ScrapePage:
    """Scrape a single URL using Scrapling fetcher."""
    try:
        if use_stealth:
            page = await asyncio.to_thread(Fetcher.get, url, stealth=True)
        else:
            page = await asyncio.to_thread(Fetcher.get, url)

        # Extract text content
        text_content = page.text_content() if hasattr(page, 'text_content') else str(page)
        html_content = page.html if include_html and hasattr(page, 'html') else ""

        return ScrapePage(
            url=url,
            status="success",
            content=text_content[:5000],  # Limit output
            html=html_content[:10000] if html_content else "",
        )
    except Exception as e:
        return ScrapePage(
            url=url,
            status="error",
            error=str(e),
        )


async def scrape_with_selector(
    url: str,
    selector: str,
    selector_type: str = "css",
    use_stealth: bool = False,
) -> dict[str, Any]:
    """Scrape URL and extract with CSS or XPath selector."""
    try:
        page = await asyncio.to_thread(
            Fetcher.get, url, stealth=use_stealth
        )

        if selector_type == "xpath":
            results = page.xpath(selector).getall() if hasattr(page, 'xpath') else []
        else:  # css
            results = page.css(selector).getall() if hasattr(page, 'css') else []

        return {
            "url": url,
            "selector": selector,
            "selector_type": selector_type,
            "matches": len(results),
            "results": results[:20],  # Limit to 20 results
            "status": "success",
        }
    except Exception as e:
        return {
            "url": url,
            "selector": selector,
            "selector_type": selector_type,
            "status": "error",
            "error": str(e),
        }


def create_mcp_server() -> Server:
    """Create and configure MCP server."""
    server = Server("scrapling-mcp")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name="scrape_url",
                description="Fetch and parse a single URL using Scrapling",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "URL to scrape",
                        },
                        "use_stealth": {
                            "type": "boolean",
                            "description": "Use stealth mode to bypass anti-bot",
                            "default": False,
                        },
                        "include_html": {
                            "type": "boolean",
                            "description": "Include raw HTML in response",
                            "default": False,
                        },
                        "timeout": {
                            "type": "integer",
                            "description": "Request timeout in seconds",
                            "default": 30,
                        },
                    },
                    "required": ["url"],
                },
            ),
            Tool(
                name="scrape_with_selector",
                description="Scrape URL and extract elements using CSS or XPath selector",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "URL to scrape",
                        },
                        "selector": {
                            "type": "string",
                            "description": "CSS selector or XPath expression",
                        },
                        "selector_type": {
                            "type": "string",
                            "enum": ["css", "xpath"],
                            "description": "Type of selector",
                            "default": "css",
                        },
                        "use_stealth": {
                            "type": "boolean",
                            "description": "Use stealth mode",
                            "default": False,
                        },
                    },
                    "required": ["url", "selector"],
                },
            ),
            Tool(
                name="batch_scrape",
                description="Scrape multiple URLs sequentially",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "urls": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of URLs to scrape",
                        },
                        "use_stealth": {
                            "type": "boolean",
                            "description": "Use stealth mode for all requests",
                            "default": False,
                        },
                    },
                    "required": ["urls"],
                },
            ),
            Tool(
                name="health_check",
                description="Check Scrapling server health and availability",
                inputSchema={
                    "type": "object",
                    "properties": {},
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> ToolResult:
        """Handle tool calls."""
        try:
            if name == "scrape_url":
                result = await scrape_single_url(
                    url=arguments["url"],
                    use_stealth=arguments.get("use_stealth", False),
                    include_html=arguments.get("include_html", False),
                    timeout=arguments.get("timeout", 30),
                )
                return ToolResult(
                    content=[
                        TextContent(
                            type="text",
                            text=json.dumps(result.model_dump(), indent=2, ensure_ascii=False),
                        )
                    ]
                )

            elif name == "scrape_with_selector":
                result = await scrape_with_selector(
                    url=arguments["url"],
                    selector=arguments["selector"],
                    selector_type=arguments.get("selector_type", "css"),
                    use_stealth=arguments.get("use_stealth", False),
                )
                return ToolResult(
                    content=[
                        TextContent(
                            type="text",
                            text=json.dumps(result, indent=2, ensure_ascii=False),
                        )
                    ]
                )

            elif name == "batch_scrape":
                urls = arguments["urls"]
                use_stealth = arguments.get("use_stealth", False)
                results = []

                for url in urls:
                    result = await scrape_single_url(
                        url=url,
                        use_stealth=use_stealth,
                    )
                    results.append(result.model_dump())
                    await asyncio.sleep(1)  # Rate limiting

                return ToolResult(
                    content=[
                        TextContent(
                            type="text",
                            text=json.dumps(
                                {"urls_scraped": len(urls), "results": results},
                                indent=2,
                                ensure_ascii=False,
                            ),
                        )
                    ]
                )

            elif name == "health_check":
                return ToolResult(
                    content=[
                        TextContent(
                            type="text",
                            text=json.dumps(
                                {
                                    "status": "healthy",
                                    "service": "scrapling-mcp",
                                    "version": "0.1.0",
                                },
                                indent=2,
                            ),
                        )
                    ]
                )

            else:
                return ToolResult(
                    content=[
                        TextContent(
                            type="text",
                            text=f"Unknown tool: {name}",
                        )
                    ],
                    isError=True,
                )

        except Exception as e:
            return ToolResult(
                content=[
                    TextContent(
                        type="text",
                        text=f"Error: {str(e)}",
                    )
                ],
                isError=True,
            )

    return server


async def main():
    """Run the MCP server."""
    server = create_mcp_server()
    async with server:
        print("Scrapling MCP server running on stdio")
        await server.wait_for_shutdown()


if __name__ == "__main__":
    asyncio.run(main())
