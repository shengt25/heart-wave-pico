import os
import json
from src.utils import GlobalSettings, pico_rom_stat


def check_file_nr(user_id):
    """If file limit exceeded, delete the oldest one."""
    directory = f"{GlobalSettings.save_directory}/user_{user_id}/"
    files = os.listdir(directory)
    num_files = len(files)
    # also check storage space, if less than 10KB, delete the oldest file
    if num_files > GlobalSettings.files_limit or pico_rom_stat() <= 10:
        files.sort()  # With current file names setting, the oldest file is the first file using the sort().
        os.remove(directory + files[0])


def check_user_dir(user_id):
    """Ensure user-specific subdirectory exists."""
    base_directory = GlobalSettings.save_directory
    user_directory = f"{base_directory}/user_{user_id}"

    # Ensure base directory exists
    try:
        os.stat(base_directory)
    except OSError:
        os.mkdir(base_directory)

    # Ensure user subdirectory exists
    try:
        os.stat(user_directory)
    except OSError:
        os.mkdir(user_directory)


def save_system(data, user_id):
    """Save measurement data to user-specific directory.

    Args:
        data (dict): Measurement data to save
        user_id (str): User ID (e.g., '001', '002')

    Returns:
        bool: True if save successful
    """
    check_user_dir(user_id)
    check_file_nr(user_id)
    directory = f"{GlobalSettings.save_directory}/user_{user_id}"
    filename = data["DATE"].replace(":", ".")
    # format: DD.MM.YY hh:mm:ss,
    # only last two digits for year, because screen is too small to display 4
    # but seconds are important to distinguish files saved in the same minute, when measuring multiple times fast
    # seconds will be cut off in listview, also because of the small screen
    file_name = f"{directory}/{filename}.txt"
    with open(file_name, "w") as file:
        json.dump(data, file)
    return True


def load_history_list(user_id):
    """Load history file list for specific user.

    Args:
        user_id (str): User ID to load history for

    Returns:
        list: List of filenames sorted newest first
    """
    directory = f"{GlobalSettings.save_directory}/user_{user_id}/"
    try:
        files = os.listdir(directory)
        files.sort(reverse=True)  # newest first
        return files
    except OSError:
        # User directory doesn't exist yet (no measurements)
        return []


def load_history_data(file_name, user_id):
    """Load measurement data from user's directory.

    Args:
        file_name (str): Filename to load
        user_id (str): User ID who owns this file

    Returns:
        dict: Measurement data
    """
    directory = f"{GlobalSettings.save_directory}/user_{user_id}/"
    path = directory + file_name
    with open(path, 'r') as file:
        data = json.load(file)
    return data
