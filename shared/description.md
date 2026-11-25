# Dazzle — product copy

## One-liner

An AI agent that deeply understands you through your photos.

## Short (≤140 chars)

Dazzle deeply understands you through your photos — who you are, where you live, your
preferences, and the people and places in your life. Ask it anything about your own life.

## Long

Dazzle is a personal AI agent that deeply understands you through your photos. Through a
companion iOS app, Dazzle learns who you are — where you live, the people in your life, the
places you've been, your routines and preferences — and answers natural-language questions
about your own life, returning a written answer plus the relevant photos. Connect it to your
agent to make every personalized question ("what gift would my dad like?", "where should we
eat tonight?", "what did I do last weekend?") answerable from your real history.

## Tools

Text-only clients (Claude Code, Codex, generic `/mcp`):

- **`dazzle`** (Dazzle Personal Assistant): `query`, optional `max_photos`; returns `message` + `photos` (`{url, location, date}`) inline

Clients that render MCP Apps (Claude.ai, ChatGPT):

- **`dazzle_ask`** (Dazzle Personal Assistant): `query`; returns a text answer, no photos
- **`dazzle_photos`** (Dazzle Photo Gallery): `query`, optional `max_photos`; renders a photo gallery widget and returns `message` + `photos`

All tools are annotated read-only, non-destructive, closed-world, and idempotent.
