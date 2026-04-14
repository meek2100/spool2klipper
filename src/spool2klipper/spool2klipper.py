#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2025 Sebastian Andersson <sebastian@bittr.nu>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Modularized entry point for the spool2klipper Moonraker agent."""

import asyncio
import logging
import os
import sys
import toml
from pathlib import Path
from typing import Any, Dict, Optional

from .api import MoonrakerClient
from .engine import KlipperEngine
from .spoolman_common.api import SpoolmanClient

PROGNAME = "spool2klipper"
CFG_DIR = "~/.config/" + PROGNAME
CFG_FILE = PROGNAME + ".cfg"

logger = logging.getLogger(PROGNAME)

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

    def __init__(self, config: Dict[str, Any]):
        self.config = config.get(PROGNAME, {})
        self.moonraker: Optional[MoonrakerClient] = None
        self.spoolman: Optional[SpoolmanClient] = None
        self.engine: Optional[KlipperEngine] = None

    async def initialize(self):
        """Build the clients and engine."""
        self.moonraker = MoonrakerClient(self.config.get("moonraker_url", "ws://localhost:7125/websocket"))
        self.spoolman = SpoolmanClient(self.config.get("spoolman_url", "http://localhost:7912").rstrip("/api").rstrip("/"))
        
        self.engine = KlipperEngine(
            moonraker=self.moonraker,
            spoolman=self.spoolman,
            macro_prefix=self.config.get("klipper_spool_set_macro_prefix", "_SPOOLMAN_SET_FIELD_"),
            clear_macro=self.config.get("klipper_spool_clear_macro", "_SPOOLMAN_CLEAR_SPOOL"),
            done_macro=self.config.get("klipper_spool_done", "_SPOOLMAN_DONE")
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

async def main_async():
    """Main asynchronous execution logic."""
    config = load_config()
    app = Spool2Klipper(config)
    
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
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    asyncio.run(main_async())

if __name__ == "__main__":
    main()
