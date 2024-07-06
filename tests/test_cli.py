"""Test the basic CLI functionality."""

from typer.testing import CliRunner

from mqtt_house.__about__ import __version__
from mqtt_house.cli import app

runner = CliRunner()


def test_no_command_fails():
    """Test that running with no command fails."""
    result = runner.invoke(app, [])
    assert result.exit_code == 2


def test_version():
    """Test that running the version command returns the current version."""
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout
