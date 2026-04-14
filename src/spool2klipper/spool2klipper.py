#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2025 Sebastian Andersson <sebastian@bittr.nu>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Modularized entry point for the spool2klipper Moonraker agent."""

import argparse
import asyncio
import logging
import os
import sys
import toml
from pathlib import Path
from typing import Any, Dict, Optional, Union

from .api import MoonrakerClient
from .engine import KlipperEngine
from .spoolman_common.api import SpoolmanClient

PROGNAME = "spool2klipper"
CFG_DIR = "~/.config/" + PROGNAME
CFG_FILE = PROGNAME + ".cfg"

logger = logging.getLogger(PROGNAME)

# Global objects
ARGS = None


def load_config(config_dir: Optional[str] = None) -> Dict[str, Any]:
    """Search for and load the TOML configuration file."""
    config_data = None
    search_paths = []
    if config_dir:
        search_paths.append(os.path.join(config_dir, CFG_FILE))
    search_paths.extend(["~/" + CFG_FILE, CFG_DIR + "/" + CFG_FILE, "./" + CFG_FILE])

    for path in search_paths:
        cfg_filename = os.path.expanduser(path)
        if os.path.exists(cfg_filename):
            with open(cfg_filename, "r", encoding="utf-8") as fp:
                config_data = toml.load(fp)
                logger.debug(f"Loaded config from {cfg_filename}")
                break

    if not config_data:
        logger.error(f"Configuration file {CFG_FILE} not found.")
        sys.exit(1)

    return config_data


class Spool2Klipper:
    """Consolidated Spool2Klipper application for use as a standalone or plugin."""

    def __init__(self, config: Optional[Union[str, Dict[str, Any]]] = None):
        if isinstance(config, dict):
            self.config = config.get(PROGNAME, config)
        else:
            self.config = load_config(config).get(PROGNAME, {})
            
        self.moonraker: Optional[MoonrakerClient] = None
        self.spoolman: Optional[SpoolmanClient] = None
        self.engine: Optional[KlipperEngine] = None

    async def initialize(self):
        """Build the clients and engine."""
        self.moonraker = MoonrakerClient(
            self.config.get("moonraker_url", "ws://localhost:7125/websocket")
        )
        self.spoolman = SpoolmanClient(
            self.config.get("spoolman_url", "http://localhost:8000")
            .rstrip("/api")
            .rstrip("/")
        )

        self.engine = KlipperEngine(
            moonraker=self.moonraker,
            spoolman=self.spoolman,
            macro_prefix=self.config.get(
                "klipper_spool_set_macro_prefix", "_SPOOLMAN_SET_FIELD_"
            ),
            clear_macro=self.config.get(
                "klipper_spool_clear_macro", "_SPOOLMAN_CLEAR_SPOOL"
            ),
            done_macro=self.config.get("klipper_spool_done", "_SPOOLMAN_DONE"),
        )
        await self.engine.initialize()

    async def run(self):
        """Start the synchronization loop."""
        if not self.engine:
            await self.initialize()
        await self.engine.run_forever()

    async def stop(self):
        """Clean up connections."""
        if self.moonraker:
            await self.moonraker.close()


def get_parser() -> argparse.ArgumentParser:
    """Initialize the argument parser."""
    parser = argparse.ArgumentParser(
        prog=PROGNAME,
        description="Monitoring Spoolman events and updating Moonraker/Klipper.",
    )
    parser.add_argument(
        "-u", "--url",
        metavar="URL",
        default=os.environ.get("SM2S_SPOOLMAN_URL", os.environ.get("SPOOLMAN_URL", "http://localhost:8000")),
        help="The web address of your Spoolman server.",
    )
    parser.add_argument(
        "-c", "--config",
        metavar="FILE",
        help="Path to the configuration file.",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show detailed progress and error information.",
    )
    return parser

async def main_async():
    """Main asynchronous execution logic."""
    global ARGS
    parser = get_parser()
    ARGS = parser.parse_args()
    
    config = load_config(ARGS.config)
    app = Spool2Klipper(config)

    # Set log level based on verbose flag
    if ARGS.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        await app.initialize()
        await app.run()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.exception(f"Fatal error in execution loop: {e}")
    finally:
        await app.stop()


def main():
    """Synchronous entry point."""
    log_level = logging.INFO
    logging.basicConfig(
        level=log_level, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
