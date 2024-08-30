import os
import json
from src.utils import GlobalSettings, pico_rom_stat


def check_file_nr():
    """If file limit exceeded, delete the oldest one."""
    directory = GlobalSettings.save_directory + "/"
    files = os.listdir(directory)
    num_files = len(files)
    # also check storage space, if less than 10KB, delete the oldest file
    if num_files > GlobalSettings.files_limit or pico_rom_stat() <= 10:
        files.sort()  # With current file names setting, the oldest file is the first file using the sort().
        os.remove(directory + files[0])


def check_home_dir():
    directory = GlobalSettings.save_directory
    try:
        os.stat(directory)
    except OSError:
        os.mkdir(directory)


def save_system(data):
    check_home_dir()
    check_file_nr()
    directory = GlobalSettings.save_directory
    filename = data["DATE"].replace(":", ".")
    # format: DD.MM.YY hh:mm:ss,
    # only last two digits for year, because screen is too small to display 4
    # but seconds are important to distinguish files saved in the same minute, when measuring multiple times fast
    # seconds will be cut off in listview, also because of the small screen
    file_name = directory + "/" + filename + ".txt"
    with open(file_name, "w") as file:
        json.dump(data, file)
    return True


def load_history_list():
    directory = GlobalSettings.save_directory + "/"
    files = os.listdir(directory)
    files.sort(reverse=True)  # newest first
    return files


def load_history_data(file_name):
    directory = GlobalSettings.save_directory + "/"
    path = directory + file_name
    with open(path, 'r') as file:
        data = json.load(file)
    return data
