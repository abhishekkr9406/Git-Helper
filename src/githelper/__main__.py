"""Application entry point. Contains no logic - launches the app."""

import sys


def main() -> int:
    """Launch GitHelper application."""
    from githelper.app.orchestrator import Orchestrator

    app = Orchestrator()
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
