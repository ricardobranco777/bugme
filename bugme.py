#!/usr/bin/env python3
"""
Bugme
"""

import logging
import os
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse, parse_qs
from typing import Any, Dict, List, Union

from datetime import datetime
from dateutil import parser
from pytz import utc

from github import Github, Auth, GithubException
from gitlab import Gitlab
from gitlab.exceptions import GitlabError
from bugzilla import Bugzilla  # type: ignore
from bugzilla.exceptions import BugzillaError  # type: ignore
from redminelib import Redmine  # type: ignore
from redminelib.exceptions import BaseRedmineError  # type: ignore
from requests.exceptions import RequestException

CREDENTIALS_FILE = os.path.expanduser("~/creds.json")


def dateit(
    date: Union[str, datetime], time_format: str = "%a %b %d %H:%M:%S %Z %Y"
) -> str:
    """
    Return date in desired format
    """
    if isinstance(date, str):
        date = utc.normalize(parser.parse(date))
    return date.astimezone().strftime(time_format)


class Item:  # pylint: disable=too-few-public-methods
    """
    Item class
    """

    def __init__(self, **kwargs):
        for attr, value in kwargs.items():
            setattr(self, attr, value)

    # Allow access this object as a dictionary

    def __getitem__(self, item: str) -> Any:
        try:
            return getattr(self, item)
        except AttributeError as exc:
            raise KeyError(exc) from exc

    def __setitem__(self, item: str, value: Any):
        setattr(self, item, value)


def get_item(string: str) -> Union[Item, None]:
    """
    Get Item from string
    """
    if "#" not in string:
        string = string if string.startswith("https://") else f"https://{string}"
        url = urlparse(string)
        assert url.hostname is not None
        repo: str = ""
        if url.hostname.startswith("git"):
            repo = os.path.dirname(
                os.path.dirname(url.path.replace("/-/", "/"))
            ).lstrip("/")
            issue_id = os.path.basename(url.path)
        elif url.hostname.startswith("bugzilla"):
            issue_id = parse_qs(url.query)["id"][0]
        elif url.hostname == "progress.opensuse.org":
            issue_id = os.path.basename(url.path)
        return Item(
            host=url.hostname,
            repo=repo,
            id=int(issue_id),
        )
    if string.startswith(("bnc#", "boo#", "bsc#")):
        return Item(host="bugzilla.suse.com", id=int(string.split("#", 1)[1]))
    if string.startswith("poo#"):
        return Item(host="progress.opensuse.org", id=int(string.split("#", 1)[1]))
    code, repo, issue = string.split("#", 2)
    code_to_host = {
        "gh": "github.com",
        "gl": "gitlab.com",
        "gsd": "gitlab.suse.de",
    }
    try:
        return Item(host=code_to_host[code], repo=repo, id=int(issue))
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

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is not None:
            logging.error(
                "%s: %s: %s: %s",
                self.__class__.__name__,
                exc_type,
                exc_value,
                traceback,
            )

    def get_item(self, item: Item) -> Union[Item, None]:
        """
        This method must be overriden if get_items() isn't overriden
        """
        raise NotImplementedError(f"{self.__class__.__name__}: get_item()")

    def get_items(self, items: List[Item]) -> List[Union[Item, None]]:
        """
        Multithreaded get_items()
        """
        with ThreadPoolExecutor(max_workers=len(items)) as executor:
            return list(executor.map(self.get_item, items))


class MyBugzilla(Service):
    """
    Bugzilla
    """

    def __init__(self, url: str, creds: dict):
        super().__init__(url)
        sslverify = os.environ.get("REQUESTS_CA_BUNDLE", True)
        self.client = Bugzilla(self.url, force_rest=True, sslverify=sslverify, **creds)

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            self.client.disconnect()
        except BugzillaError:
            pass
        super().__exit__(exc_type, exc_value, traceback)

    def get_item(self, item: Item) -> Union[Item, None]:
        """
        Get Bugzilla item
        """
        try:
            return self._to_item(self.client.getbug(item.id))
        except BugzillaError as exc:
            logging.error("Bugzilla: %s: get_items(%d): %s", self.url, item, exc)
        return None

    def get_items(self, items: List[Item]) -> List[Union[Item, None]]:
        """
        Get Bugzilla items
        """
        try:
            return [
                self._to_item(info)
                for info in self.client.getbugs([_.id for _ in items])
            ]
        except BugzillaError as exc:
            logging.error("Bugzilla: %s: get_items(): %s", self.url, exc)
        return []

    def _to_item(self, info: Any) -> Union[Item, None]:
        return Item(
            id=info.id,
            status=info.status,
            title=info.summary,
            updated=info.last_change_time,
            url=f"{self.url}/show_bug.cgi?id={info.id}",
            extra=info.__dict__,
        )


