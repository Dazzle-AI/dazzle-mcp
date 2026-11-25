"""Smoke tests for the thin `dazzle` entry point. The interesting logic lives in proxy.py."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from dazzle_photo_intelligence import cli


def test_version_flag_exits_zero(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["--version"])
    assert exc.value.code == 0
    assert "dazzle" in capsys.readouterr().out


def test_no_args_invokes_proxy_main():
    with patch("dazzle_photo_intelligence.cli.proxy.main") as mock_main:
        rc = cli.main([])
    assert rc == 0
    mock_main.assert_called_once_with()
