from glob import glob
import os
import errno

APPRENTICE_FOLDER_NAME = "apprentices"

# HELPERS

# format apprentice list for output
def printApprentices(apprentices):
    print("Apprentices:")
    for apprentice in apprentices:
        print("\t" + apprentice)

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
        volume += "./apprentice_folders/" + name + "\n  "
        volume += "accs:\n    rw: " + nameToUser(name) + "\n\n"
        volumes.append(volume)

    return "".join(volumes)
    



# CODE

# all directories in sibling folder APPRENTICE_FOLDER_NAME
apprentice_regex = "../" + APPRENTICE_FOLDER_NAME + "/*/"
apprentices = getFolderList(apprentice_regex)

# Check to see that we found at least 1 apprentice
if len(apprentices) < 1:
    print("Could not find apprentice folders!")
    raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), apprentice_regex)

# generate account and volume listings, write to file
with open("./conf/users.conf", "w", encoding="utf-8") as file:
    file.write(generateAccounts(apprentices))
    file.write("\n\n")
    file.write(generateVolume(apprentices))
