# Dazzle Photo Intelligence for ChatGPT

The plugin package submitted to the ChatGPT plugin directory.

- `plugin/` is the ZIP root: `plugin.json` (listing, review test cases, publication countries),
  `mcp.json` (the hosted MCP server at `https://api.dazzle.ai/apps/chatgpt` with OAuth),
  the onboarding skill, and icons.
- `build_plugin.py` checks the package against OpenAI's submission rules and builds the
  upload ZIP.

```bash
make openai-plugin-validate   # check the package
make openai-plugin-zip        # check, then write dist/dazzle-photo-intelligence-<version>.zip
```

Bump `version` in `plugin/plugin.json` for every upload after the first.
