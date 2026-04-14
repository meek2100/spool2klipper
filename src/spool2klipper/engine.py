# SPDX-FileCopyrightText: 2025 Sebastian Andersson <sebastian@bittr.nu>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Orchestration logic for syncing Spoolman data to Klipper."""

import logging
from typing import Any, Dict, List, Optional, Union
from .api import MoonrakerClient
from .spoolman_common.api import SpoolmanClient

logger = logging.getLogger(__name__)

class KlipperEngine:
    """Orchestrates the data flow between Moonraker and Spoolman."""

    def __init__(
        self,
        moonraker: MoonrakerClient,
        spoolman: SpoolmanClient,
        macro_prefix: str = "_SPOOLMAN_SET_FIELD_",
        clear_macro: str = "_SPOOLMAN_CLEAR_SPOOL",
        done_macro: str = "_SPOOLMAN_DONE"
    ):
        self.moonraker = moonraker
        self.spoolman = spoolman
        self.macro_prefix = macro_prefix
        self.clear_macro = clear_macro
        self.done_macro = done_macro
        
        self.available_macros: List[str] = []

    async def initialize(self):
        """Perform initial setup and macro discovery."""
        await self.moonraker.connect()
        self.available_macros = await self.moonraker.get_macros()
        logger.debug(f"Discovered {len(self.available_macros)} Klipper macros")
        
        # Subscribe to spool changes
        self.moonraker.subscribe_active_spool(self._handle_active_spool_set)

    async def _handle_active_spool_set(self, params: Dict[str, Any]):
        """Callback for Moonraker's active_spool_set notification."""
        spool_id = params.get("spool_id")
        logger.info(f"Received active_spool_set: id={spool_id}")

        if spool_id is not None:
            try:
                spool_data = self.spoolman.get_spool(int(spool_id))
                if not spool_data:
                    logger.warning(f"Spool ID {spool_id} not found in Spoolman, clearing Klipper.")
                    await self._clear_klipper()
                    return

                logger.info(f"Fetched data for spool {spool_id}, syncing to Klipper...")
                await self._clear_klipper() # Clear old values first
                await self._sync_data_to_macros(self.macro_prefix, spool_data)
                
                if self.done_macro in self.available_macros:
                    await self.moonraker.run_gcode(self.done_macro)

            except Exception as e:
                logger.error(f"Failed to sync spool {spool_id} to Klipper: {e}")
        else:
            logger.info("Spool cleared in Moonraker, clearing Klipper.")
            await self._clear_klipper()

    async def _clear_klipper(self):
        """Execute the clear macro to reset spool fields."""
        if self.clear_macro in self.available_macros:
            await self.moonraker.run_gcode(self.clear_macro)
        else:
            logger.debug("No clear macro found in Klipper, skipping reset.")

    async def _sync_data_to_macros(self, prefix: str, data: Any):
        """Recursively map dictionary keys to Klipper G-code macros."""
        if not isinstance(data, dict):
            return

        for key, val in data.items():
            macro_name = prefix + key
            if isinstance(val, dict):
                # Recursively handle nested fields (e.g., filament.name -> _SPOOLMAN_SET_FIELD_filament_name)
                await self._sync_data_to_macros(macro_name + "_", val)
            elif isinstance(val, list):
                # We typically don't map lists to macros directly
                continue
            elif macro_name in self.available_macros:
                # Build the gcode script
                if isinstance(val, (int, float)):
                    script = f"{macro_name} VALUE={val}"
                else:
                    # Sanitize string values
                    safe_val = str(val).replace('"', "''")
                    script = f'{macro_name} VALUE="{safe_val}"'
                
                await self.moonraker.run_gcode(script)

    async def run_forever(self):
        """Keep the engine alive and monitoring."""
        # Moonraker connection is already established and async.
        # We just need to prevent the process from exiting.
        import asyncio
        while True:
            await asyncio.sleep(3600)
