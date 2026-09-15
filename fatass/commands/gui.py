import argparse

from .base import Command


class GuiCommand(Command):
    name = "gui"
    help = "start a local web GUI (FastAPI server wrapping a fatass shell) at http://<host>:<port>/"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--host", default="127.0.0.1", help="bind host (default: 127.0.0.1)")
        parser.add_argument("--port", type=int, default=8756, help="bind port (default: 8756)")

    def run(self, args: argparse.Namespace) -> int:
        import uvicorn

        from ..gui.server import app

        print(f"fatass gui: http://{args.host}:{args.port}/")
        uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
        return 0
