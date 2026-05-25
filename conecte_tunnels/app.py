"""Textual UI for managing SSM tunnels."""
import os
from pathlib import Path
import yaml
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, DataTable, Button, Static, Input, Select
from datetime import datetime, timezone
from textual.screen import ModalScreen
from textual.containers import Container, Horizontal
from .credential_helper import get_identity
from .tunnel_manager import TunnelManager

CONFIG_PATH = Path(__file__).with_name("config.yaml")


class ConecteApp(App):
    CSS_PATH = "conecte.css"
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "refresh", "Refresh Credentials"),
        ("c", "cleanup", "Cleanup Sessions"),
        ("enter", "start_selected", "Start Selected"),
    ]

    def __init__(self):
        self.single_active = False  # allow multiple tunnels at once
        self._ssm_expiry = None
        super().__init__()
        self.tunnel_manager = TunnelManager()
        self.identity_label = Static("Identity: loading...", id="identity")
        self.table = DataTable(id="tunnel-table")
        self.status = Static("", id="status")
        self.instance_tag = "Fullstack App"
        self.config = []

    def compose(self) -> ComposeResult:
        yield Header()
        yield self.identity_label
        yield self.table
        with Horizontal():
            yield Button("Start All", id="start_all")
            yield Button("Stop All", id="stop_all")
            yield Button("Add", id="add")
            yield Button("Edit", id="edit")
            yield Button("Remove", id="remove")
            yield Button("Refresh Credentials", id="refresh_creds")
            yield Button("Cleanup", id="cleanup")
        yield self.status
        yield Footer()

    async def on_mount(self) -> None:
        await self.refresh_identity()
        self.load_config()
        arn = None
        try:
            arn, _ = get_identity()
        except Exception:
            pass
        self.tunnel_manager.find_instance(self.instance_tag)
        if self.tunnel_manager.instance_id:
            self.tunnel_manager.cleanup_sessions(arn)
            self.status.update(f"Instance: {self.tunnel_manager.instance_id} | Sessions cleaned")
        else:
            self.status.update(f"ERROR: Instance with tag '{self.instance_tag}' not found")
        self.refresh_table()
        # Refresh credentials every 30 seconds
        self.set_interval(30, self.refresh_identity)
        # Monitor SSM expiry every 60 seconds
        self.set_interval(60, self._monitor_ssm_expiry)
        # Check and restart dead tunnels every 30 seconds
        self.set_interval(30, self._auto_restart_dead_tunnels)

    async def refresh_identity(self) -> None:
        try:
            arn, expiry = get_identity()
            self._ssm_expiry = expiry
            self.identity_label.update(f"Identity: {arn} (expires {expiry.isoformat()})")
        except Exception as e:
            self._ssm_expiry = None
            self.identity_label.update(f"Identity: error {e}")

    async def _monitor_ssm_expiry(self) -> None:
        """Check if SSM credentials have expired and restart tunnels if needed."""
        if self._ssm_expiry is None:
            return
        # Compare in UTC
        now = datetime.now(timezone.utc)
        if now >= self._ssm_expiry:
            # Refresh credentials
            await self.refresh_identity()
            # Restart tunnels according to single_active mode
            if self.single_active:
                # Stop any running tunnels
                self.tunnel_manager.stop_all()
                # Start first configured tunnel if any
                if self.config:
                    entry = self.config[0]
                    try:
                        self.tunnel_manager.start_tunnel(
                            entry["name"],
                            entry.get("type", "port"),
                            entry.get("remote_host", ""),
                            entry["remote_port"],
                            entry["local_port"],
                        )
                        self.status.update(f"Auto-restarted {entry['name']} after credential refresh")
                    except Exception as e:
                        self.status.update(f"Error restarting {entry['name']}: {e}")
            else:
                # Restart all configured tunnels
                for entry in self.config:
                    try:
                        self.tunnel_manager.start_tunnel(
                            entry["name"],
                            entry.get("type", "port"),
                            entry.get("remote_host", ""),
                            entry["remote_port"],
                            entry["local_port"],
                        )
                    except Exception as e:
                        self.status.update(f"Error restarting {entry['name']}: {e}")
            self.refresh_table()

    def _auto_restart_dead_tunnels(self) -> None:
        """Check for dead tunnels and restart them automatically."""
        dead = self.tunnel_manager.get_dead_tunnels()
        if dead:
            for info in dead:
                # Find matching config entry
                for entry in self.config:
                    if entry["name"] == info.name:
                        try:
                            self.tunnel_manager.start_tunnel(
                                entry["name"],
                                entry.get("type", "port"),
                                entry.get("remote_host", ""),
                                entry["remote_port"],
                                entry["local_port"],
                            )
                            self.status.update(f"Auto-restarted {entry['name']}")
                        except Exception as e:
                            self.status.update(f"Error auto-restarting {entry['name']}: {e}")
                        break
            self.refresh_table()

    def load_config(self) -> None:
        if CONFIG_PATH.is_file():
            with open(CONFIG_PATH) as f:
                data = yaml.safe_load(f) or {}
                self.instance_tag = data.get("instance", {}).get("tag_name", "Fullstack App")
                self.config = data.get("tunnels", [])
        else:
            self.instance_tag = "Fullstack App"
            self.config = []

    def save_config(self) -> None:
        data = {"instance": {"tag_name": self.instance_tag}, "tunnels": self.config}
        tmp = CONFIG_PATH.with_suffix(".tmp")
        with open(tmp, "w") as f:
            yaml.safe_dump(data, f)
        os.replace(tmp, CONFIG_PATH)

    def refresh_table(self) -> None:
        self.table.clear(columns=True)
        self.table.add_columns("Name", "Type", "Remote", "Local Port", "Status", "PID")
        for ti in self.tunnel_manager.list_active():
            if ti.tunnel_type == "port":
                remote = str(ti.remote_port)
            else:
                remote = f"{ti.remote_host}:{ti.remote_port}"
            self.table.add_row(ti.name, ti.tunnel_type, remote, str(ti.local_port), "Running", str(ti.process.pid))
        for entry in self.config:
            if entry["name"] not in self.tunnel_manager.tunnels:
                ttype = entry.get("type", "port")
                if ttype == "port":
                    remote = str(entry["remote_port"])
                else:
                    remote = f"{entry.get('remote_host', '?')}:{entry['remote_port']}"
                self.table.add_row(entry["name"], ttype, remote, str(entry["local_port"]), "Stopped", "-")

    def action_quit(self) -> None:
        self.tunnel_manager.stop_all()
        self.exit()

    async def action_refresh(self) -> None:
        await self.refresh_identity()

    async def action_cleanup(self) -> None:
        try:
            arn, _ = get_identity()
            self.tunnel_manager.cleanup_sessions(arn)
            self.status.update("Sessions cleaned up")
        except Exception as e:
            self.status.update(f"Cleanup error: {e}")

    def action_start_selected(self) -> None:
        """Start the selected tunnel."""
        if self.table.cursor_row is not None:
            row = self.table.get_cell_at(self.table.cursor_row)
            name = row[0] if row else None
            if name and name not in self.tunnel_manager.tunnels:
                # Find config entry
                for entry in self.config:
                    if entry["name"] == name:
                        try:
                            self.tunnel_manager.start_tunnel(
                                entry["name"],
                                entry.get("type", "port"),
                                entry.get("remote_host", ""),
                                entry["remote_port"],
                                entry["local_port"],
                            )
                            self.status.update(f"Started {entry['name']}")
                        except Exception as e:
                            self.status.update(f"Error starting {entry['name']}: {e}")
                        break
                self.refresh_table()

    async def on_button_pressed(self, event) -> None:
        btn_id = event.button.id
        if btn_id == "start_all":
            if self.single_active:
                # Stop any running tunnels first
                self.tunnel_manager.stop_all()
                # Start only the first configured tunnel
                if self.config:
                    entry = self.config[0]
                    try:
                        self.tunnel_manager.start_tunnel(
                            entry["name"],
                            entry.get("type", "port"),
                            entry.get("remote_host", ""),
                            entry["remote_port"],
                            entry["local_port"],
                        )
                    except Exception as e:
                        self.status.update(f"Error starting {entry['name']}: {e}")
            else:
                for entry in self.config:
                    if entry["name"] not in self.tunnel_manager.tunnels:
                        try:
                            self.tunnel_manager.start_tunnel(
                                entry["name"],
                                entry.get("type", "port"),
                                entry.get("remote_host", ""),
                                entry["remote_port"],
                                entry["local_port"],
                            )
                        except Exception as e:
                            self.status.update(f"Error starting {entry['name']}: {e}")
            self.refresh_table()
        elif btn_id == "stop_all":
            self.tunnel_manager.stop_all()
            self.refresh_table()
        elif btn_id == "add":
            await self.push_screen(AddEditScreen(self, mode="add"))
        elif btn_id == "remove":
            if self.table.cursor_row is not None:
                row = self.table.get_cell_at(self.table.cursor_row)
                name = row[0] if row else None
                if name:
                    self.tunnel_manager.stop_tunnel(name)
                    self.config = [c for c in self.config if c["name"] != name]
                    self.save_config()
                    self.refresh_table()
        elif btn_id == "edit":
            if self.table.cursor_row is not None:
                row = self.table.get_cell_at(self.table.cursor_row)
                name = row[0] if row else None
                if name:
                    await self.push_screen(AddEditScreen(self, mode="edit", edit_name=name))
                    # Table will refresh after screen pops via on_screen_dismiss
        elif btn_id == "refresh_creds":
            await self.refresh_identity()
        elif btn_id == "cleanup":
            await self.action_cleanup()

    async def on_screen_dismiss(self) -> None:
        self.refresh_table()

    def on_data_table_row_selected(self, event) -> None:
        """Handle row selection - could be used for future actions."""
        pass


