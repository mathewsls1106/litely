# Plan for Mateo: Implement SSM Tunnel Manager (conecte_tunnels)

## Goal
Replace the existing Bash script with a modern interactive Python TUI that:
- Manages AWS SSM port‑forwarding tunnels.
- Automatically refreshes AWS SSO credentials.
- Stores tunnel definitions in a JSON/YAML config file.
- Allows the user to add, edit, and remove tunnels via the UI.
- Runs inside an isolated vertical‑slice directory `conecte_tunnels/`.

## Tasks
1. **Scaffold package**
   - Create `conecte_tunnels/` with `__init__.py`, `__main__.py`, `app.py`, `tunnel_manager.py`, `credential_helper.py`, `utils.py`, `config.yaml` (sample tunnels), and optional `logging.yaml`.
2. **Credential helper** (`credential_helper.py`)
   - Detect `AWS_PROFILE`.
   - Use `boto3.Session()` to get credentials and expiration.
   - If credentials expire within 2 min, run `aws sso login` via subprocess.
   - Provide `get_identity()` returning the ARN for UI display.
3. **Tunnel manager** (`tunnel_manager.py`)
   - Functions to start/stop tunnels using `aws ssm start-session`.
   - Support DB tunnel and remote‑host tunnel formats.
   - Track subprocesses (PID, status) in a dictionary.
   - Provide `list_active()` for UI.
4. **Textual UI** (`app.py`)
   - Load `config.yaml`.
   - Show identity panel (ARN, expiry).
   - Table of tunnels (name, remote, local, status, PID).
   - Buttons: Start All, Stop All, Refresh Credentials, Add, Edit, Remove, Quit.
   - Modals for add/edit (use Textual Input widgets).
   - Periodic timer (30 s) to refresh credential status and tunnel health.
   - On exit, clean up all running tunnel subprocesses.
5. **CLI entrypoint** (`__main__.py`)
   - `from .app import ConecteApp; ConecteApp().run()`.
6. **Update pyproject.toml**
   - Add package path and optional console script entry point.
   - Add `PyYAML` to dependencies if missing.
7. **Logging** (optional) – simple rotating file under `logs/`.
8. **Documentation** – brief README in `conecte_tunnels/` with usage.

## Verification
- Run `python -m conecte_tunnels` → UI opens, shows identity.
- Click **Start All** → verify `aws ssm start-session` processes appear.
- Add a new tunnel via UI, start it, then remove it → process lifecycle correct.
- Simulate credential expiry → **Refresh Credentials** triggers `aws sso login` and UI updates ARN.
- Exit UI → all tunnel processes terminated.

## Notes
- Use `subprocess.Popen(..., preexec_fn=os.setsid)` for proper group termination.
- Validate that `local_port` is free before starting a tunnel.
- Use atomic writes for `config.yaml` updates.
- Keep the package self‑contained; no changes to existing `core/` or `s3_tui/`.
