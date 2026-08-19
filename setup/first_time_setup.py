# Places copyparty into user home directory and registers start.py as a systemd service
import os
import errno
import subprocess
import shutil
import time
import sys

from pathlib import Path
from glob import glob

# HELPER
# makes checking systemctl easier
def manage_service(action, service_name):
    
    try:
        # Construct the command safely as a list
        command = ["systemctl", action, service_name]

        if len(service_name) < 1:
            command = ["systemctl", action]

        
        # Run the command and capture text output
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        
        print(f"Success: {action} on {service_name} completed.")
        return result.stdout
        
    except subprocess.CalledProcessError as e:
        print(f"Error executing systemctl: {e.stderr}")
        return None




## DOUBLE CHECK WE'RE IN THE RIGHT DIRECTORY
# Get the directory of the current script
script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)

## double check the os!! idk why but this may be needed
if not sys.platform.startswith('linux'):
    print("Error! This script only runs on Linux! It registers copyparty as a service and makes it run on boot.\nThe fileserver can be run in Windows, but the start.py file must be opened manually.")
    print("Automatically exiting in 5 seconds")
    time.sleep(5)
    sys.exit()

if os.geteuid() != 0:
        sys.exit("Error! This script must be run as root or with sudo.")


# get username (NEEDS VALIDATION ON DEBIAN)
# 'sudo_user' env variable used as this run as sudo and most other methods return the root user
USER_PLACEHOLDER = "{usr}"

username = os.environ.get("SUDO_USER")

print(username)

if username:
    # Safely expands to /home/username or /Users/username
    home_dir = Path(f"~{username}").expanduser()
else:
    # Fallback if running normally without sudo
    home_dir = Path.home()



# Get user's home dir and create path to installation destination
dest_dir = os.path.join(os.path.expanduser("~"), "steamojicopyparty")
src_dir = os.path.dirname(script_dir)


installed = False

## OUTLINE
# if old files exist. delete them.

if glob(dest_dir):
    print("Already found an installation at:" + dest_dir)
    print("Delete old installation and replace? Apprentice folder will not be modified.")
    installed = True
else:
    print("No install found, will install to: " + dest_dir)

if True:
    print("Press Y to continue")
    while True:
        userConfirmation = input()

        if len(userConfirmation) > 0:
            if userConfirmation.lower() == "y":

                if installed:
                    print("Deleting old installation...")
                    shutil.rmtree(dest_dir)

                # copy the repo to home folder
                shutil.copytree(src_dir, dest_dir)
                print("Successfully copied!")
                break
 
            else:
                if installed:
                    print("Leaving old installation...")
                    time.sleep(2)
                else:
                    print("Cannot continue with no install, exiting")
                    time.sleep(2)
                    sys.exit()

                break



# now that application is in place, generate unit file
unit_template_path_rel = "steamoji_copyparty_TEMPLATE.service"
unit_path_rel = "steamoji_copyparty.service"
unit_dest_path = os.path.join("/etc/systemd/system/", unit_path_rel)

restart_unit = "copyparty_restart.service"
restart_unit_dest = os.path.join("/etc/systemd/system/", restart_unit)
restart_timer = "copyparty_restart.timer"
restart_timer_dest = os.path.join("/etc/systemd/system/", restart_timer)



# Open template, replace {usr} placeholder
with open(unit_template_path_rel, "r") as file:
    text = file.read() 
    text = text.replace(USER_PLACEHOLDER, user)



# Write generated file to current dir
with open(unit_path_rel, "w") as file:
    file.write(text)


# Copy to /etc/systemd/system - this is where admin-created systemd unit files live
shutil.copy(unit_path_rel, unit_dest_path)

#also copy timer and restart units
shutil.copy(restart_unit, restart_unit_dest)
shutil.copy(restart_timer, restart_timer_dest)


# double check the service file is there before registering 
if not glob(unit_dest_path):
    print("Core service not found in folder! Try copying \"steamojicopyparty.service\" to \"/etc/systemd/system\" manually!")
    time.sleep(5)
    sys.exit()

if not glob(restart_unit_dest) or not glob(restart_timer_dest):
    print("Restart unit or timer not found in folder! Try copying \"copyparty_restart.service\" and \"copyparty_restart.timer\" to \"/etc/systemd/system\" manually!")
    time.sleep(5)
    sys.exit()




# REGISTER UNITS
# Only timer needs to be registered for the restart unit
manage_service("daemon-reload", "")
manage_service("enable", "steamoji_copyparty.service")
manage_service("enable", "copyparty_restart.timer")

