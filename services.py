"""
Services
"""

import logging
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from urllib.parse import urlparse, parse_qs
from typing import Any

from bugzilla import Bugzilla  # type: ignore
from bugzilla.exceptions import BugzillaError  # type: ignore
from github import Github, GithubException
from gitlab import Gitlab
from gitlab.exceptions import GitlabError
from redminelib import Redmine  # type: ignore
from redminelib.exceptions import BaseRedmineError, ResourceNotFoundError  # type: ignore
from requests.exceptions import RequestException


CODE_TO_HOST = {
    "bnc": "bugzilla.suse.com",
    "bsc": "bugzilla.suse.com",
    "boo": "bugzilla.suse.com",
    "gh": "github.com",
    "gl": "gitlab.com",
    "gsd": "gitlab.suse.de",
    "poo": "progress.opensuse.org",
}


class Item:  # pylint: disable=too-few-public-methods
    """
    Item class
    """

    def __init__(self, **kwargs):
        for attr, value in kwargs.items():
            setattr(self, attr, value)

    def __repr__(self):
        attrs = ", ".join(f"{attr}={getattr(self, attr)!r}" for attr in vars(self))
        return f"{self.__class__.__name__}({attrs})"

    # Allow access this object as a dictionary
    def __getitem__(self, item: str) -> Any:
        try:
            return getattr(self, item)
        except AttributeError as exc:
            raise KeyError(exc) from exc


def get_item(string: str) -> Item | None:
    """
    Get Item from string
    """
    if "#" not in string:
        # URL
        string = string if string.startswith("https://") else f"https://{string}"
        url = urlparse(string)
        hostname = url.hostname.removeprefix("www.") if url.hostname is not None else ""
        repo: str = ""
        if hostname.startswith("git"):
            repo = os.path.dirname(
                os.path.dirname(url.path.replace("/-/", "/"))
            ).lstrip("/")
            issue_id = os.path.basename(url.path)
        elif hostname.startswith("bugzilla"):
            issue_id = parse_qs(url.query)["id"][0]
        elif hostname == "progress.opensuse.org":
            issue_id = os.path.basename(url.path)
        else:
            return None
        return Item(
            item_id=int(issue_id),
            host=hostname,
            repo=repo,
        )
    # Tag
    try:
        code, repo, issue = string.split("#", 2)
    except ValueError:
        code, issue = string.split("#", 1)
        repo = ""
    try:
        return Item(
            item_id=int(issue),
            host=CODE_TO_HOST[code],
            repo=repo,
        )
    except KeyError:
        logging.warning("Unsupported %s", string)
    return None


class Service:
    """
    Service class to abstract methods
    """

    def __init__(self, url: str):
        url = url.rstrip("/")
        self.url = url if url.startswith("https://") else f"https://{url}"
        self.tag = "".join([s[0] for s in str(urlparse(self.url).hostname).split(".")])

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(url='{self.url}')"

    def _not_found(self, item_id: int, url: str, tag: str) -> Item:
        now = datetime.now()
        return Item(
            id=item_id,
            status="ERROR",
            title="NOT FOUND",
            created=now,
            updated=now,
            url=url,
            tag=tag,
            extra={},
        )

    def get_item(self, item_id: int = -1, **kwargs) -> Item | None:
        """
        This method must be overriden if get_items() isn't overriden
        """
        raise NotImplementedError(f"{self.__class__.__name__}: get_item()")

    def get_items(self, items: list[dict]) -> list[Item | None]:
        """
        Multithreaded get_items()
        """
        with ThreadPoolExecutor(max_workers=min(10, len(items))) as executor:
            return list(executor.map(lambda it: self.get_item(**it), items))


class MyBugzilla(Service):
    """
    Bugzilla
    """

    def __init__(self, url: str, creds: dict):
        super().__init__(url)
        sslverify = os.environ.get("REQUESTS_CA_BUNDLE", True)
        try:
            self.client = Bugzilla(
                self.url, force_rest=True, sslverify=sslverify, **creds
            )
        except (BugzillaError, RequestException) as exc:
            logging.error("Bugzilla: %s: %s", self.url, exc)

    def __del__(self):
        try:
            self.client.disconnect()
        except (AttributeError, BugzillaError):
            pass

    def get_item(self, item_id: int = -1, **kwargs) -> Item | None:
        """
        Get Bugzilla item
        """
        try:
            return self._to_item(self.client.getbug(item_id))
        except IndexError:
            return self._not_found(
                item_id,
                f"{self.url}/show_bug.cgi?id={item_id}",
                f"{self.tag}#{item_id}",
            )
        except (AttributeError, BugzillaError, RequestException) as exc:
            logging.error("Bugzilla: %s: get_item(%d): %s", self.url, item_id, exc)
        return None

    def get_items(self, items: list[dict]) -> list[Item | None]:
        """
        Get Bugzilla items
        """
        try:
            found = [
                self._to_item(info)
                for info in self.client.getbugs([item["item_id"] for item in items])
            ]
        except (AttributeError, BugzillaError, RequestException) as exc:
            logging.error("Bugzilla: %s: get_items(): %s", self.url, exc)
            return []
        # Bugzilla silently fails on not found items
        found_ids = {item["id"] for item in found}
        not_found = [
            self._not_found(
                item["item_id"],
                f"{self.url}/show_bug.cgi?id={item['item_id']}",
                f"{self.tag}#{item['item_id']}",
            )
            for item in items
            if item["item_id"] not in found_ids
        ]
        return found + not_found  # type: ignore

    def _to_item(self, info: Any) -> Item:
        return Item(
            id=info.id,
            status=info.status,
            title=info.summary,
            created=info.creation_time,
            updated=info.last_change_time,
            url=f"{self.url}/show_bug.cgi?id={info.id}",
            tag=f"{self.tag}#{info.id}",
            extra=info.__dict__,
        )


