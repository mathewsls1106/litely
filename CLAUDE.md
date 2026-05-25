# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Litely is a modular CLI toolbox for AWS operations, built with Python 3.12 and Textual (TUI framework). It uses a plugin-style architecture where each tool is an isolated package registered with the central menu system.

## Running the Application

```bash
# Run the main menu (select a module interactively)
python main.py

# Run a specific module directly
python -m s3_tui.main
python -m conecte_tunnels

# Or via the installed entry point
conecte-tunnels
```

## Dependencies

Managed with `uv`. Install: `uv sync`. Key dependencies: textual, boto3, PyYAML, python-dotenv, django.

## Architecture

### Core: Module Registry Pattern

- `core/module_registry.py` — `MODULES` dict maps display names to import paths. New tools are registered here.
- `core/menu.py` — Reads the registry, presents a numbered CLI menu, dynamically imports the selected module via `importlib`, and calls its `run()` or `main()` entry point.

**To add a new tool**: create a package with a `run()` or `main()` function, then add it to `MODULES` in `core/module_registry.py`.

### S3 Browser (`s3_tui/`)

Vertical-slice architecture with three layers:
- `s3_access.py` — Pure S3 logic (boto3). `S3Client` handles list/upload/download/delete/create_folder. Config comes from AWS SSM Parameter Store with env var fallback (`SSMConfig`).
- `ui_components.py` — Reusable Textual modal widgets (`InputModal`, `ConfirmModal`).
- `app.py` — `S3BrowserApp` (Textual App) orchestrates UI + S3 ops. Uses `@work` decorators for async operations and `asyncio.to_thread` for blocking boto3 calls.
- `main.py` — Entry point with `run()`, validates `DJANGO_AWS_STORAGE_BUCKET_NAME` env var before launching.

### SSM Tunnel Manager (`conecte_tunnels/`)

- `credential_helper.py` — AWS SSO credential management. Auto-triggers `aws sso login` if credentials expire within 2 minutes.
- `tunnel_manager.py` — Manages SSM port-forwarding subprocesses. Supports two tunnel types: direct instance port and remote host. Uses `os.setsid` for process group management.
- `app.py` — `ConecteApp` (Textual App) with tunnel table, add/edit modals, periodic credential refresh (30s), and SSM expiry monitoring (60s). Enforces `single_active` mode (one tunnel at a time).
- `config.yaml` — Tunnel definitions (name, type, remote_host, remote_port, local_port). Atomically written via tmp+replace.
- `__main__.py` — Entry point with `main()`.

### Key Patterns

- Each tool package is self-contained; no cross-dependencies between `s3_tui/` and `conecte_tunnels/`.
- Both packages support dual import: as a module (`from .app import ...`) and directly (`if __package__ is None`).
- S3 operations return `(success_bool, error_string | None)` tuples.
- Tunnel processes are subprocess.Popen with process groups; cleanup sends SIGTERM to the group, then falls back to kill.
