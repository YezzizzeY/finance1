"""The command table: every registered command resolves to a function, and `finagent --help` lists them all."""
from __future__ import annotations

import importlib

import pytest

from finagent import cli


@pytest.mark.parametrize("name", list(cli.COMMANDS))
def test_command_target_exists(name):
    module, func = cli.COMMANDS[name][0].split(":")
    assert callable(getattr(importlib.import_module(module), func))


def test_help_lists_every_command(capsys):
    assert cli.main(["--help"]) == 0
    out = capsys.readouterr().out
    assert all(f"  {name} " in out for name in cli.COMMANDS)
