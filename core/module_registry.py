"""Registry of available CLI modules.

Each entry maps a human readable name to the import path of a module that
exposes a callable entry point. The entry point is expected to be a function
named ``run``; if such a function does not exist the menu will try to call a
``main`` function as a fallback.
"""

from typing import Dict

MODULES: Dict[str, str] = {
    "S3 Browser": "s3_tui.main",
    # Add future modules here, e.g. "CloudWatch": "cloudwatch_tui.main"
    "SSM Tunnel Manager": "conecte_tunnels.__main__",
}


def register(name: str, import_path: str) -> None:
    """Register a new module at runtime.

    This helper allows modules to register themselves via import side‑effects
    without editing this file manually.
    """
    MODULES[name] = import_path
