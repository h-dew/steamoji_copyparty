from glob import glob
import os
import errno
import tomllib
import os
import time


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

# fills template.conf with given values
def fillTemplate(storage, backup, projectFiles, misc):
    with open("./template.conf", "r") as file:
        text = file.read()
        text = text.replace("{storage}", storage).replace("{backup}", backup).replace("{projectFiles}", projectFiles).replace("{misc}", misc)

    return text
        



# generate the entire conf file. probably what you wanna use
def generateConfFile():
    # Get path names from paths.toml
    with open("./paths.toml", "rb") as file:
        paths = tomllib.load(file)

    # get drive and folder names from paths.toml
    apprenticeFolderName = paths["folders"]["apprenticeFolder"]
    projectFilesFolderName = paths["folders"]["projectFilesFolder"]
    miscFolderName = paths["folders"]["miscFolder"]


    storageDriveName = paths["drives"]["storage"]
    backupDriveName = paths["drives"]["backup"]


    storageDrivePath = "/mnt/" + storageDriveName + "/"
    backupDrivePath = "/mnt/" + backupDriveName + "/"

    apprenticeFolderPath = storageDrivePath + apprenticeFolderName + "/"
    apprentice_regex = apprenticeFolderPath + "*/"

    projectFilesFolderPath = storageDrivePath + projectFilesFolderName + "/"
    miscFolderPath = storageDrivePath + miscFolderName + "/"



    # check if drives are mounted and in the correct location
    if not glob(storageDrivePath):
        raise FileNotFoundError("Could not find storage drive! It should be mounted to /mnt/" + storageDriveName + "/. Make sure the drive is mounted and that it is mounted to the correct location.")

    if not glob(backupDrivePath):
        print("Could not find backup drive! It should be mounted to /mnt/" + storageDriveName + "/. Make sure the drive is mounted and that it is mounted to the correct location.")


    # double check that the apprentice, project files, and misc folders exist
    if not glob(apprenticeFolderPath):
        raise FileNotFoundError("Could not find apprentice folder with path: " + apprenticeFolderPath + ". Make sure the folder exists and has the right name.")

    if not glob(projectFilesFolderPath):
        raise FileNotFoundError("Could not find project files folder with path: " + projectFilesFolderPath + ". Make sure the folder exists and has the right name.")

    if not glob(miscFolderPath):
        raise FileNotFoundError("Could not find miscellaneous folder with path: " + miscFolderPath + ". Make sure the folder exists and has the right name.")



    apprentices = getFolderList(apprentice_regex)

    # check to see that we found at least 1 apprentice
    if len(apprentices) < 1:
        raise FileNotFoundError("No apprentices found! Make sure the apprentice folder isn't empty!")

    print("Found apprentice(s), generating users.conf")

    # generate account and volume listings, write to file
    with open("./users.conf", "w", encoding="utf-8") as file:
        file.write(generateAccounts(apprentices))
        file.write("\n\n")
        file.write(generateGroup(apprentices))
        file.write("\n\n")
        file.write(fillTemplate(storageDriveName, backupDriveName,
                                projectFilesFolderName, miscFolderName))
        file.write("\n\n")
        file.write(generateVolume(apprentices, apprenticeFolderPath))

    print("Wrote to users.conf sucessfully")


