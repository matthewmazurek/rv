import types

import pytest


@pytest.fixture()
def init_args(tmp_path):
    """Return a default args namespace for cmd_init pointing at tmp_path."""
    return types.SimpleNamespace(
        name=str(tmp_path / "myproject"),
        git=False,
        renv=True,
        rproj=False,
        slurm=False,
        force=False,
        sync=False,
    )


RV_CONFIG_CONTENT = """\
renv = true
packages = ["dplyr", "ggplot2@3.4.0", "tidyr"]
"""
