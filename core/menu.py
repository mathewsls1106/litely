"""CLI menu for selecting and running registered modules.

The menu reads the ``MODULES`` dictionary from ``core.module_registry`` and
presents a numbered list to the user. The user selects a number (or ``0`` to
exit). The selected module is imported dynamically with ``importlib`` and the
callable ``run`` (or ``main``) entry point is executed.

All errors are caught and displayed, after which the menu is shown again.
"""

from __future__ import annotations

import importlib
import sys
from typing import Callable

from .module_registry import MODULES


def _get_entry_callable(module) -> Callable:
    """Return the entry point callable from a module.

    Preference order:
    1. ``run`` attribute if callable
    2. ``main`` attribute if callable
    Raises ``AttributeError`` if none are found.
    """
    if hasattr(module, "run") and callable(getattr(module, "run")):
        return getattr(module, "run")
    if hasattr(module, "main") and callable(getattr(module, "main")):
        return getattr(module, "main")
    raise AttributeError("No entry point ('run' or 'main') found in module")


def run_menu() -> None:
    """Display the menu loop until the user chooses to exit.

    The function blocks on ``input`` and executes the selected module's entry
    point. Errors are printed to ``stderr`` but do not terminate the menu.
    """
    while True:
        print("\n=== litely CLI Main Menu ===")
        for idx, name in enumerate(MODULES.keys(), start=1):
            print(f"{idx}. {name}")
        print("0. Exit")
        try:
            choice = input("Select an option: ").strip()
        except EOFError:
            # Treat EOF as exit request (e.g., piped input)
            print("\nExiting.")
            break
        if not choice.isdigit():
            print("Invalid selection – please enter a number.")
            continue
        choice_int = int(choice)
        if choice_int == 0:
            print("Good‑bye!")
            break
        if 1 <= choice_int <= len(MODULES):
            name = list(MODULES.keys())[choice_int - 1]
            import_path = MODULES[name]
            try:
                module = importlib.import_module(import_path)
                entry = _get_entry_callable(module)
                entry()
            except Exception as exc:
                print(f"Error loading '{name}': {exc}", file=sys.stderr)
        else:
            print("Selection out of range.")
