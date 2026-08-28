from src.settings._jobs import JobParams


def test_job_params_truthiness_is_false_by_default():
    assert not JobParams()


def test_job_params_truthiness_reflects_enabled_flag():
    assert JobParams(enabled=True)
    assert not JobParams(enabled=False)


def _jobs(config):
    from unittest.mock import MagicMock

    from src.settings._jobs import Jobs

    settings = MagicMock()
    settings.general.obsolete_tag = "Obsolete"
    return Jobs(config, settings)


def test_remove_stalled_min_days_stalled_defaults_to_zero():
    """The bare `remove_stalled:` YAML form keeps the job defaults."""
    jobs = _jobs({"jobs": {"remove_stalled": None}})

    assert jobs.remove_stalled.min_days_stalled == 0


def test_remove_stalled_min_days_stalled_read_from_job_config():
    jobs = _jobs({"jobs": {"remove_stalled": {"min_days_stalled": 7}}})

    assert jobs.remove_stalled.min_days_stalled == 7
