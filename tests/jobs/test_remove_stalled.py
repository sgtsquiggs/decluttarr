import pytest

from src.jobs.remove_stalled import RemoveStalled
from tests.jobs.utils import shared_fix_affected_items, shared_test_affected_items


# Test to check if items with the specific error message are included in affected items with parameterized data
@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("queue_data", "expected_download_ids"),
    [
        (
            [
                {
                    "downloadId": "1",
                    "status": "warning",
                    "errorMessage": "The download is stalled with no connections",
                },  # Valid item
                {
                    "downloadId": "2",
                    "status": "completed",
                    "errorMessage": "The download is stalled with no connections",
                },  # Wrong status
                {
                    "downloadId": "3",
                    "status": "warning",
                    "errorMessage": "Some other error",
                },  # Incorrect errorMessage
            ],
            [
                "1"
            ],  # Only the item with "warning" status and the correct errorMessage should be affected
        ),
        (
            [
                {
                    "downloadId": "1",
                    "status": "warning",
                    "errorMessage": "Some other error",
                },  # Incorrect errorMessage
                {
                    "downloadId": "2",
                    "status": "completed",
                    "errorMessage": "The download is stalled with no connections",
                },  # Wrong status
                {
                    "downloadId": "3",
                    "status": "warning",
                    "errorMessage": "The download is stalled with no connections",
                },  # Correct item
            ],
            [
                "3"
            ],  # Only the item with "warning" status and the correct errorMessage should be affected
        ),
        (
            [
                {
                    "downloadId": "1",
                    "status": "warning",
                    "errorMessage": "The download is stalled with no connections",
                },  # Valid item
                {
                    "downloadId": "2",
                    "status": "warning",
                    "errorMessage": "The download is stalled with no connections",
                },  # Another valid item
            ],
            ["1", "2"],  # Both items match the condition
        ),
        (
            [
                {
                    "downloadId": "1",
                    "status": "completed",
                    "errorMessage": "The download is stalled with no connections",
                },  # Wrong status
                {
                    "downloadId": "2",
                    "status": "warning",
                    "errorMessage": "Some other error",
                },  # Incorrect errorMessage
            ],
            [],  # No items match the condition
        ),
    ],
)
async def test_find_affected_items(queue_data, expected_download_ids):
    # Arrange
    removal_job = shared_fix_affected_items(RemoveStalled, queue_data)

    # Act and Assert
    await shared_test_affected_items(removal_job, expected_download_ids)


def _stalled_job(min_days_stalled, qbit_items, queue):
    """RemoveStalled wired to a single qbit client returning the given torrents."""
    from unittest.mock import AsyncMock, MagicMock

    from src.utils.queue_manager import QueueManager

    job = RemoveStalled.__new__(RemoveStalled)
    job.arr = MagicMock()
    job.job_name = "remove_stalled"
    job.queue = queue

    qbit = AsyncMock()
    qbit.ready = True
    qbit.get_qbit_items.return_value = qbit_items

    settings = MagicMock()
    settings.download_clients.qbittorrent = [qbit]
    settings.jobs.remove_stalled.min_days_stalled = min_days_stalled
    job.settings = settings
    job.job = settings.jobs.remove_stalled
    job.queue_manager = QueueManager(job.arr, settings)
    return job


def _stalled_row(download_id):
    return {
        "downloadId": download_id,
        "status": "warning",
        "errorMessage": "The download is stalled with no connections",
    }


@pytest.mark.asyncio
async def test_min_days_stalled_keeps_recently_active_downloads():
    """A torrent that moved data yesterday has not been stalled for a week."""
    import time

    job = _stalled_job(
        7,
        [{"hash": "AAA", "last_activity": time.time() - 86400}],
        [_stalled_row("AAA")],
    )

    assert await job._find_affected_items() == []


@pytest.mark.asyncio
async def test_min_days_stalled_allows_long_stalled_downloads():
    """A torrent inactive longer than the threshold is still eligible for removal."""
    import time

    job = _stalled_job(
        7,
        [{"hash": "AAA", "last_activity": time.time() - (30 * 86400)}],
        [_stalled_row("AAA")],
    )

    affected = await job._find_affected_items()

    assert [item["downloadId"] for item in affected] == ["AAA"]


@pytest.mark.asyncio
async def test_min_days_stalled_disabled_by_default_keeps_all():
    """min_days_stalled=0 preserves the pre-existing behaviour."""
    import time

    job = _stalled_job(
        0, [{"hash": "AAA", "last_activity": time.time()}], [_stalled_row("AAA")]
    )

    affected = await job._find_affected_items()

    assert [item["downloadId"] for item in affected] == ["AAA"]


@pytest.mark.asyncio
async def test_min_days_stalled_keeps_download_missing_from_the_client():
    """A download the client knows nothing about must not be silently spared."""
    job = _stalled_job(7, [], [_stalled_row("AAA")])

    affected = await job._find_affected_items()

    assert [item["downloadId"] for item in affected] == ["AAA"]
