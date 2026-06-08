# Scrapling MCP Server

MCP (Model Context Protocol) server that exposes Scrapling web scraping framework as tools for Claude Code and other MCP clients.

## Setup Local

### Prerequisites
- Python 3.10+
- pip

### Install

```bash
cd scrapling-mcp
pip install -r requirements.txt
pip install "scrapling[fetchers]"
scrapling install
```

### Run Locally

```bash
python server.py
```

## Tools Available

### 1. `scrape_url`
Fetch and parse a single URL.

**Parameters:**
- `url` (string, required): URL to scrape
- `use_stealth` (boolean): Use stealth mode to bypass anti-bot (default: false)
- `include_html` (boolean): Include raw HTML in response (default: false)
- `timeout` (integer): Request timeout in seconds (default: 30)

**Returns:** URL content, status, and optional HTML

### 2. `scrape_with_selector`
Scrape URL and extract elements using CSS or XPath selector.

**Parameters:**
- `url` (string, required): URL to scrape
- `selector` (string, required): CSS selector or XPath expression
- `selector_type` (string): "css" or "xpath" (default: "css")
- `use_stealth` (boolean): Use stealth mode (default: false)

**Returns:** List of matching elements

### 3. `batch_scrape`
Scrape multiple URLs sequentially with rate limiting.

**Parameters:**
- `urls` (array, required): List of URLs to scrape
- `use_stealth` (boolean): Use stealth mode for all requests (default: false)

**Returns:** Results for all URLs

### 4. `health_check`
Check server health and availability.

**Returns:** Service status and version

## Deploy to Render (Free)

### Steps

1. **Create GitHub repo** (if not already)
   ```bash
   cd scrapling-mcp
   git init
   git add .
   git commit -m "Initial scrapling-mcp"
   git push origin main
   ```

2. **Create Render service**
   - Go to https://render.com
   - Sign up/login
   - Click "New +" → "Web Service"
   - Connect GitHub repo
   - Select "scrapling-mcp" directory
   - Name: `scrapling-mcp`
   - Environment: Docker
   - Plan: Free
   - Click "Create Web Service"

3. **Wait for deployment** (~5 minutes)

4. **Get service URL**
   - From Render dashboard: `https://scrapling-mcp-xxxx.onrender.com`

## Configure Claude Code

1. **Get server URL from Render**

2. **Update `.mcp.json`**:
   ```json
   {
     "mcpServers": {
       "scrapling": {
         "type": "url",
         "url": "https://scrapling-mcp-xxxx.onrender.com"
       }
     }
   }
   ```

3. **Restart Claude Code**

4. **Test:**
   - Use `/mcp-inspect` to see available tools
   - Ask Claude to scrape a URL

## Environment Variables (Optional)

- `PYTHONUNBUFFERED=true` (default on Render)

## Notes

- Free Render tier goes to sleep after 15 minutes of inactivity
- First request after sleep takes 30-60 seconds
- Stealth mode requires additional resources (more CPU/memory)
- Batch scraping includes 1-second delays between requests

## Troubleshooting

**Server won't start:**
```bash
pip install --upgrade scrapling
scrapling install
```

**Import errors:**
```bash
pip install -r requirements.txt --upgrade
```

**Timeout on Render:**
- May be caused by free tier resource limits
- Try increasing timeout parameter
- Use `use_stealth=false` first
