# Dazzle MCP

Dazzle's hosted MCP server — ask any question about your own life and get an answer plus photos.

- **Endpoint:** `https://api.dazzle.ai/mcp` (Streamable HTTP, OAuth 2.0 + PKCE + DCR). Curated clients use a per-client path `https://api.dazzle.ai/apps/<client_id>` so capabilities match the client.
- **Tools:** depend on the client.
  - Text-only clients (Claude Code, Codex, generic `/mcp`): `dazzle`, which answers and lists photos inline.
  - Clients that render MCP Apps (Claude.ai, ChatGPT): `dazzle_ask` for a text answer and `dazzle_photos` for a photo gallery.
- **Registry:** `io.github.dazzle-ai/dazzle-photo-intelligence`

Tool, endpoint, authentication, and error reference: [`TOOLS.md`](./TOOLS.md).

## Connect any client

Dazzle is a standard remote MCP server — any compliant client connects with just the URL.
See [`connect.md`](./connect.md).

## First-class integrations

These ship as installable artifacts rather than a paste-the-URL step:

| Target | Install |
|--------|---------|
| **Claude Code** | `/plugin marketplace add dazzle-ai/dazzle-mcp` then `/plugin install dazzle-photo-intelligence@dazzle` — [details](./anthropic/install.md) |
| **ChatGPT** | Plugin directory listing, "Dazzle Photo Intelligence" — [package](./openai/README.md) |
| **OpenClaw** | `clawhub install @Dazzle/dazzle-photo-intelligence` — [details](./openclaw/install.md) |
