---
name: dazzle-photo-intelligence
description: Answer questions about the signed-in user's own life from their Dazzle photo library, such as their pets, family and friends, home, trips, hobbies, and tastes, and show matching photos. Use when the user asks about their own life, history, or photos, or mentions Dazzle by name. Do not use for general knowledge or public images.
---

# Dazzle Photo Intelligence

Dazzle Photo Intelligence answers questions about the signed-in user's own life from the
photos they share with the Dazzle iPhone app and the profile Dazzle builds from them.

## Tools

- `dazzle_ask` returns a written answer for you to present or build on. Use it for
  questions like "What pets do I have?", "What type of food do I enjoy?", or when you need
  facts about the user to personalize a recommendation ("What gift would my dad like?").
- `dazzle_photos` displays a photo gallery to the user. Use it only when the user wants
  to see photos ("Show me my dog", "What does my backyard look like?"). Once the gallery
  is shown, add at most a short framing line and do not list the photos again.

## Asking good questions

Send one complete natural-language question per call, not keywords. Photo lookups work
best over a short time window, such as a day, a week, or a single trip.

## When Dazzle finds nothing

Answers come only from photos the user has shared with Dazzle. If Dazzle finds nothing
relevant, say so plainly and do not guess. A user without the Dazzle iPhone app, or with
no photos shared yet, can install the app from https://dazzle.ai.

## What Dazzle cannot do

Dazzle is read-only. It cannot search the web, find public images, or edit, upload, share,
or delete photos.
