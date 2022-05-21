import webbrowser
from distutils.version import LooseVersion
from typing import Iterable, List, Optional

from github import Github
from github.PaginatedList import PaginatedList
from github.GitRelease import GitRelease

from juniors_toolbox import __version__

class ReleaseManager():
    def __init__(self, owner: str, repository: str):
        self._owner = owner
        self._repo = repository
        self._releases: Optional[PaginatedList[GitRelease]] = None
        self.populate()

    @property
    def owner(self) -> str:
        return self._owner

    @property
    def repository(self) -> str:
        return self._repo

    @owner.setter
    def owner(self, owner: str):
        self._owner = owner

    @repository.setter
    def repository(self, repo: str):
        self._repo = repo

    @property
    def releaseLatestURL(self) -> str:
        return f"https://github.com/{self._owner}/{self._repo}/releases/latest"

    @property
    def releasesURL(self) -> str:
        return f"https://github.com/{self._owner}/{self._repo}/releases"

    def get_newest_release(self) -> Optional[GitRelease]:
        if self._releases is None or self._releases.totalCount == 0:
            return None
        return self._releases[0]

    def get_oldest_release(self) -> Optional[GitRelease]:
        if self._releases is None or self._releases.totalCount == 0:
            return None
        return self._releases[-1]

    def get_releases(self) -> Iterable[GitRelease]:
        if self._releases is None or self._releases.totalCount == 0:
            return []
        return self._releases

    def compile_changelog_from(self, version: str) -> str:
        """ Returns a Markdown changelog from the info of future versions """
        seperator = "\n\n---\n\n"

        newReleases: List[GitRelease] = list()
        lver = LooseVersion(version.lstrip("v"))
        for release in self.get_releases():
            if LooseVersion(release.tag_name.lstrip("v")) <= lver:
                break
            newReleases.append(release)

        markdown = ""
        for release in newReleases:
            markdown += release.body.replace("Changelog",
                                             f"Changelog ({release.tag_name})").strip() + seperator

        return markdown.rstrip(seperator).strip()

    def populate(self) -> bool:
        g = Github()
        repo = g.get_repo(f"{self.owner}/{self.repository}")
        self._releases = repo.get_releases()
        return True

    @staticmethod
    def view(release: GitRelease, browser: Optional[webbrowser.GenericBrowser] = None, asWindow: bool = False):
        if browser is None:
            webbrowser.open(release.html_url, int(asWindow))
        else:
            browser.open(release.html_url, int(asWindow))
