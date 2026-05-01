---
name: handoff
description: Prepare a prompt for a new thread based on the work done so far, tailored to what the user intends to do next.
argument-hint: "[next task or focus area]"
---

# Handoff

Your goal is to prepare a prompt for a new thread based on the work done so far, tailored to the user prompt for what they intend to do next. You are handing off your work to the next agent to continue executing on the overall goal. You should only include information that is directly relevant to the user prompt, but don't miss anything that might be deemed important.

## Title Prompt

Use the following prompt to guide the title inside the `<title>` tag. The title must be prefixed with `handoff:` and must be enclosed in ``.

> !`jq -r '.prompt // empty' ~/.cache/claude-code-auto-title/config.json 2>/dev/null || echo "A short, specific headline (under 80 chars) that distinguishes this handoff from any other. Capture the specific change, feature, or goal — not a generic label. Avoid vague words like work, updates, or changes."`

## Template

```markdown
`<title>handoff: {title derived from prompt above}</title>`

Continuing work from previous conversation. When you lack specific information, you can first establish the context you need by searching for and reading the necessary files.

\@relevant/file/1.go \@relevant/file/2.md \@relevant/file/3.go

## Summary

- <summary of work done in this thread>
- <it can be multi-line as needed>
- <also include any verification/testing that you've done>

## Next Steps

- <establish goal/focus of new thread>
- <add relevant flavor/information to the user prompt>

<direct copy of the user prompt>
```

## User Prompt

$ARGUMENTS
