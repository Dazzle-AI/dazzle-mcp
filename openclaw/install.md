# Install Dazzle in OpenClaw

OpenClaw installs Dazzle as a skill from ClawHub (the skill bridges to Dazzle's hosted MCP
server via a local stdio proxy with transparent OAuth).

```
clawhub install @Dazzle/dazzle-photo-intelligence
```

Then follow the one-time setup in the skill's `SKILL.md` (registers the bridge and signs you
in on first use). Source: `./dazzle-photo-intelligence/`.

## Native remote MCP (OpenClaw ≥ remote-MCP support)

If you prefer the hosted server directly instead of the stdio bridge:

```
openclaw mcp add dazzle --url https://api.dazzle.ai/mcp --transport streamable-http --auth oauth
```
