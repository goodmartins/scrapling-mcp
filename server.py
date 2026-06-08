#!/usr/bin/env python3
"""MCP server for Scrapling web scraping framework — HTTP/SSE transport."""

import asyncio
import json
import os
from typing import Any

from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import Tool, TextContent, ToolResult
import mcp.types as types
from pydantic import BaseModel, Field
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route
import uvicorn

try:
    from scrapling.fetchers import Fetcher
except ImportError:
    raise ImportError("Scrapling not installed. Run: pip install scrapling[fetchers]")


CRAWL_JOBS: dict = {}
JOB_COUNTER = 0


class ScraplingError(Exception):
    pass


class ScrapePage(BaseModel):
    url: str
    status: str
    content: str = Field(default="")
    html: str = Field(default="")
    error: str = Field(default="")


async def scrape_single_url(
    url: str,
    use_stealth: bool = False,
    include_html: bool = False,
    timeout: int = 30,
) -> ScrapePage:
    try:
        if use_stealth:
            page = await asyncio.to_thread(Fetcher.get, url, stealth=True)
        else:
            page = await asyncio.to_thread(Fetcher.get, url)

        text_content = page.text_content() if hasattr(page, "text_content") else str(page)
        html_content = page.html if include_html and hasattr(page, "html") else ""

        return ScrapePage(
            url=url,
            status="success",
            content=text_content[:5000],
            html=html_content[:10000] if html_content else "",
        )
    except Exception as e:
        return ScrapePage(url=url, status="error", error=str(e))


async def scrape_with_selector(
    url: str,
    selector: str,
    selector_type: str = "css",
    use_stealth: bool = False,
) -> dict[str, Any]:
    try:
        page = await asyncio.to_thread(Fetcher.get, url, stealth=use_stealth)

        if selector_type == "xpath":
            results = page.xpath(selector).getall() if hasattr(page, "xpath") else []
        else:
            results = page.css(selector).getall() if hasattr(page, "css") else []

        return {
            "url": url,
            "selector": selector,
            "selector_type": selector_type,
            "matches": len(results),
            "results": results[:20],
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
                        "url": {"type": "string", "description": "URL to scrape"},
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
                        "url": {"type": "string", "description": "URL to scrape"},
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
                inputSchema={"type": "object", "properties": {}},
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> ToolResult:
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
                    result = await scrape_single_url(url=url, use_stealth=use_stealth)
                    results.append(result.model_dump())
                    await asyncio.sleep(1)

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
                                {"status": "healthy", "service": "scrapling-mcp", "version": "0.2.0"},
                                indent=2,
                            ),
                        )
                    ]
                )

            else:
                return ToolResult(
                    content=[TextContent(type="text", text=f"Unknown tool: {name}")],
                    isError=True,
                )

        except Exception as e:
            return ToolResult(
                content=[TextContent(type="text", text=f"Error: {str(e)}")],
                isError=True,
            )

    return server


def create_app() -> Starlette:
    mcp_server = create_mcp_server()
    sse = SseServerTransport("/messages/")

    async def handle_sse(request: Request):
        async with sse.connect_sse(
            request.scope, request.receive, request._send
        ) as streams:
            await mcp_server.run(
                streams[0], streams[1], mcp_server.create_initialization_options()
            )

    async def health(request: Request):
        return JSONResponse({"status": "ok", "service": "scrapling-mcp", "version": "0.2.0"})

    return Starlette(
        routes=[
            Route("/health", endpoint=health),
            Route("/sse", endpoint=handle_sse),
            Mount("/messages/", app=sse.handle_post_message),
        ]
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app = create_app()
    uvicorn.run(app, host="0.0.0.0", port=port)
