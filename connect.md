# Connect Dazzle to any MCP client

Dazzle is a hosted **remote MCP server** (Streamable HTTP, OAuth 2.1 + PKCE + Dynamic Client
Registration). Any spec-compliant client connects with just a URL — it discovers Dazzle's
OAuth endpoints, registers itself, and runs the browser sign-in automatically. There is no
client ID or secret to copy.

## Endpoint

```
https://api.dazzle.ai/mcp
```

## Pattern A — native remote MCP

If your client supports remote (HTTP) MCP servers, add one and paste the URL above. The
client opens a browser, you approve, and the `dazzle` tool loads.

## Pattern B — `mcp-remote` bridge

If your client only accepts local (stdio) servers, or takes a remote URL but doesn't run the
OAuth browser flow, bridge to Dazzle with the `mcp-remote` stdio proxy. It handles OAuth in
the browser on first use and caches credentials in `~/.mcp-auth`:

```json
{
  "mcpServers": {
    "dazzle": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "https://api.dazzle.ai/mcp"]
    }
  }
}
```
