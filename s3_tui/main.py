#!/usr/bin/env python3
'''Vertical 4: Punto de entrada - Inicialización de la aplicación'''

import os
import sys

# Support both running as a module (python -m s3_tui.main) and directly (python s3_tui/main.py)
if __package__ is None:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from s3_tui.app import S3BrowserApp
else:
    from .app import S3BrowserApp


def run() -> None:
    """Public entry point used by the modular CLI menu to launch the S3 Browser TUI."""
    # Ensure required environment variable is set before launching
    if not os.environ.get("DJANGO_AWS_STORAGE_BUCKET_NAME"):
        print("Error: DJANGO_AWS_STORAGE_BUCKET_NAME environment variable not set")
        print("Configure SSM parameter /s3_tui/django_aws_storage_bucket_name or set DJANGO_AWS_STORAGE_BUCKET_NAME env var")
        sys.exit(1)
    app = S3BrowserApp()
    app.run()


if __name__ == "__main__":
    run()
