#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2025 Sebastian Andersson <sebastian@bittr.nu>
# SPDX-License-Identifier: GPL-3.0-or-later

"""
Moonraker agent to send Spoolman's spool info to Klipper

It listens for active_spool_set events from moonraker,
that will cause it to lookup the new spool's data
and for every field, if there exists a gcode macro
with the right name in Klipper, it will invoke it
with the field's value.
"""

import asyncio
import logging
import os
import shutil
import sys
import argparse
from typing import Any, Dict, List, Optional, Union
from pathlib import Path

import aiohttp
from jsonrpc_websocket import Server
import toml

PROGNAME = "spool2klipper"
DEFAULT_CFG_DIR = os.path.expanduser("~/.config/" + PROGNAME)
DEFAULT_CFG_FILE = PROGNAME + ".cfg"


class Spool2Klipper:
    """Moonraker agent to send Spoolman's spool info to Klipper"""

    def __init__(
        self,
        moonraker_url: str,
        spoolman_url: str,
        klipper_spool_set_macro_prefix: str = "_SPOOLMAN_SET_FIELD_",
        klipper_spool_clear_macro: str = "_SPOOLMAN_CLEAR_SPOOL",
        klipper_spool_done: str = "_SPOOLMAN_DONE",
    ):
        self.gcode_macros: List[str] = []
        self.http_session: Optional[aiohttp.ClientSession] = None
        self.moonraker_server: Optional[Server] = None
        self.moonraker_url = moonraker_url
        self.spoolman_url = spoolman_url
        self.klipper_spool_set_macro_prefix = klipper_spool_set_macro_prefix
        self.klipper_spool_clear_macro = klipper_spool_clear_macro
        self.klipper_spool_done = klipper_spool_done

    async def _fetch_spool_info(
        self, spool_id: Union[int, None]
    ) -> Optional[Union[Dict[str, Any], Exception]]:
        try:
            async with self.http_session.get(
                f"{self.spoolman_url}/v1/spool/{spool_id}",
            ) as response:
                if response.status == 404:
                    return None
                if response.status == 200:
                    return await response.json()
                return Exception(await response.text())
        except aiohttp.client_exceptions.ClientConnectorError as e:
            return e

    async def _get_response_error(self, response: Exception) -> str:
        if isinstance(response, aiohttp.client_exceptions.ClientConnectorError):
            err_msg = f"Failed to connect to server: {response}"
        else:
            err_msg = f"Unknown error: {response}"
        return err_msg

    def _has_spoolman_set_macros(self) -> bool:
        prefix = self.klipper_spool_set_macro_prefix
        for k in self.gcode_macros:
            if k.startswith(prefix):
                return True
        return False

    async def _notify_active_spool_set(self, params: Dict[str, Any]) -> None:
        spool_id = params.get("spool_id")
        if spool_id is not None:
            if self._has_spoolman_set_macros():
                logging.debug("Fetching data from Spoolman id=%s", spool_id)
                spool_data = await self._fetch_spool_info(spool_id)
                if spool_data is None:
                    logging.info("Spool ID %s not found, clearing fields", spool_id)
                    await self._run_gcode(self.klipper_spool_clear_macro)
                elif isinstance(spool_data, Exception):
                    err_msg = await self._get_response_error(spool_data)
                    logging.info("Attempt to fetch spool info failed: %s", err_msg)
                else:
                    logging.info("Fetched Spool data for ID %s", spool_id)
                    logging.debug("Got data from Spoolman: %s", spool_data)
                    await self._run_gcode(self.klipper_spool_clear_macro)
                    await self._call_klipper_with_data(
                        self.klipper_spool_set_macro_prefix,
                        spool_data,
                    )

                    if self.klipper_spool_done in self.gcode_macros:
                        await self._run_gcode(self.klipper_spool_done)
            else:
                logging.debug("No spoolman gcode set macros found")
        else:
            if self.klipper_spool_clear_macro in self.gcode_macros:
                await self._run_gcode(self.klipper_spool_clear_macro)
            else:
                logging.debug("No spoolman gcode clear macro found")

    async def _call_klipper_with_data(
        self,
        prefix: str,
        spool_data: Any,
    ) -> None:
        for key, val in spool_data.items():
            macro_name = prefix + key
            if isinstance(val, dict):
                await self._call_klipper_with_data(macro_name + "_", val)
            elif macro_name in self.gcode_macros:
                if isinstance(val, (int, float)):
                    script = f"{macro_name} VALUE={val}"
                else:
                    val = str(val).replace('"', "''")
                    script = f'{macro_name} VALUE="{val}"'
                await self._run_gcode(script)

    async def _run_gcode(self, script):
        logging.info("Run in klipper: '%s'", script)
        await self.moonraker_server.printer.gcode.script(
            script=script, _notification=True
        )

    async def _routine(self):
        async with aiohttp.ClientSession() as self.http_session:
            self.moonraker_server = Server(self.moonraker_url)
            try:
                await self.moonraker_server.ws_connect()

                objects = await self.moonraker_server.printer.objects.list()
                self.gcode_macros = [
                    x[12:] for x in objects["objects"] if x.startswith("gcode_macro ")
                ]
                logging.debug("Available macros: %s", self.gcode_macros)

                self.moonraker_server.notify_active_spool_set = (
                    self._notify_active_spool_set
                )

                while True:
                    await asyncio.sleep(3600)
            finally:
                if self.moonraker_server:
                    await self.moonraker_server.close()

    def run(self):
        """Run the agent in the async loop"""
        loop = asyncio.get_event_loop()
        try:
            loop.run_until_complete(self._routine())
        except KeyboardInterrupt:
            logging.info("Interrupted by user")


