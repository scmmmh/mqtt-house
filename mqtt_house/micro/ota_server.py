import asyncio
import binascii
import json
import os

from hashlib import sha256
from machine import reset
from microdot import Microdot, Request
from status_led import status_led


Request.max_content_length = 1024 * 1024
server = Microdot()


def file_exists(filename):
    """Check if the given file exists."""
    try:
        return (os.stat(filename)[0] & 0x4000) == 0
    except OSError:
        return False


@server.get("/ota/about")
def about(request):
    """Return information about this device."""
    return {"version": "0.0.1"}


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
    with open("inventory.json", "wb") as out_f:
        while size > 0:
            chunk = await request.stream.read(min(size, 1024))
            hash.update(chunk)
            out_f.write(chunk)
            size -= len(chunk)
    status_led.stop_activity()
    if binascii.hexlify(hash.digest()).decode() == upload_hash:
        return None, 204
    else:
        os.remove("inventory.json")
        return "Inventory hash does not match", 400


@server.put("/ota/file")
async def update_file(request):
    """Update a file on the device."""
    status_led.start_activity()
    size = int(request.headers["Content-Length"])
    upload_hash = request.headers["X-Filehash"]
    hash = sha256()
    with open(f"{request.headers['X-Filename']}.tmp", "wb") as out_f:
        while size > 0:
            chunk = await request.stream.read(min(size, 1024))
            hash.update(chunk)
            out_f.write(chunk)
            size -= len(chunk)
    status_led.stop_activity()
    if binascii.hexlify(hash.digest()).decode() == upload_hash:
        return None, 204
    else:
        os.remove(f"{request.headers['X-Filename']}.tmp")
        return "File hash does not match", 400


@server.post("/ota/commit")
async def commit_update(request):
    """Commit the update specified by the inventory.json."""
    status_led.start_activity()
    if file_exists("inventory.json"):
        with open("inventory.json") as in_f:
            inventory = json.load(in_f)
        for filename in inventory.keys():
            if file_exists(filename):
                os.remove(filename)
            os.rename(f"{filename}.tmp", filename)
        for filename in os.listdir("/"):
            if filename not in inventory:
                os.remove(filename)
        status_led.stop_activity()
        return None, 204
    else:
        status_led.stop_activity()
        return None, 404
