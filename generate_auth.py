from glob import glob
import os

# HELPERS

def getFolderList(path):
    apprentices = []

    # do a unix-style glob and iterate through all els
    for dir in glob(path):
        apprentices.append(os.path.basename(dir[:-1]))
    
    return apprentices

def nameToAccount(name):
    fname = nameToUser(name)
    return fname + ": " + fname

def nameToUser(name):
    return "".join(name.lower().split(" "))


def generateAccounts(names):
    accounts = "[accounts]\n"
    for name in names:
        accounts += "  " + nameToAccount(name) + "\n"
    return accounts

def generateVolume(names):
    volumes = []
    for name in names:
        volume = "[/" + name + "]\n  "
        volume += "./apprentice_folders/" + name + "\n  "
        volume += "accs:\n    rw: " + nameToUser(name) + "\n\n"
        volumes.append(volume)

    return "".join(volumes)
    

# CODE
apprentices = getFolderList("apprentice_folders/*/")

with open("./conf/users.conf", "w", encoding="utf-8") as file:
    file.write(generateAccounts(apprentices))
    file.write("\n\n")
    file.write(generateVolume(apprentices))
