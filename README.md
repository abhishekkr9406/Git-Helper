# GitHelper

A lightweight, offline-first desktop companion that sits quietly alongside your normal Git workflow and protects you from losing uncommitted work.

GitHelper is **not** a Git GUI. It does not replace your terminal, editor, or existing Git tools. It is a safety net and a nudge — a small background presence that watches, waits, and only speaks up when it has something genuinely useful to say.

## Requirements

- Python 3.12+
- Git (installed and on PATH)
- Windows 10+ (macOS/Linux support planned)

## Install from Source

```bash
# Clone and enter the project
cd GitHelper

# Create a virtual environment
python -m venv .venv
.venv\Scripts\activate    # Windows
# source .venv/bin/activate  # Linux/macOS

# Install in development mode
pip install -e ".[dev]"
```

## Run

```bash
python -m githelper
```

## Run Tests

```bash
pytest
```

## Documentation

See the `docs/` folder for the complete project specification.

## License

LGPL-3.0-or-later
