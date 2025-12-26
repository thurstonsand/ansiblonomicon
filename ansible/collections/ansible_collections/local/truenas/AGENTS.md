# local.truenas Collection

Thin Ansible wrappers around TrueNAS SCALE's `midclt` CLI.

## Commands

Run from repo root:
- `uv run poe lint` — Lint everything (includes this collection)
- `uv run ruff check ansible/collections/` — Python linting only
- `uv run basedpyright` — Type checking only

## Module Pattern

Each module defines these constants, then follows query→compare→act→report:
- `RESOURCE` — midclt endpoint (e.g., `"initshutdownscript"`)
- `IDENTITY_FIELD` — Field used to find existing resources (e.g., `"comment"`)
- `MANAGED_FIELDS` — List of fields that can be set via the module

## Code Style

- Full type annotations required (strict basedpyright)
- Type stubs for `ansible.module_utils.basic` are in `stubs/` at repo root
- Use `ResourceRecord = dict[str, Any]` for TrueNAS API responses
- DOCUMENTATION/EXAMPLES/RETURN docstrings go before imports (Ansible convention)
- Use FQCN in examples: `local.truenas.modulename`, not just `modulename`
