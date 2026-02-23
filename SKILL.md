---
name: youtube
description: Summarize YouTube videos from links using the local chrome-youtube-transcript project. Use when a user sends a YouTube URL (youtube.com, youtu.be, shorts) and asks for a transcript, summary, key points, or breakdown. Extract transcript with this project’s Python tool, then return a concise actionable summary personalized to Nick’s projects, goals, and work style.
---

# YouTube Summary (project-backed)

Use this workflow every time this skill is invoked.

## 1) Extract transcript with the project tool (required)

Run:

```bash
python3 /Users/mike/projects/chrome-youtube-transcript/extract_transcript.py "<YOUTUBE_URL>" --json
```

Rules:
- Always use this project tool for extraction.
- Do not switch to other transcript tools.
- Parse JSON output and check `success`.

## 2) Handle extraction failure

If `success` is false:
- Reply with a short failure note.
- Include the tool’s error text.
- Ask for another link or a retry.

## 3) Build summary from transcript

When extraction succeeds, produce:
- **Title + channel**
- **Key points** (5–8 bullets)
- **Actionable for Nick** (3–5 bullets tied to his context)

Personalization targets for Nick:
- OpenClaw monetization and skill/product opportunities
- Shipping habits, distribution consistency, and creator workflow
- Builder-first decisions for indie products (pricing, positioning, MVP scope)
- Practical next actions he can do today

## 4) Response style

- Keep it concise, useful, and concrete.
- Avoid fluff and generic motivation.
- Prefer explicit next steps over abstract advice.

## 5) Optional save (only when asked)

If user asks to save artifacts:
- Save transcript to `/Users/Shared/yt_transcripts/<video_id>.txt`
- Save summary to `/Users/Shared/yt_summaries/<video_id>.md`

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
