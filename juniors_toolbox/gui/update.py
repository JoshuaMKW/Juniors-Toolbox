from distutils.version import LooseVersion
import time
from typing import Iterable, Optional

from github.GitRelease import GitRelease
from PySide6.QtCore import Signal, Slot, QObject, QRunnable

from juniors_toolbox import __version__
from juniors_toolbox.update import ReleaseManager


class GitUpdateScraper(QObject, QRunnable, ReleaseManager):
    updatesFound = Signal(list)

    def __init__(self, owner: str, repository: str, parent: Optional[QObject] = None):
        QObject.__init__(self, parent)
        ReleaseManager.__init__(self, owner, repository)
        self.setObjectName(f"{self.__class__.__name__}.{owner}.{repository}")

        self.waitTime = 0.0
        self._quitting = False

    def set_wait_time(self, seconds: float):
        self.waitTime = seconds

    @Slot()
    def run(self):
        newReleases = self.check_updates()
        if len(newReleases) > 0:
            self.updatesFound(newReleases)

        # while not self._quitting:
        #     newReleases = self.check_updates()
        #     if len(newReleases) > 0:
        #         self.updatesFound(newReleases)

        #     start = time.time()
        #     while time.time() - start < self.waitTime:
        #         if self._quitting:
        #             break
        #         time.sleep(1)

    def check_updates(self) -> Iterable[GitRelease]:
        successful = self.populate()
        if not successful:
            return []
        
        newestRelease = self.get_newest_release()
        if newestRelease is None:
            return []

        if LooseVersion(newestRelease.tag_name.lstrip("v")) <= LooseVersion(__version__.lstrip("v")):
            return []

        return self.get_releases()

    def kill(self) -> None:
        self._quitting = True