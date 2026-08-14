from glob import glob
import os
import errno
import tomllib
import os


    # Import this into another script and call generateConfFile to generate conf file. Drive and folder names are determined from paths.toml

# format apprentice list for output
def printApprentices(apprentices):
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

# given list of users, puts them in a group together
def generateGroup(names):
    group = "[groups] \n\tapprentices: "
    usernames = [nameToUser(name) for name in names]
    group = group + ", ".join(usernames)
    return group

# given list of names, generates account list
def generateAccounts(names):
    accounts = "[accounts]\n"
    for name in names:
        accounts += "  " + nameToAccount(name) + "\n"
    return accounts

# given list of names, generates volume listing
def generateVolume(names, path):
    volumes = []
    for name in names:
        volume = "[/" + name + "]\n  "
        volume += path + name + "\n  "
        volume += "accs:\n    rw: " + nameToUser(name) + "\n\n"
        volumes.append(volume)

    return "".join(volumes)

# generate the entire conf file. probably what you wanna use
def generateConfFile():
    # Get path names from paths.toml
    with open("./paths.toml", "rb") as file:
        paths = tomllib.load(file)

    # get drive and folder names from paths.toml
    apprenticeFolderName = paths["folders"]["apprenticeFolder"]
    storageDriveName = paths["drives"]["storage"]

    apprenticeFolderPath = "/mnt/" + storageDriveName + "/" + apprenticeFolderName + "/"

    # all directories in sibling folder APPRENTICE_FOLDER_NAME
    apprentice_regex = apprenticeFolderPath + "*/"
    apprentices = getFolderList(apprentice_regex)

    # check to see that we found at least 1 apprentice
    if len(apprentices) < 1:
        print("Could not find apprentice folders!")
        raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), apprentice_regex)

    print("Found apprentice(s), generating users.conf")

    # generate account and volume listings, write to file
    with open("./users.conf", "w", encoding="utf-8") as file:
        file.write(generateAccounts(apprentices))
        file.write("\n\n")
        file.write(generateGroup(apprentices))
        file.write("\n\n")
        file.write(generateVolume(apprentices, apprenticeFolderPath))

    print("Wrote to users.conf sucessfully")


