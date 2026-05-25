"""Vertical 3: Aplicación Principal - Orquestación UI y lógica de negocio"""

import asyncio
import os
import sys

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import DataTable, Footer, Header, Static

# Support both running as a module and directly
if __package__ is None:
    from s3_access import S3Client
    from ui_components import ConfirmModal, InputModal
else:
    from .s3_access import S3Client
    from .ui_components import ConfirmModal, InputModal


class S3BrowserApp(App):
    """Aplicación principal del navegador S3."""

    CSS = """
  Screen {
      layout: vertical;
  }

  DataTable {
      height: 1fr;
      border: solid green;
  }

  .modal-container {
      padding: 2;
      background: $surface;
      border: thick $primary;
      width: 60;
      height: auto;
      align: center middle;
  }

  .buttons {
      width: 100%;
      align: center middle;
      margin-top: 1;
  }

  Button {
      margin: 0 1;
  }

  #path_display {
      background: $boost;
      padding: 0 1;
      dock: top;
  }
  """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("u", "upload", "Upload"),
        Binding("n", "new_folder", "New Folder"),
        Binding("d", "delete", "Delete"),
        Binding("w", "download", "Download"),
        Binding("b", "back", "Back"),
    ]

    def __init__(self):
        super().__init__()
        self.s3_client = S3Client()
        self.current_prefix = ""
        self.current_items = []

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(
            f"Bucket: {self.s3_client.bucket_name} | Path: /", id="path_display"
        )
        yield DataTable(cursor_type="row")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("Type", "Name", "Size", "Modified")
        self.load_directory(self.current_prefix)

    @work(exclusive=True)
    async def load_directory(self, prefix):
        table = self.query_one(DataTable)
        table.loading = True
        self.query_one("#path_display").update(
            f"Bucket: {self.s3_client.bucket_name} | Path: /{prefix}"
        )

        # Run S3 op in a thread
        items, error = await asyncio.to_thread(self.s3_client.list_objects, prefix)

        table.loading = False
        table.clear()

        if error:
            self.notify(f"Error: {error}", severity="error")
            return

        self.current_items = items
        for item in items:
            # We use the 'key' as the row key
            icon = "📁" if item["type"] == "folder" else "📄"
            table.add_row(
                icon, item["name"], item["size"], item["last_modified"], key=item["key"]
            )

        table.focus()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        selected_key = event.row_key.value
        selected_item = next(
            (i for i in self.current_items if i["key"] == selected_key), None
        )

        if selected_item and selected_item["type"] == "folder":
            if selected_item["name"] == "..":
                # Navigate up
                # Logic handled in list_objects creating the ".." key correctly?
                # Actually, my list_objects ".." key is the parent prefix.
                self.current_prefix = selected_item["key"]
                if self.current_prefix == ".":
                    self.current_prefix = ""
            else:
                self.current_prefix = selected_item["key"]

            self.load_directory(self.current_prefix)

    def action_refresh(self):
        self.load_directory(self.current_prefix)

    def action_back(self):
        if not self.current_prefix:
            return

        # Simple string manipulation to go back
        parts = self.current_prefix.rstrip("/").split("/")
        if len(parts) <= 1:
            self.current_prefix = ""
        else:
            self.current_prefix = "/".join(parts[:-1]) + "/"

        self.load_directory(self.current_prefix)

    @work
    async def action_upload(self):
        def handle_input(local_path):
            if local_path:
                # Remove optional @ prefix if user used it
                if local_path.startswith("@"):
                    local_path = local_path[1:]
                self.perform_upload(local_path)

        self.push_screen(
            InputModal("Enter local path (file or folder):", "./"), handle_input
        )

    @work
    async def perform_upload(self, local_path):
        if not os.path.exists(local_path):
            self.notify("Path not found!", severity="error")
            return

        if os.path.isdir(local_path):
            # Folder upload logic
            base_folder_name = os.path.basename(os.path.normpath(local_path))
            self.notify(f"Starting upload of folder: {base_folder_name}...")

            files_to_upload = []
            for root, dirs, files in os.walk(local_path):
                for file in files:
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, local_path)
                    # S3 Key: current_prefix + base_folder_name + / + relative_path
                    # Ensure slashes are forward slashes for S3
                    s3_rel_path = os.path.join(base_folder_name, rel_path).replace(
                        os.sep, "/"
                    )
                    s3_key = self.current_prefix + s3_rel_path
                    files_to_upload.append((full_path, s3_key))

            total = len(files_to_upload)
            success_count = 0

            for fpath, skey in files_to_upload:
                success, error = await asyncio.to_thread(
                    self.s3_client.upload_file, fpath, skey
                )
                if success:
                    success_count += 1
                else:
                    self.notify(
                        f"Failed to upload {os.path.basename(fpath)}: {error}",
                        severity="error",
                    )

            self.notify(
                f"Folder upload complete. {success_count}/{total} files uploaded.",
                severity="information",
            )
            self.load_directory(self.current_prefix)

        else:
            # Single file upload
            filename = os.path.basename(local_path)
            s3_key = self.current_prefix + filename

            self.notify(f"Uploading {filename}...")
            success, error = await asyncio.to_thread(
                self.s3_client.upload_file, local_path, s3_key
            )

            if success:
                self.notify("Upload successful!", severity="information")
                self.load_directory(self.current_prefix)
            else:
                self.notify(f"Upload failed: {error}", severity="error")

    @work
    async def action_new_folder(self):
        def handle_input(folder_name):
            if folder_name:
                self.perform_create_folder(folder_name)

        self.push_screen(InputModal("Enter new folder name:", ""), handle_input)

    @work
    async def perform_create_folder(self, folder_name):
        self.notify(f"Creating folder {folder_name}...")
        success, error = await asyncio.to_thread(
            self.s3_client.create_folder, self.current_prefix, folder_name
        )

        if success:
            self.notify("Folder created!", severity="information")
            self.load_directory(self.current_prefix)
        else:
            self.notify(f"Failed to create folder: {error}", severity="error")

    @work
    async def action_delete(self):
        table = self.query_one(DataTable)
        try:
            row_key = table.coordinate_to_cell_key(
                table.cursor_coordinate
            ).row_key.value
        except:
            self.notify("No item selected", severity="warning")
            return

        selected_item = next(
            (i for i in self.current_items if i["key"] == row_key), None
        )
        if not selected_item or selected_item["name"] == "..":
            return

        def handle_confirm(confirmed):
            if confirmed:
                self.perform_delete(row_key)

        self.push_screen(
            ConfirmModal(f"Are you sure you want to delete {selected_item['name']}?"),
            handle_confirm,
        )

    @work
    async def perform_delete(self, key):
        success, error = await asyncio.to_thread(self.s3_client.delete_object, key)
        if success:
            self.notify("Deleted successfully", severity="information")
            self.load_directory(self.current_prefix)
        else:
            self.notify(f"Delete failed: {error}", severity="error")

    @work
    async def action_download(self):
        table = self.query_one(DataTable)
        try:
            row_key = table.coordinate_to_cell_key(
                table.cursor_coordinate
            ).row_key.value
        except:
            self.notify("No item selected", severity="warning")
            return

        selected_item = next(
            (i for i in self.current_items if i["key"] == row_key), None
        )
        if not selected_item or selected_item["type"] == "folder":
            self.notify("Can only download files", severity="warning")
            return

        def handle_input(local_path):
            if local_path:
                self.perform_download(row_key, local_path)

        default_name = selected_item["name"]
        self.push_screen(
            InputModal("Enter destination path:", f"./{default_name}"), handle_input
        )

    @work
    async def perform_download(self, key, local_path):
        self.notify(f"Downloading to {local_path}...")
        success, error = await asyncio.to_thread(
            self.s3_client.download_file, key, local_path
        )
        if success:
            self.notify("Download successful!", severity="information")
        else:
            self.notify(f"Download failed: {error}", severity="error")