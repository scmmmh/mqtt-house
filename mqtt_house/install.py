"""Local installation commands."""

import re
from subprocess import run
from tempfile import NamedTemporaryFile
from typing import Optional

from rich.progress import Progress
from typer import FileBinaryRead, Typer
from yaml import safe_load

from mqtt_house.base import app, console
from mqtt_house.ota import prepare_update
from mqtt_house.settings import ConfigModel

group = Typer(name="setup", help="Set up a locally connected board")
app.add_typer(group)


def get_boards() -> list[tuple[str, str]]:
    """Return a list of boards identified by rshell."""
    boards = []
    result = run(["rshell", "--quiet", "boards"], capture_output=True, check=False)  # noqa: S603, S607
    for line in result.stdout.decode("utf-8").split("\n"):
        match = re.search(r"^([a-zA-Z0-9\-]+)\s*@\s*([a-zA-Z0-9\-/]+)", line)
        if match:
            boards.append((match.group(1), match.group(2)))
    return boards


@group.command()
def boards() -> None:
    """List connected boards."""
    for name, device in get_boards():
        console(f"{name} ({device})")


@group.command()
def install(config_file: FileBinaryRead, board: Optional[str] = None) -> None:
    """Install to a given board."""
    config = ConfigModel(**safe_load(config_file))
    with Progress() as progress:
        task = progress.add_task("Checking for boards", total=None)
        progress.start_task(task)
        target_board = None
        for name, _ in get_boards():
            if not board or board == name:
                target_board = name
                break
        progress.update(task, total=1, completed=1)
        if target_board:
            task = progress.add_task("Clearing old files", total=None)
            result = run(  # noqa:S603
                ["rshell", "--quiet", "ls", "-l", f"/{target_board}"], capture_output=True, check=False  # noqa: S607
            )
            files = result.stdout.decode("utf-8").split("\n")
            progress.update(task, total=len(files))
            for line in files:
                parts = line.strip().split(" ")
                if len(parts) == 5 or len(parts) == 7:  # noqa: PLR2004
                    result = run(  # noqa: S603
                        ["rshell", "--quiet", "rm", "-rf", f"/{target_board}/{parts[-1]}"],  # noqa: S607
                        capture_output=True,
                        check=False,
                    )
                progress.update(task, advance=1)
            _, files = prepare_update(config)
            task = progress.add_task("Copying files", total=len(files))
            for file in files:
                with NamedTemporaryFile("bw", delete_on_close=False) as fp:
                    fp.write(file["data"])
                    fp.close()
                    if "/" in file["filename"]:

                        run(  # noqa:S603
                            [  # noqa:S607
                                "rshell",
                                "--quiet",
                                "mkdir",
                                f"/{target_board}/{'/'.join(file['filename'].split('/')[:-1])}",
                            ],
                            capture_output=True,
                            check=False,
                        )
                    run(  # noqa: S603
                        ["rshell", "--quiet", "cp", fp.name, f"/{target_board}/{file['filename']}"],  # noqa:S607
                        capture_output=True,
                        check=False,
                    )
                progress.update(task, advance=1)
        elif board:
            console(f":x: [red bold]Board {board} not found")
        else:
            console(":x: [red bold]No board found")
