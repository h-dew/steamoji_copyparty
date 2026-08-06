# Places copyparty into user home directory and registers start.py as a systemd service
import os
import errno


# get username (NEEDS VALIDATION ON DEBIAN)
# 'sudo_user' env variable used as this run as sudo and most other methods return the root user
user = os.getenv('SUDO_USER')

userPholder = "{usr}"

# EDIT SERVICE FILE FOR USER
# Maybe have the service file below be a template?
# Replace specific expression with user from above. idk should be doable.
# Maybe read template as string, replace format specifiers in string, then write file to usr/lib/systemd/system

try:
    with open("steamoji_copyparty.service", "r") as file
        text = file.read()
        text = text.replace(userPholder, user)
except IOError as e:
    if e[0] == errno.EPERM:
       sys.exit("Run this script as sudo you dingus!")



with open("/usr/lib/systemd/system/steamoji_copyparty.service", "w") as file
    file.write(text)
