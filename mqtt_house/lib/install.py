"""Local installation commands."""

import re
from subprocess import run
from tempfile import NamedTemporaryFile
from typing import Optional

from rich import print as console
from rich.progress import Progress

from mqtt_house.lib.ota import prepare_update
from mqtt_house.settings import ConfigModel


def get_boards() -> list[tuple[str, str]]:
    """Return a list of boards identified by rshell."""
    boards = []
    result = run(["rshell", "--quiet", "boards"], capture_output=True, check=False)  # noqa: S603, S607
    for line in result.stdout.decode("utf-8").split("\n"):
        match = re.search(r"^([a-zA-Z0-9\-]+)\s*@\s*([a-zA-Z0-9\-/]+)", line)
        if match:
            boards.append((match.group(1), match.group(2)))
    return boards


def install(config: ConfigModel, progress: Progress, board: Optional[str] = None) -> None:
    """Install to a given board."""
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
            ["rshell", "--quiet", "ls", "-l", f"/{target_board}"],  # noqa:S607
            capture_output=True,
            check=False,
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
