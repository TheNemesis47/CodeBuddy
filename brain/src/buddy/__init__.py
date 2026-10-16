"""CodeBuddy brain: turns code context into tutor answers streamed to the notch."""

__version__ = "0.2.0"


def main() -> None:
    from buddy.cli import main as cli_main

    raise SystemExit(cli_main())
