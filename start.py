# handles auth generation and starts copyparty pointing to main.conf
import generate_auth
import tomllib
import os
import sys

from glob import glob

# get drive and folder names
apprenticeFolderName = "apprentice_folders"

# check for required files
if not glob("main.conf"):
    print("Missing main.conf! Please redownload from: https://github.com/h-dew/steamoji_copyparty!")

if not glob("copyparty-sfx.py"):
    print("Missing copyparty-sfx.py! Please redownload from: https://github.com/h-dew/steamoji_copyparty")

# check for paths.toml
if not glob("paths.toml"):
    print("Could not find paths.toml in ... please redownload from: https://github.com/h-dew/steamoji_copyparty")


# to change apprentice folder name, can set APPRENTICE_FOLDER_NAME right here
#  EX: generate_auth.APPRENTICE_FOLDER_NAME = "folder"
# note that apprentice folder must be sibling to steamoji_copyparty

# check if apprentice parent folder exists
#if not glob("../" + generate_auth.APPRENTICE_FOLDER_NAME):
#    print("Could not find apprentice container folder! Check this script and manually change APPRENTICE_FOLDER_NAME above if needed")



# generate auth
print("Generating users from apprentice folder: " + apprenticeFolderName)
generate_auth.generateConfFile()

# double check that we have the users file
if not glob("users.conf"):
    print("Could not find users.conf... should've been generated earlier. Check apprentice folder layout or" + " generate_auth.py")


# FINISH LATER
target_script = "copyparty-sfx.py"

args = [sys.executable, target_script, "-c", "main.conf"]

os.execv(sys.executable, args)

