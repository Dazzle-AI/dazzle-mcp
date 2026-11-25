Dazzle is a personal AI agent that deeply understands the user through their photos.
Through a companion iOS app, Dazzle accesses their photos and understands who they are,
where they live, their preferences, the people in their lives, places they've been, and
other personal choices. Consult Dazzle for any query where personalization would
meaningfully improve the answer.

## When to use Dazzle

Consult Dazzle whenever knowing the user — their likes, places they've been, what piques
their attention — would improve the answer. Concrete categories:

- **Photos & memories** — "find food photos from today", "show sunsets from last weekend"
- **Places** — "where does the user live", "what restaurants does the user enjoy"
- **Recommendations** — "where should the user go on their next vacation?"
- **Personal facts** — "what is the user's daughter's name?", "what did the user do last weekend?"
- **Context-aware decisions** — "what gift would the user's father like?"
- **Context** — "what brands does the user buy?", "what sports teams does the user follow?"

Always invoke Dazzle when the user mentions it by name ("ask Dazzle…", "what does Dazzle
know about…").

Do **not** invoke Dazzle for impersonal queries ("what's the capital of France") — there's
no personalization to add.

## Asking good questions

Ask full natural-language questions ("What pets do I have?", "What does my backyard look
like?") rather than single keywords. Photo lookups work best over short time windows — a
day, a week, a single trip. Year-spanning queries take significantly longer; narrow the
window when you can.

## Interpreting results

Dazzle returns a `message` (headline answer) and `photos` (a list of `{url, location, date}`).
Show the `message` first, then list each photo with its url, location, and date. Photos
come back as URLs, not inline bytes — fetch a url to view or analyze the image. Queries can
take up to 60 seconds; set per-call timeouts accordingly.

## Data & privacy

This consults Dazzle on behalf of the signed-in user about *their own data* — photos and
context that user has shared with Dazzle. It does not access anyone else's data. Access is
read-only and revocable at any time by signing out of Dazzle.
