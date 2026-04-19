# model segment

Custom `model` segment overrides the built-in `pi-powerline-footer` model segment.

## Style options

Valid style values for both `verbosity.style` and `fast.style` are:

- `compact`
- `text`
- `icon`

`labelled` is no longer supported.

## Provider icon note

The upstream `SegmentContext["model"]` type does not declare `provider`, even though it may exist at runtime.

This segment therefore:

1. uses runtime `model.provider` when present
2. otherwise infers provider from `model.id` / `model.name`

Current provider icons:

- OpenAI → `❁`
- Anthropic → `✴️`
- Google → `✨`
