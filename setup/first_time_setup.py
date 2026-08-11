# Places copyparty into user home directory and registers start.py as a systemd service
import os
import errno
import subprocess
import shutil
import time
import sys

from glob import glob

## DOUBLE CHECK WE'RE IN THE RIGHT DIRECTORY
# Get the directory of the current script
script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)

## double check the os!! idk why but this may be needed
if not sys.platform.startswith('linux'):
    print("This script only runs on Linux!\nThe fileserver can be run in Windows, but the start.py file must be opened manually.")
    print("Automatically exiting in 5 seconds")
    time.sleep(5)
    sys.exit()



# get username (NEEDS VALIDATION ON DEBIAN)
# 'sudo_user' env variable used as this run as sudo and most other methods return the root user
user = os.getenv('SUDO_USER')
USER_PLACEHOLDER = "{usr}"


# Get user's home dir and create path to installation destination
dest_dir = os.path.join(os.path.expanduser("~"), "steamojicopyparty")
src_dir = os.path.dirname(script_dir)




## OUTLINE
# if old files exist. delete them.

if glob(dest_dir):
    print("Already found an installation at:" + dest_dir)
    print("Delete old installation and replace? Apprentice folder will not be modified. Press Y to continue")
    while True:
        userConfirmation = input()

        if len(userConfirmation) > 0:
            if userConfirmation.lower() == "y":
                print("Deleting old installation...")
                shutil.rmtree(dest_dir)

                # copy the repo to home folder
                shutil.copytree(src_dir, dest_dir)

                break
 
            else:
                print("Leaving old installation...")
                time.sleep(2)

                break



# now that application is in place, generate unit file
unit_template_path_rel = "steamojicopyparty_TEMPLATE.service"
unit_path_rel = "steamojicopyparty.service"

unit_dest_path = os.path.join("/etc/systemd/system/", unit_path_rel)


# Open template, replace {usr} placeholder
with open(unit_template_path_rel, "r") as file:
    text = file.read()
    text = text.replace(USER_PLACEHOLDER, user)



# Write generated file to current dir
with open(unit_path_rel, "w") as file:
    file.write(text)


# Copy to /etc/systemd/system - this is where admin-created systemd unit files live
shutil.copy(unit_path_rel, unit_dest_path)


# double check the service file is there before registering 
if not glob(unit_dest_path):
    print("Service not found in folder! Try copying \"steamojicopyparty.service\" to to \"/etc/systemd/system\" manually!")