class AddEditScreen(ModalScreen):
    def __init__(self, app: ConecteApp, mode: str = "add", edit_name: str | None = None):
        super().__init__()
        self.parent_app = app
        self.mode = mode
        self.edit_name = edit_name

    def compose(self) -> ComposeResult:
        with Container(id="dialog"):
            yield Input(placeholder="Name", id="name")
            yield Select(
                [("Instance Port", "port"), ("Remote Host", "remote_host")],
                prompt="Tunnel Type",
                value="port",
                id="tunnel_type",
            )
            yield Input(placeholder="Remote Host (IP, for Remote Host type)", id="remote_host")
            yield Input(placeholder="Remote Port", id="remote_port")
            yield Input(placeholder="Local Port", id="local_port")
            yield Static("", id="status")
            with Horizontal():
                yield Button("Save", id="save", variant="primary")
                yield Button("Cancel", id="cancel")

    def on_mount(self) -> None:
        name_input = self.query_one("#name", Input)
        if self.mode == "edit" and self.edit_name:
            for entry in self.parent_app.config:
                if entry["name"] == self.edit_name:
                    name_input.value = entry["name"]
                    name_input.disabled = True  # Prevent name changes
                    self.query_one("#tunnel_type", Select).value = entry.get("type", "port")
                    self.query_one("#remote_host", Input).value = entry.get("remote_host", "")
                    self.query_one("#remote_port", Input).value = str(entry["remote_port"])
                    self.query_one("#local_port", Input).value = str(entry["local_port"])
                    break

    async def on_button_pressed(self, event) -> None:
        status = self.query_one("#status", Static)
        if event.button.id == "save":
            name = self.query_one("#name", Input).value.strip()
            tunnel_type = self.query_one("#tunnel_type", Select).value
            remote_host = self.query_one("#remote_host", Input).value.strip()
            remote_port_str = self.query_one("#remote_port", Input).value.strip()
            local_port_str = self.query_one("#local_port", Input).value.strip()

            # Validate required fields
            if not name:
                status.update("Error: Name is required")
                return
            if not remote_port_str.isdigit():
                status.update("Error: Remote Port must be a number")
                return
            if not local_port_str.isdigit():
                status.update("Error: Local Port must be a number")
                return

            remote_port = int(remote_port_str)
            local_port = int(local_port_str)

            # Check for duplicate name in add mode
            if self.mode == "add":
                for existing in self.parent_app.config:
                    if existing["name"] == name:
                        status.update(f"Error: Tunnel '{name}' already exists")
                        return

            entry = {
                "name": name,
                "type": tunnel_type,
                "remote_port": remote_port,
                "local_port": local_port,
            }
            if tunnel_type == "remote_host":
                if not remote_host:
                    status.update("Error: Remote Host is required for Remote Host type")
                    return
                entry["remote_host"] = remote_host

            if self.mode == "add":
                self.parent_app.config.append(entry)
            else:
                # Replace the entire entry instead of modifying in place
                new_config = []
                for c in self.parent_app.config:
                    if c["name"] == self.edit_name:
                        new_config.append(entry)
                    else:
                        new_config.append(c)
                self.parent_app.config = new_config

            self.parent_app.save_config()
            self.parent_app.refresh_table()
            await self.parent_app.pop_screen()
        else:
            await self.parent_app.pop_screen()