def load_config(args):
    """Load configuration from env vars, config file, or defaults."""
    config = {
        "moonraker_url": os.getenv(
            "S2K_MOONRAKER_URL", "ws://localhost:7125/websocket"
        ),
        "spoolman_url": os.getenv("S2K_SPOOLMAN_URL", "http://localhost:8000/api"),
        "klipper_spool_set_macro_prefix": os.getenv(
            "S2K_SET_MACRO_PREFIX", "_SPOOLMAN_SET_FIELD_"
        ),
        "klipper_spool_clear_macro": os.getenv(
            "S2K_CLEAR_MACRO", "_SPOOLMAN_CLEAR_SPOOL"
        ),
        "klipper_spool_done": os.getenv("S2K_DONE_MACRO", "_SPOOLMAN_DONE"),
    }

    # Load from config file if specified or found in default locations
    cfg_file = args.config
    config_data = None

    search_paths = []
    if cfg_file:
        search_paths.append(cfg_file)
    else:
        search_paths.extend(
            [
                os.path.join(os.path.expanduser("~"), DEFAULT_CFG_FILE),
                os.path.join(DEFAULT_CFG_DIR, DEFAULT_CFG_FILE),
            ]
        )

    for path in search_paths:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as fp:
                    file_data = toml.load(fp)
                    if PROGNAME in file_data:
                        config_data = file_data[PROGNAME]
                        logging.info("Loaded config from %s", path)
                        break
            except Exception as e:
                logging.warning("Failed to load config from %s: %s", path, e)

    if config_data:
        # Override with file data only if env vars are NOT set
        for key in config:
            env_key = f"S2K_{key.upper()}".replace("KLIPPER_SPOOL_", "").replace(
                "_MACRO", ""
            )
            # This is a bit complex, let's just do it directly for simplicity
            pass

        # Simpler: Config file overrides defaults, but Env Vars override everything.
        if "moonraker_url" in config_data and not os.getenv("S2K_MOONRAKER_URL"):
            config["moonraker_url"] = config_data["moonraker_url"]
        if "spoolman_url" in config_data and not os.getenv("S2K_SPOOLMAN_URL"):
            config["spoolman_url"] = config_data["spoolman_url"]
        if "klipper_spool_set_macro_prefix" in config_data and not os.getenv(
            "S2K_SET_MACRO_PREFIX"
        ):
            config["klipper_spool_set_macro_prefix"] = config_data[
                "klipper_spool_set_macro_prefix"
            ]
        if "klipper_spool_clear_macro" in config_data and not os.getenv(
            "S2K_CLEAR_MACRO"
        ):
            config["klipper_spool_clear_macro"] = config_data[
                "klipper_spool_clear_macro"
            ]
        if "klipper_spool_done" in config_data and not os.getenv("S2K_DONE_MACRO"):
            config["klipper_spool_done"] = config_data["klipper_spool_done"]

    return config


def main():
    parser = argparse.ArgumentParser(description="Moonraker agent for Spoolman")
    parser.add_argument("-c", "--config", help="Path to config file")
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose logging"
    )
    args = parser.parse_args()

    log_level = (
        logging.DEBUG if args.verbose or os.getenv("S2K_DEBUG") else logging.INFO
    )
    logging.basicConfig(
        level=log_level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    config = load_config(args)

    agent = Spool2Klipper(
        moonraker_url=config["moonraker_url"],
        spoolman_url=config["spoolman_url"],
        klipper_spool_set_macro_prefix=config["klipper_spool_set_macro_prefix"],
        klipper_spool_clear_macro=config["klipper_spool_clear_macro"],
        klipper_spool_done=config["klipper_spool_done"],
    )
    agent.run()


if __name__ == "__main__":
    main()
