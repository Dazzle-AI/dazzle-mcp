# Dazzle MCP tool reference

Dazzle answers questions about the signed-in user's own life from the photos they share with
the Dazzle iPhone app: their pets, family and friends, home, trips, hobbies, and tastes. It is
operated by Dazzle AI, Inc.

All tools are **read-only**. They never create, change, share, or delete anything, and they only
read the data of the Dazzle account that signed in.

## Endpoints

Each assistant connects to its own endpoint, so it gets the tools it can display.

| Assistant | MCP endpoint | Tools |
|-----------|--------------|-------|
| ChatGPT | `https://api.dazzle.ai/apps/chatgpt` | `dazzle_ask`, `dazzle_photos` |
| Claude (claude.ai, desktop, mobile) | `https://api.dazzle.ai/apps/claude-ai` | `dazzle_ask`, `dazzle_photos` |
| Meta Muse | `https://api.dazzle.ai/apps/muse` | `dazzle` |
| Claude Code | `https://api.dazzle.ai/apps/claude-code` | `dazzle` |
| Codex | `https://api.dazzle.ai/apps/codex` | `dazzle` |
| Antigravity | `https://api.dazzle.ai/apps/antigravity` | `dazzle` |

Transport is MCP Streamable HTTP: JSON-RPC requests are sent with `POST` and answered with a single
JSON response. Supported methods: `initialize`, `ping`, `tools/list`, `tools/call`,
`resources/list`, `resources/templates/list`, and `resources/read`.

## Authentication

- OAuth 2.1 authorization code flow with PKCE (`S256`). The client is public, so there is no
  client secret.
- Scope: `query`.
- Discovery: `/.well-known/oauth-protected-resource/apps/<client>` (RFC 9728) and
  `/.well-known/oauth-authorization-server/apps/<client>` (RFC 8414). Each endpoint also offers
  dynamic client registration at `/apps/<client>/register`.
- Access tokens last 1 hour and refresh tokens last 30 days.
- Users sign in with their Dazzle account (phone number and verification code) and approve
  access on Dazzle's consent screen.
- Users can disconnect at any time from the assistant's settings or by emailing
  support@dazzle.ai. Disconnecting revokes the assistant's access.

## Tools

### `dazzle`

Answers a question about the user's own life and lists matching photos in the text response.

| | |
|---|---|
| Class | Read |
| Permission | `query` scope |
| Side effects | None |
| Annotations | `readOnlyHint: true`, `destructiveHint: false`, `openWorldHint: false`, `idempotentHint: true` |

Inputs:

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `query` | string | yes | A complete natural-language question, for example "What pets do I have?" |
| `max_photos` | integer, 0 to 10, default 3 | no | How many photos to return; 0 for a text-only answer |

Output: a text block with the answer. When photos are returned, the answer is followed by a
`<photos>` block containing a JSON list of photos. The block is omitted when `max_photos` is 0 or no
photos match. Each photo has `url` (an HTTPS link that expires after 1 hour), `location` (where it
was taken, when known), and `date` (when it was taken, when known).

### `dazzle_ask`

Answers a question about the user's own life in text, without photos.

| | |
|---|---|
| Class | Read |
| Permission | `query` scope |
| Side effects | None |
| Annotations | `readOnlyHint: true`, `destructiveHint: false`, `openWorldHint: false`, `idempotentHint: true` |

Inputs:

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `query` | string | yes | A complete natural-language question |

Output: a text answer, plus `structuredContent` of `{ "message": string, "photos": [] }`.

### `dazzle_photos`

Shows photos from the user's own library in a gallery widget (`ui://dazzle/photo-viewer.html`).

| | |
|---|---|
| Class | Read |
| Permission | `query` scope |
| Side effects | None |
| Annotations | `readOnlyHint: true`, `destructiveHint: false`, `openWorldHint: false`, `idempotentHint: true` |

Inputs:

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `query` | string | yes | What to show, for example "Show me my dog" |
| `max_photos` | integer, 1 to 10, default 3 | no | How many photos to show |

Output: a short text answer, plus `structuredContent` of
`{ "message": string, "photos": [{ "url", "location", "date" }] }`. Photo links expire after 1 hour.

## Errors

| Situation | Response |
|-----------|----------|
| Missing, expired, or revoked token | HTTP 401 with `WWW-Authenticate: Bearer resource_metadata=...`, which starts sign-in |
| Malformed JSON | JSON-RPC error `-32700` |
| Unknown tool, missing `query`, or `max_photos` out of range | JSON-RPC error `-32600` |
| Unsupported method | JSON-RPC error `-32601` |
| Rate limit reached | Tool result with `isError: true`: "Rate limit exceeded — retry in 60 seconds." |
| Temporary outage | Tool result with `isError: true`: "Service temporarily unavailable, retry later." |
| Query failure | Tool result with `isError: true`: "An error occurred processing your query." |

## Limits

- 60 tool calls per minute per user.
- A query can take up to about 60 seconds, especially for long time ranges.
- Answers come only from photos the user has shared with Dazzle. If nothing matches, Dazzle says so.

## Data and privacy

Dazzle only reads the signed-in user's own photos and profile, returns what is needed to answer
the question, and does not use private data to train public AI models. See
the [privacy policy](https://dazzle.ai/privacy-policy/) and
[terms of service](https://dazzle.ai/terms-of-service/). Support:
[dazzle.ai/support](https://dazzle.ai/support/).
