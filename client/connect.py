import socket
import os
import subprocess
import shutil
from string import ascii_uppercase

# Get current drives using modern os.listdrives() (Python 3.12+)
# Fall back to checking existence if on older versions... I like the other way better
def getEmptyDrive():
    if hasattr(os, "listdrives"):
        used_drives = {d[0].upper() for d in os.listdrives()}
    else:
        used_drives = {
            chr(i) for i in range(65, 91) if os.path.exists(chr(i) + ":\\")
        }

    free_letters = sorted(set(ascii_uppercase) - used_drives)

    # Pick the first available empty slot letter
    empty_slot = free_letters[0] if free_letters else None

    if empty_slot == None:
        raise OSError("No open drive slots! System should be rebooted and non-essential extra drives should be removed")

    return empty_slot

def getIp(hostname):
    # Get IP of server
    # mDNS baybeeee!!
    return socket.gethostbyname(hostname)


def generateMountCommand(hostname, volume):
    mntlocation = getEmptyDrive()

    return f"rclone mount --vfs-cache-mode writes --dir-cache-time 5s --network-mode {hostname}-dav:{volume} {mntlocation}:".split()

def generateConfig(hostname, username, password):
    hosturl = "http://" + getIp(hostname)

    return f"rclone config create {hostname}-dav webdav url={hosturl} vendor=owncloud pacer_min_sleep=0.01ms user={username} pass={password}".split()

def connect(username, password, host, volume):
    # Generates Rclone config, then connects.
    # Returns 0 on success

    if shutil.which("rclone") is None:
        subprocess.run("winget install Rclone.Rclone",
                       shell=True)
        subprocess.run("winget install WinFsp.WinFsp",
                       shell=True)


    if len(host) < 1:
        # just a fallback in case
        host = "StoragePC"
        print("No host specified, using default: StoragePC")

    try:
        # Check that host resolves
        ip = getIp(host)

    except:
        print("Could not resolve host's IP! Check hostname. (" + host + ")")  
        return 1

    ## NVMMM WE USING POPEN
    subprocess.run(generateConfig(host, username, password))

    return subprocess.Popen(generateMountCommand(host, volume),
                     stdout=subprocess.PIPE,
                            creationflags=subprocess.CREATE_NO_WINDOW)

def connectApprentice(username, host):
    if len(host) < 1:
        host = "StoragePC"

    return connect(username, username, host, "")
