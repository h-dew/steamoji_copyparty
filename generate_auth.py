from glob import glob
import os
import errno

from colorama import init as colorama_init
from colorama import Fore
from colorama import Style

APPRENTICE_FOLDER_NAME = "apprentices"

colorama_init(autoreset=True)

# HELPERS

# format apprentice list for output
def printApprentices(apprentices):
    for apprentice in apprentices:
        print("\t" + Fore.YELLOW + apprentice)

# do a unix-style glob to generate list of folders matching path
def getFolderList(path):
    apprentices = []

    # do a unix-style glob and iterate through all els
    for dir in glob(path):
        apprentices.append(os.path.basename(dir[:-1]))
   
    printApprentices(apprentices)

    return apprentices

# format folder name to copyparty login
def nameToAccount(name):
    fname = nameToUser(name)
    return fname + ": " + fname

# join first and last names from folder, make lowercase
def nameToUser(name):
    return "".join(name.lower().split(" "))

# given list of names, generates account list
def generateAccounts(names):
    accounts = "[accounts]\n"
    for name in names:
        accounts += "  " + nameToAccount(name) + "\n"
    return accounts

# given list of names, generates volume listing
def generateVolume(names):
    volumes = []
    for name in names:
        volume = "[/" + name + "]\n  "
        volume += "../" + APPRENTICE_FOLDER_NAME + "/" + name + "\n  "
        volume += "accs:\n    rw: " + nameToUser(name) + "\n\n"
        volumes.append(volume)

    return "".join(volumes)

# generate the entire conf file. probably what you wanna use
def generateConfFile():
    # all directories in sibling folder APPRENTICE_FOLDER_NAME
    apprentice_regex = "../" + APPRENTICE_FOLDER_NAME + "/*/"
    apprentices = getFolderList(apprentice_regex)

    # check to see that we found at least 1 apprentice
    if len(apprentices) < 1:
        print(Fore.RED + "Could not find apprentice folders!" + Fore.RESET_ALL)
        raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), apprentice_regex)

    print(Fore.GREEN + "Found apprentice(s), generating users.conf")

    # generate account and volume listings, write to file
    with open("./users.conf", "w", encoding="utf-8") as file:
        file.write(generateAccounts(apprentices))
        file.write("\n\n")
        file.write(generateVolume(apprentices))

    print(Fore.GREEN + "Wrote to users.conf sucessfully")


