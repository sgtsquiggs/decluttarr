"""Removes stalled downloads."""

import time

from src.jobs.removal_job import RemovalJob
from src.utils.log_setup import logger

SECONDS_PER_DAY = 86400


class RemoveStalled(RemovalJob):
    queue_scope = "normal"
    blocklist = True

    async def _find_affected_items(self):
        conditions = [("warning", "The download is stalled with no connections")]
        affected_items = self.queue_manager.filter_queue(self.queue, conditions)
        return await self._filter_by_min_days_stalled(affected_items)

    async def _filter_by_min_days_stalled(self, affected_items):
        """
        Drop items that have not been stalled long enough yet.

        A download counts as stalled since qBittorrent last recorded activity on it
        ('last_activity'). Unlike the strike counter this survives a restart of
        decluttarr, because it is read from the download client rather than held in
        memory. Downloads the client does not know about are left untouched, so a
        missing torrent never silently spares an item.
        """
        min_days = getattr(self.job, "min_days_stalled", 0) or 0
        if not min_days or not affected_items:
            return affected_items

        cutoff = time.time() - (min_days * SECONDS_PER_DAY)
        last_activity = await self._get_last_activity(
            [item["downloadId"] for item in affected_items]
        )

        kept = []
        for item in affected_items:
            activity = last_activity.get(item["downloadId"].upper())
            if activity is not None and activity > cutoff:
                logger.debug(
                    f"remove_stalled.py/_filter_by_min_days_stalled: Keeping "
                    f"{item.get('title')} - last active "
                    f"{(time.time() - activity) / SECONDS_PER_DAY:.1f} days ago, "
                    f"which is below min_days_stalled of {min_days}"
                )
                continue
            kept.append(item)

        return kept

    async def _get_last_activity(self, download_ids):
        """Map of upper-cased torrent hash to its qBittorrent last_activity."""
        last_activity = {}
        for qbit in self.settings.download_clients.qbittorrent:
            if not qbit.ready:
                continue
            for item in await qbit.get_qbit_items(hashes=download_ids):
                last_activity[item["hash"].upper()] = item.get("last_activity")
        return last_activity
