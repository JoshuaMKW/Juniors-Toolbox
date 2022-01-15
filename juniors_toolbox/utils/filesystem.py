from pathlib import Path
import subprocess
import sys
from juniors_toolbox import __file__ as _ModulePath

def resource_path(relPath: str = "") -> Path:
    """
    Get absolute path to resource, works for dev and for cx_freeze
    """
    import sys

    if hasattr(sys, "_MEIPASS"):
        return getattr(sys, "_MEIPASS", Path(__file__).parent) / relPath
    else:
        if getattr(sys, "frozen", False):
            # The application is frozen
            base_path = Path(sys.executable).parent
        else:
            base_path = Path(_ModulePath).parent


        return base_path / relPath


def get_program_folder(folder: str = "") -> Path:
    """
    Get path to appdata
    """
    from os import getenv
    import sys

    if sys.platform == "win32":
        datapath = Path(getenv("APPDATA")) / folder
    elif sys.platform == "darwin":
        if folder:
            folder = "." + folder
        datapath = Path("~/Library/Application Support").expanduser() / folder
    elif "linux" in sys.platform:
        if folder:
            folder = "." + folder
        datapath = Path.home() / folder
    else:
        raise NotImplementedError(f"{sys.platform} OS is unsupported")
    return datapath


def open_path_in_explorer(path: Path):
    if sys.platform == "win32":
        subprocess.Popen(
            f"explorer /select,\"{path.resolve()}\"", shell=True)
    elif sys.platform == "linux":
        subprocess.Popen(["xdg-open", path.resolve()])
    elif sys.platform == "darwin":
        subprocess.Popen(['open', '--', path.resolve()])


# bytes pretty-printing
UNITS_MAPPING = (
    (1 << 50, " PB"),
    (1 << 40, " TB"),
    (1 << 30, " GB"),
    (1 << 20, " MB"),
    (1 << 10, " KB"),
    (1, (" byte", " bytes")),
)


# CREDITS: https://stackoverflow.com/a/12912296/13189621
def pretty_filesize(bytes, units=UNITS_MAPPING):
    """
    Get human-readable file sizes.
    simplified version of https://pypi.python.org/pypi/hurry.filesize/
    """
    for factor, suffix in units:
        if bytes >= factor:
            break
    amount = int(bytes / factor)

    if isinstance(suffix, tuple):
        singular, multiple = suffix
        if amount == 1:
            suffix = singular
        else:
            suffix = multiple
    return str(amount) + suffix