class MyGithub(Service):
    """
    Github
    """

    def __init__(self, url: str, creds: dict):
        super().__init__(url)
        # Uncomment when latest PyGithub is published on Tumbleweed
        # auth = Auth.Token(**creds)
        # self.client = Github(auth=auth)
        self.client = Github(**creds)
        self.tag = "gh"

    def get_item(self, item_id: int = -1, **kwargs) -> Item | None:
        """
        Get Github issue
        """
        repo = kwargs.pop("repo")
        try:
            info = self.client.get_repo(repo, lazy=True).get_issue(item_id)
        except (GithubException, RequestException) as exc:
            if getattr(exc, "status", None) == 404:
                return self._not_found(
                    item_id,
                    "{self.url}/{repo}/issues/{item_id}",
                    "{self.tag}#{repo}#{item_id}",
                )
            logging.error("Github: get_issue(%s, %s): %s", repo, item_id, exc)
            return None
        return self._to_item(info, repo)

    def _to_item(self, info: Any, repo: str) -> Item:
        return Item(
            id=info.number,
            status=info.state,
            title=info.title,
            created=info.created_at,
            updated=info.updated_at,
            url=f"{self.url}/{repo}/issues/{info.number}",
            tag=f"{self.tag}#{repo}#{info.number}",
            extra=info.__dict__["_rawData"],
        )


class MyGitlab(Service):
    """
    Gitlab
    """

    def __init__(self, url: str, creds: dict):
        super().__init__(url)
        ssl_verify = os.environ.get("REQUESTS_CA_BUNDLE", False) if self.url else True
        self.client = Gitlab(url=self.url, ssl_verify=ssl_verify, **creds)
        hostname = str(urlparse(self.url).hostname)
        self.tag = "gl" if hostname == "gitlab.com" else self.tag

    def __del__(self):
        try:
            self.client.__exit__(None, None, None)
        except (AttributeError, GitlabError):
            pass

    def get_item(self, item_id: int = -1, **kwargs) -> Item | None:
        """
        Get Gitlab issue
        """
        repo = kwargs.pop("repo")
        try:
            info = self.client.projects.get(repo, lazy=True).issues.get(item_id)
        except (GitlabError, RequestException) as exc:
            if getattr(exc, "response_code", None) == 404:
                return self._not_found(
                    item_id,
                    f"{self.url}/{repo}/-/issues/{item_id}",
                    f"{self.tag}#{repo}#{item_id}",
                )
            logging.error(
                "Gitlab: %s: get_issue(%s, %s): %s", self.url, repo, item_id, exc
            )
            return None
        return self._to_item(info, repo)

    def _to_item(self, info: Any, repo: str) -> Item:
        return Item(
            id=info.iid,
            status=info.state,
            title=info.title,
            created=info.created_at,
            updated=info.updated_at,
            url=f"{self.url}/{repo}/-/issues/{info.iid}",
            tag=f"{self.tag}#{repo}#{info.iid}",
            extra=info.asdict(),
        )


class MyRedmine(Service):
    """
    Redmine
    """

    def __init__(self, url: str, creds: dict):
        super().__init__(url)
        self.client = Redmine(url=self.url, raise_attr_exception=False, **creds)

    def get_item(self, item_id: int = -1, **kwargs) -> Item | None:
        """
        Get Redmine ticket
        """
        try:
            info = self.client.issue.get(item_id)
        except ResourceNotFoundError:
            return self._not_found(
                item_id, f"{self.url}/issues/{item_id}", f"{self.tag}#{item_id}"
            )
        except (BaseRedmineError, RequestException) as exc:
            logging.error("Redmine: %s: get_issue(%d): %s", self.url, item_id, exc)
            return None
        return self._to_item(info)

    def _to_item(self, info: Any) -> Item:
        return Item(
            id=info.id,
            status=info.status.name,
            title=info.subject,
            created=info.created_on,
            updated=info.updated_on,
            url=f"{self.url}/issues/{info.id}",
            tag=f"{self.tag}#{info.id}",
            extra=info.raw(),
        )
