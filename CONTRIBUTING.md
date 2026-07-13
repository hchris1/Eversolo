# Contributing

Contributions and hardware validation are welcome.

## Before opening a pull request

1. Create a focused branch.
2. Keep existing entity unique IDs unless the change includes a tested migration.
3. Never hard-code input or output lists for one Eversolo model.
4. Add or update response fixtures for each affected model/firmware.
5. Run:

    python -m ruff check .
    python -m ruff format --check .
    python -m pytest

## API changes

The Eversolo/Zidoo API differs by model and firmware. New endpoints should:

- use structured query parameters;
- map unsupported status codes to EversoloApiClientUnsupportedError;
- avoid adding extra calls to the two-second polling path;
- preserve the previous cached value when an optional setting temporarily fails;
- include sanitized sample responses and tests.

Do not include passwords, IP addresses, MAC addresses, library paths, account data, or media URLs from a real installation.

## Bug reports

Use the templates in this repository and include:

- model and firmware;
- Home Assistant version;
- integration version;
- redacted diagnostics;
- exact reproduction steps.

Report issues at [TheFab21/Eversolo](https://github.com/TheFab21/Eversolo/issues).
