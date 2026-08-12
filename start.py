# handles auth generation and starts copyparty pointing to main.conf
import generate_auth

from glob import glob

# check for required files
if not glob("main.conf"):
    print("Missing main.conf! Please redownload from https://github.com/h-dew/steamoji_copyparty!")

if not glob("copyparty-sfx.py"):
    print("Missing copyparty-sfx.py! Please redownload from https://github.com/h-dew/steamoji_copyparty")

# to change apprentice folder name, can set APPRENTICE_FOLDER_NAME right here
#  EX: generate_auth.APPRENTICE_FOLDER_NAME = "folder"
# note that apprentice folder must be sibling to steamoji_copyparty

# check if apprentice parent folder exists
if not glob("../" + generate_auth.APPRENTICE_FOLDER_NAME):
    print("Could not find apprentice container folder! Check this script and manually change APPRENTICE_FOLDER_NAME above if needed")

# generate auth
print("Generating users from apprentice folder: " + generate_auth.APPRENTICE_FOLDER_NAME)
generate_auth.generateConfFile()

# double check that we have the users file
if not glob("users.conf"):
    print("Could not find users.conf... should've been generated earlier. Check apprentice folder layout or" + " generate_auth.py")



# TIME TO FORK BABY !!!
pid = os.fork()

# FINISH LATER
path_to_python_binary = sys.executable

args = ["python3", "/PATH"] # CHECK IF PATH IS RELATIVE

env = os.environ

os.execve(path_to_python_binary, args, env)

