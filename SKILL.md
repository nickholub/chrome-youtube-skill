---
name: youtube
description: Summarize YouTube videos from links using the local chrome-youtube-skill project. Use when a user shares a YouTube URL (youtube.com, youtu.be, shorts) and asks for a transcript, summary, key points, or breakdown. Extract transcript with this project's Python tool, then return a concise actionable summary personalized to Nick's projects, goals, and work style.
---

# YouTube Summary (project-backed)

Use this workflow every time this skill is invoked.

## 1) Extract transcript with the project tool (required)

Run:

```bash
SKILL_DIR="/Users/nick/.codex/skills/youtube"
PYTHONPATH="$SKILL_DIR/src" python3 -m yt_transcript "<YOUTUBE_URL>" --json
```

Rules:
- Always use this project tool for extraction.
- Do not switch to other transcript tools.
- Parse JSON output and check `success`.

## 2) Handle extraction failure

If `success` is false:
- Reply with a short failure note.
- Include the tool's error text.
- Ask for another link or a retry.

## 3) Build summary in the exact target markdown shape

When extraction succeeds, build output with this exact structure:

```markdown
**URL:** <video_url>

## <title> (<channel>)

### Key points
- ...

### Relevant to you
- ...

### Actionable items
- ...
```

Content rules:
- Key points: 5-8 bullets
- Relevant to you: 3-5 bullets personalized to Nick
- Actionable items: 3-5 concrete next steps

Personalization targets for Nick:
- OpenClaw monetization and skill/product opportunities
- Shipping habits, distribution consistency, and creator workflow
- Builder-first decisions for indie products (pricing, positioning, MVP scope)
- Practical next actions he can do today

## 4) Response style

- Keep it concise, useful, and concrete.
- Avoid fluff and generic motivation.
- Prefer explicit next steps over abstract advice.

## 5) Required save + identical Telegram output

On every successful run, always write the summary file to:

`/Users/Shared/yt_summary/<channel> - <title>.md`

Rules:
- Create `/Users/Shared/yt_summary` if it does not exist.
- Sanitize filename characters (`/ \\ : * ? " < > |`) to `_`.
- File contents must exactly match the markdown structure in Step 3.
- Telegram/user reply must be exactly the same text as the saved file (byte-for-byte content match).

## Expected JSON fields

Typical output includes:
- `success`
- `video_id`
- `title`
- `channel`
- `url`
- `transcript`
- `language`
- `method`
- `error`
