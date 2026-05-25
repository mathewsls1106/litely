---
name: main-page-modular-cli
description: Design and implement a CLI main menu that dynamically loads TUI modules and fixes missing entry points.
metadata:
  type: plan
---

# Context
The project currently has a simple `main.py` and a `s3_tui` package lacking a proper entry point. We need a CLI main menu that lists available modules (e.g., S3 Browser) and launches the selected module. The solution must be extensible for future modules and include fixing the missing `run` entry point for `s3_tui`.

# Objectives
- Create a module registry for mapping menu names to module entry points.
- Implement a reusable CLI menu that dynamically imports and runs selected modules.
- Add a `run()` function to `s3_tui/main.py` that launches `S3BrowserApp`.
- Update `main.py` to start the new menu.
- Ensure the system is extensible for future TUI modules.
- Verify functionality and pass all tests.

# Files Affected
- `/home/pc3/Escritorio/practicas/litely/core/module_registry.py` (new)
- `/home pc3/Escritorio/practicas/litely/core/menu.py` (new)
- `/home/pc3/Escritorio/practicas/litely/main.py` (modify)
- `/home/pc3/Escritorio/practicas/litely/s3_tui/main.py` (modify to add `run`)
- Optionally `/home/pc3/Escritorio/practicas/litely/README.md` (update usage notes)

# Technical Steps
1. **Create core package**
   - Add `core/__init__.py` (empty) to make it a package.
2. **Create module_registry.py**
   ```python
   # core/module_registry.py
   MODULES = {
       "S3 Browser": "s3_tui.main",
       # Add future modules here, e.g., "CloudWatch": "cloudwatch_tui.main"
   }
   ```
3. **Create menu.py**
   ```python
   # core/menu.py
   import importlib
   from .module_registry import MODULES

   def run_menu() -> None:
       while True:
           print("\nAvailable modules:")
           for idx, name in enumerate(MODULES, start=1):
               print(f"{idx}. {name}")
           print("0. Exit")
           choice = input("Select a module: ")
           if choice == "0":
               print("Exiting.")
               break
           try:
               idx = int(choice) - 1
               module_name = list(MODULES.values())[idx]
           except (ValueError, IndexError):
               print("Invalid selection, try again.")
               continue
           try:
               mod = importlib.import_module(module_name)
               entry = getattr(mod, "run", None) or getattr(mod, "main", None)
               if not entry:
                   print(f"Module {module_name} has no run() or main() function.")
                   continue
               entry()
           except Exception as e:
               print(f"Error loading module {module_name}: {e}")
   ```
4. **Update main.py**
   Replace existing greeting with:
   ```python
   from core.menu import run_menu

   if __name__ == "__main__":
       run_menu()
   ```
5. **Add run() to s3_tui/main.py**
   ```python
   from .app import S3BrowserApp

   def run() -> None:
       """Launch the S3 browser TUI application."""
       S3BrowserApp().run()
   ```
6. **(Optional) Update README.md** with brief usage instructions.
7. **Testing / Verification**
   - Execute `python main.py`; menu should list "S3 Browser".
   - Selecting option `1` starts the S3 TUI without errors.
   - Removing `run` should produce a clear error message.
   - Add a dummy entry to `module_registry.py` and confirm menu updates.
   - Run existing unit tests to ensure no regressions.

# Acceptance Criteria
- [ ] `s3_tui/main.py` contains a public `run()` that launches `S3BrowserApp`.
- [ ] `core/module_registry.py` maps "S3 Browser" to `s3_tui.main`.
- [ ] `core/menu.py` provides a functional CLI menu loop.
- [ ] `main.py` starts the menu when executed.
- [ ] Selecting the listed option launches the S3 TUI successfully.
- [ ] Adding new modules only requires updating `module_registry.py`.
- [ ] No runtime errors occur during menu operation.
- [ ] All existing tests pass.

---
*Plan includes fixing the missing entry point for the S3 Browser module and implementing the CLI main menu.*