"""Entry point for conecte_tunnels package."""

from .app import ConecteApp

def main() -> None:
    ConecteApp().run()

if __name__ == "__main__":
    main()
