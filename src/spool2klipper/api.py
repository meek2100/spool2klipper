# SPDX-FileCopyrightText: 2025 Sebastian Andersson <sebastian@bittr.nu>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Moonraker API client for Klipper communication."""

import logging
from typing import Any, Dict, List, Optional
from jsonrpc_websocket import Server

logger = logging.getLogger(__name__)

class MoonrakerClient:
    """Stateful client for the Moonraker JSON-RPC WebSocket API."""

    def __init__(self, url: str):
        self.url = url
        self._server: Optional[Server] = None

    async def connect(self):
        """Establish the WebSocket connection to Moonraker."""
        self._server = Server(self.url)
        await self._server.ws_connect()
        logger.info(f"Connected to Moonraker at {self.url}")

    async def close(self):
        """Close the WebSocket connection."""
        if self._server:
            await self._server.close()
            logger.info("Closed Moonraker connection")

    async def get_macros(self) -> List[str]:
        """Fetch the list of available G-code macros from Klipper."""
        if not self._server:
            raise RuntimeError("Moonraker client not connected")
        
        objects = await self._server.printer.objects.list()
        macros = [
            x[12:] for x in objects.get("objects", []) if x.startswith("gcode_macro ")
        ]
        return macros

    async def run_gcode(self, script: str):
        """Execute a G-code script in Klipper."""
        if not self._server:
            raise RuntimeError("Moonraker client not connected")
        
        logger.info(f"Executing G-code: '{script}'")
        await self._server.printer.gcode.script(script=script, _notification=True)

    def subscribe_active_spool(self, callback):
        """Subscribe to active spool change notifications."""
        if not self._server:
            raise RuntimeError("Moonraker client not connected")
        
        self._server.notify_active_spool_set = callback

    async def wait_until_closed(self):
        """Wait for the connection to be closed or handle long-running tasks."""
        # This is a placeholder for any background task management needed
        pass
