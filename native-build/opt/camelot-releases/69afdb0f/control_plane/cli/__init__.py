# SPDX-License-Identifier: MIT

"""Camelot-OS modular CLI package.

Splits the monolithic ``camelot_cli.py`` into focused modules while preserving
full backward compatibility.  The original ``control_plane.camelot_cli`` module
now re-exports everything from here.
"""

from control_plane.cli.dispatch import main as main  # noqa: F401
