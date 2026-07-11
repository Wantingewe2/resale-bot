from __future__ import annotations

import argparse
import logging
import sys

from bot.config import load_settings
from bot.scheduler import run_forever


def setup_logging(level: str, log_file: str) -> None:
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    handlers = [logging.StreamHandler(sys.stdout)]
    if log_file:
        handlers.append(logging.FileHandler(log_file))
    logging.basicConfig(level=level, format=fmt, handlers=handlers)


def main() -> None:
    parser = argparse.ArgumentParser(description="Cross-platform resale listing monitor")
    parser.add_argument(
        "--config", default="config.yaml", help="Path to config.yaml (default: ./config.yaml)"
    )
    args = parser.parse_args()

    settings = load_settings(args.config)
    setup_logging(settings.log_level, settings.log_file)

    try:
        run_forever(settings)
    except KeyboardInterrupt:
        logging.getLogger("main").info("Stopped by user.")


if __name__ == "__main__":
    main()
