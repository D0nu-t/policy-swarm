"""Launch the dashboard: ``python -m policyswarm.gui [--port 8000] [--runs-dir runs]``."""

from __future__ import annotations

import argparse

import uvicorn

from ..suggest import DEFAULT_CHECKPOINT
from .server import create_app


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m policyswarm.gui",
                                     description="PolicySwarm experiment dashboard")
    parser.add_argument("--host", default="127.0.0.1",
                        help="Interface to bind. The default is loopback only; the "
                             "dashboard has no authentication, so do not expose it.")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--runs-dir", default="runs",
                        help="Directory that receives one sub-folder per run (default: runs).")
    parser.add_argument("--decider-checkpoint", default=DEFAULT_CHECKPOINT,
                        help="Laya model used by \"Suggest keyword rules\": a model id or the "
                             "folder of a fine-tuned checkpoint (default: the stock model).")
    args = parser.parse_args()

    print(f"PolicySwarm dashboard: http://{args.host}:{args.port}  (runs -> {args.runs_dir}/)")
    uvicorn.run(create_app(args.runs_dir, args.decider_checkpoint), host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
