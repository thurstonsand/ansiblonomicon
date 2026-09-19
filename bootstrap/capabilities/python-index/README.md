# Python index capability

This work-only capability validates ordinary uv TOML from the scalar `python_index_config` in the work target's ignored `mise.local.toml` before writing either target. It copies that value to uv and derives pip configuration from it. Each `[[index]]` requires an HTTP(S) `url`; `default` and `name` retain uv's optional boolean/string forms. At most one index may be the default. Multiple non-default indexes become one pip multiline `extra-index-url` value. Personal and pod042 hosts intentionally have no system Python-index configuration.

Templates and the validator live in `bootstrap/capabilities/python-index/files/`; the work target exposes that directory as `python-index/` beside its mise environment files.

Run `mise python-index` or `mise python-index --check`. Within the work target, select `MISE_ENV=python-index` and run `mise run python-index:apply`; this task prepares the validated input for native rendering. The capability configures indexes only; it does not install or upgrade packages.
