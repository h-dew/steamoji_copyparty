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

print("script dir:" + script_dir + "\n")


# get username (NEEDS VALIDATION ON DEBIAN)
# 'sudo_user' env variable used as this run as sudo and most other methods return the root user
user = os.getenv('SUDO_USER')
USER_PLACEHOLDER = "{usr}"

time.sleep(5)

# Get user's home directory
dest_dir = os.path.join(os.path.expanduser("~"), "steamojicopyparty")

src_dir = os.path.dirname(script_dir)







## OUTLINE
# if old files exist. delete them.

if glob(dest_dir):
    print("Already found an installation at:" + copyparty_dir)
    print("Delete old installation and replace? Apprentice folder will not be modified. Press Y to continue")
    while true:
        userConfirmation = input()

        if len(userConfirmation) > 0:
            if userConfirmation.lower() == "y":
                print("Deleting old installation...")
                shutil.rmtree(dest_dir)
 
                break
            else:
                print("Cannot continue, exiting...")
                time.sleep(3)
                sys.exit()

# copy new files
shutil.cptree(dest_dir, )


# generate unit file

# place unit file

# register as systemd service




# EDIT SERVICE FILE FOR USER
# Maybe have the service file below be a template?
# Replace specific expression with user from above. idk should be doable.
# Maybe read template as string, replace format specifiers in string, then write file to usr/lib/systemd/system


try:
    with open("steamoji_copyparty.service", "r") as file:
        text = file.read()
        text = text.replace(u, user)
except IOError as e:
    if e[0] == errno.EPERM:
       sys.exit(Fore.YELLOW + "Run this script as sudo you dingus!")



with open("/usr/lib/systemd/system/steamojicopyparty.service", "w") as file:
    file.write(text)

if not glob("/usr/lib/systemd/system/steamojicopyparty.service"):
    print("Couldn't register service, please move file manually!")
