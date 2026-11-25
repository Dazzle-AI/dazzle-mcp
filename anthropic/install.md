# Install Dazzle in Claude Code

**Two commands:**

```
/plugin marketplace add dazzle-ai/dazzle-mcp
/plugin install dazzle-photo-intelligence@dazzle
```

Claude Code connects to Dazzle's hosted MCP server and runs a browser sign-in on first use.

## Alternative — add the MCP server directly (no plugin)

```
claude mcp add --transport http dazzle https://api.dazzle.ai/apps/claude-code
```

Then run `/mcp` to complete the OAuth sign-in.

## Claude.ai / Claude Desktop (Connectors)

Settings → Connectors → **Add custom connector** → URL `https://api.dazzle.ai/apps/claude-ai` → sign in.
