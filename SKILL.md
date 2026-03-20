---
name: youtube
description: Summarize YouTube videos from links using the local chrome-youtube-skill project. Use when a user shares a YouTube URL (youtube.com, youtu.be, shorts) and asks for a transcript, summary, key points, or breakdown. Extract transcript with this project's Python tool, then return a concise actionable summary personalized to the user's projects, goals, and work style.
---

# YouTube Summary (project-backed)

Use this workflow every time this skill is invoked.

## 1) Extract transcript with the project tool (required)

Run:

```bash
TMP_JSON="$(mktemp -t yt_transcript_XXXXXX.json)"

if [ -x ./scripts/run_transcript.py ]; then
  ./scripts/run_transcript.py "<YOUTUBE_URL>" --json --json-out "$TMP_JSON" >/dev/null
elif [ -x ./extract ]; then
  ./extract "<YOUTUBE_URL>" --json --json-out "$TMP_JSON" >/dev/null
else
  echo "Runner not found. Run from the youtube skill root."
  exit 1
fi

cat "$TMP_JSON"
```

Rules:
- Always use this project tool for extraction.
- Do not switch to other transcript tools.
- The extractor launches a visible Chrome session; extract **once** per URL and reuse `TMP_JSON` for downstream steps.
- Parse JSON output and check `success`.

## 2) Handle extraction failure

If `success` is false:
- Reply with a short failure note.
- Include the tool's error text.
- Ask for another link or a retry.

## 3) Build summary in the exact target markdown shape

When extraction succeeds, build output with this exact structure:

```markdown
## <title> (<channel>)

**URL:** <video_url>

### Key points
- ...

### Relevant to you
- ...

### Actionable items
- ...
```

Content rules:
- Key points: 5-8 bullets
- Relevant to you: 3-5 bullets personalized
- Actionable items: 3-5 concrete next steps

Personalization targets for the user:
- OpenClaw monetization and skill/product opportunities
- Shipping habits, distribution consistency, and creator workflow
- Builder-first decisions for indie products (pricing, positioning, MVP scope)
- Practical next actions he can do today

## 4) Response style

- Keep it concise, useful, and concrete.
- Avoid fluff and generic motivation.
- Prefer explicit next steps over abstract advice.

## 5) Required save

On every successful run, always write the summary file to a configured output directory.

**Output directory resolution:**
1. Read from `skill.config` in the project root (format: `OUTPUT_DIR=/path/to/directory`)
2. If config doesn't exist or `OUTPUT_DIR` is not set, fall back to `~/youtube_transcripts`

**File path format:** `<output_directory>/<channel> - <title>.md`

Rules:
- Create output directory if it does not exist.
- Sanitize filename characters (`/ \\ : * ? " < > |`) to `_`.
- File contents must exactly match the markdown structure in Step 3.
- Save via shell `exec` (not `write`) because file tools are workspace-root sandboxed and will reject paths outside workspace with `Path escapes workspace root`.
- Use a safe heredoc pattern for writes (example):

```bash
# Read output directory from config or use default
if [ -f skill.config ]; then
  source skill.config
fi
OUTPUT_DIR="${OUTPUT_DIR:-$HOME/youtube_transcripts}"

mkdir -p "$OUTPUT_DIR"
cat > "$OUTPUT_DIR/<channel> - <title>.md" <<'MD'
<full markdown summary>
MD
```

- After saving, output the exact absolute path of the saved file.

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