class MyGithub(Service):
    """
    Github
    """

    def __init__(self, url: str, creds: dict):
        super().__init__(url)
        auth = Auth.Token(**creds)
        self.client = Github(auth=auth)

    def get_item(self, item: Item) -> Union[Item, None]:
        """
        Get Github issue
        """
        try:
            info = self.client.get_repo(item.repo, lazy=True).get_issue(item.id)
        except GithubException as exc:
            logging.error("Github: get_issue(%s): %s", item.id, exc)
            return None
        return self._to_item(info, item)

    def _to_item(self, info: Any, item: Item) -> Union[Item, None]:
        return Item(
            id=info.number,
            status=info.state,
            title=info.title,
            updated=info.last_modified,
            url=f"{self.url}/{item.repo}/issues/{item.id}",
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

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            self.client.__exit__(exc_type, exc_value, traceback)
        except GitlabError:
            pass
        super().__exit__(exc_type, exc_value, traceback)

    def get_item(self, item: Item) -> Union[Item, None]:
        """
        Get Gitlab issue
        """
        try:
            info = self.client.projects.get(item.repo, lazy=True).issues.get(item.id)
        except (GitlabError, RequestException) as exc:
            logging.error("Gitlab: %s: get_issue(%s): %s", self.url, item.id, exc)
            return None
        return self._to_item(info, item)

    def _to_item(self, info: Any, item: Item) -> Union[Item, None]:
        return Item(
            id=info.iid,
            status=info.state,
            title=info.title,
            updated=info.updated_at,
            url=f"{self.url}/{item.repo}/-/issues/{item.id}",
            extra=info.asdict(),
        )


class MyRedmine(Service):
    """
    Redmine
    """

    def __init__(self, url: str, creds: dict):
        super().__init__(url)
        self.client = Redmine(url=self.url, raise_attr_exception=False, **creds)

    def get_item(self, item: Item) -> Union[Item, None]:
        """
        Get Redmine ticket
        """
        try:
            info = self.client.issue.get(item.id)
        except BaseRedmineError as exc:
            logging.error("Redmine: %s: get_issue(%d): %s", self.url, item.id, exc)
            return None
        return self._to_item(info)

    def _to_item(self, info: Any) -> Union[Item, None]:
        return Item(
            id=info.id,
            status=info.status.name,
            title=info.subject,
            updated=info.updated_on,
            url=f"{self.url}/issues/{info.id}",
            extra=info.raw(),
        )


def main() -> None:
    """
    Main function
    """
    with open(CREDENTIALS_FILE, encoding="utf-8") as file:
        if os.fstat(file.fileno()).st_mode & 0o77:
            sys.exit(f"ERROR: {CREDENTIALS_FILE} has insecure permissions")
        creds = json.load(file)

    items: Dict[str, List[Item]] = {}
    for arg in sys.argv[1:]:
        item = get_item(arg)
        if item is None:
            continue
        if item["host"] not in items:
            items[item["host"]] = [item]
        else:
            items[item["host"]].append(item)

    host_to_cls = {
        "bugzilla.suse.com": MyBugzilla,
        "progress.opensuse.org": MyRedmine,
        "gitlab.suse.de": MyGitlab,
        "gitlab.com": MyGitlab,
        "github.com": MyGithub,
    }

    clients: Dict[str, Any] = {}
    for host in items:
        clients[host] = host_to_cls[host](f"https://{host}", creds[host])

    if len(clients) == 0:
        sys.exit(0)

    with ThreadPoolExecutor(max_workers=len(clients)) as executor:
        iterator = executor.map(
            lambda host: clients[host].get_items(items[host]), clients
        )
        for results in iterator:
            for item in results:
                if item is None:
                    continue
                print(
                    "\t".join(
                        [item.url, item.status, dateit(item.updated), item.title]
                    )
                )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
