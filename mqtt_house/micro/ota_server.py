import asyncio
import binascii
import json
import os

from hashlib import sha256
from machine import reset
from microdot import Microdot, Request
from status_led import status_led

from mqtt_house.__about__ import __version__

Request.max_content_length = 1024 * 1024
server = Microdot()


def file_exists(filename):
    """Check if the given filename exists."""
    try:
        os.stat(filename)
        return True
    except OSError:
        return False


def is_file(filename):
    """Check if the given filename is a file."""
    try:
        return (os.stat(filename)[0] & 0x4000) == 0
    except OSError:
        return False


def is_dir(filename):
    """Check if the given filename is a directory."""
    try:
        return (os.stat(filename)[0] & 0x4000) != 0
    except OSError:
        return False


def makedirs(dirpath):
    """Create the directories on the dirpath, if they do not exist."""
    if len(dirpath) > 0:
        path = ""
        for part in dirpath:
            path = f"{path}/{part}"
            if not is_dir(path):
                os.mkdir(path)


def listdirs(dirpath):
    """List all directories and files underneath dirpath."""
    filenames = []
    dirnames = [dirpath]
    added = True
    while added:
        added = False
        for dirname in dirnames:
            for name in os.listdir(dirname):
                fullpath = f"{dirname}/{name}"
                if fullpath not in filenames and is_file(fullpath):
                    filenames.append(fullpath)
                elif fullpath not in dirnames and is_dir(fullpath):
                    dirnames.append(fullpath)
                    added = True
        dirnames.sort(key=lambda p: len(p), reverse=True)
    filenames.sort(key=lambda p: len(p), reverse=True)
    return dirnames, filenames


def rmtree(dirpath):
    """Remove the tree of files at dirpath."""
    dirnames, filenames = listdirs(dirpath)
    for filename in filenames:
        os.remove(filename)
    for dirname in dirnames:
        os.remove(dirname)


@server.get("/ota/about")
def about(request):
    """Return information about this device."""
    return {"version": __version__}


@server.post("/ota/reset")
def handle_reset(request):
    """Request that the device reset itself."""

    async def reset_task():
        """Wait one second and then reset."""
        await asyncio.sleep(1)
        reset()

    status_led.start_indeterminate()
    asyncio.create_task(reset_task())
    return None, 202


@server.put("/ota/inventory")
async def update_inventory(request):
    """Upload the OTA inventory."""
    status_led.start_activity()
    size = int(request.headers["Content-Length"])
    upload_hash = request.headers["X-Filehash"]
    hash = sha256()
    if not is_dir("uploads"):
        os.mkdir("uploads")
    with open("uploads/inventory.json", "wb") as out_f:
        while size > 0:
            chunk = await request.stream.read(min(size, 1024))
            hash.update(chunk)
            out_f.write(chunk)
            size -= len(chunk)
    status_led.stop_activity()
    if binascii.hexlify(hash.digest()).decode() == upload_hash:
        return None, 204
    else:
        os.remove("uploads/inventory.json")
        return "Inventory hash does not match", 400


@server.put("/ota/file")
async def update_file(request):
    """Update a file on the device."""
    status_led.start_activity()
    size = int(request.headers["Content-Length"])
    upload_hash = request.headers["X-Filehash"]
    filename = request.headers["X-Fileid"]
    if not is_dir("uploads"):
        os.mkdir("uploads")
    sha256_hash = sha256()
    with open(f"uploads/{filename}", "wb") as out_f:
        while size > 0:
            chunk = await request.stream.read(min(size, 1024))
            sha256_hash.update(chunk)
            out_f.write(chunk)
            size -= len(chunk)
    status_led.stop_activity()
    if binascii.hexlify(sha256_hash.digest()).decode() == upload_hash:
        return None, 204
    else:
        os.remove(f"uploads/{filename}")
        return "File hash does not match", 400


@server.post("/ota/commit")
async def commit_update(request):
    """Commit the update specified by the uploads/inventory.json."""
    if file_exists("uploads/inventory.json"):
        with open("uploads/inventory.json") as in_f:
            inventory = json.load(in_f)
        for entry in inventory:
            try:
                status_led.start_activity()
                if file_exists(entry["filename"]):
                    os.remove(entry["filename"])
                makedirs(entry["filename"].split("/")[:-1])
                os.rename(f"uploads/{entry['fileid']}", entry["filename"])
            except Exception as e:
                return str(e), 500
            finally:
                status_led.stop_activity()
        rmtree("uploads")
        return None, 204
    else:
        return None, 404


@server.post("/ota/rollback")
def rollback_update(request):
    """Rollback any existing, partial OTA update."""
    if is_dir("uploads"):
        rmtree("uploads")
    return None, 204
