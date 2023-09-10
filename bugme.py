#!/usr/bin/env python3
"""
Bugme
"""

import argparse
import logging
import os
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse, parse_qs
from typing import Any

from datetime import datetime
from dateutil import parser
from pytz import utc

from bugzilla import Bugzilla  # type: ignore
from bugzilla.exceptions import BugzillaError  # type: ignore
from github import Github, GithubException
from gitlab import Gitlab
from gitlab.exceptions import GitlabError
from redminelib import Redmine  # type: ignore
from redminelib.exceptions import BaseRedmineError  # type: ignore
from requests.exceptions import RequestException
from jinja2 import Template


DEFAULT_CREDENTIALS_FILE = os.path.expanduser("~/creds.json")

CODE_TO_HOST = {
    "bnc": "bugzilla.suse.com",
    "bsc": "bugzilla.suse.com",
    "boo": "bugzilla.suse.com",
    "gh": "github.com",
    "gl": "gitlab.com",
    "gsd": "gitlab.suse.de",
    "poo": "progress.opensuse.org",
}

VERSION = "1.1"


def dateit(date: str | datetime, time_format: str = "%a %b %d %H:%M:%S %Z %Y") -> str:
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
            item_id=int(issue_id),
            host=url.hostname,
            repo=repo,
        )
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

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(url='{self.url}')"

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
        except (AttributeError, BugzillaError, RequestException) as exc:
            logging.error("Bugzilla: %s: get_item(%d): %s", self.url, item_id, exc)
        return None

    def get_items(self, items: list[dict]) -> list[Item | None]:
        """
        Get Bugzilla items
        """
        try:
            return [
                self._to_item(info)
                for info in self.client.getbugs([item["item_id"] for item in items])
            ]
        except (AttributeError, BugzillaError, RequestException) as exc:
            logging.error("Bugzilla: %s: get_items(): %s", self.url, exc)
        return []

    def _to_item(self, info: Any) -> Item | None:
        return Item(
            id=info.id,
            status=info.status,
            title=info.summary,
            created=info.creation_time,
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
        # Uncomment when latest PyGithub is published on Tumbleweed
        # auth = Auth.Token(**creds)
        # self.client = Github(auth=auth)
        self.client = Github(**creds)

    def get_item(self, item_id: int = -1, **kwargs) -> Item | None:
        """
        Get Github issue
        """
        repo = kwargs.pop("repo")
        try:
            info = self.client.get_repo(repo, lazy=True).get_issue(item_id)
        except (GithubException, RequestException) as exc:
            logging.error("Github: get_issue(%s, %s): %s", repo, item_id, exc)
            return None
        return self._to_item(info, repo)

    def _to_item(self, info: Any, repo: str) -> Item | None:
        return Item(
            id=info.number,
            status=info.state,
            title=info.title,
            created=info.created_at,
            updated=info.updated_at,
            url=f"{self.url}/{repo}/issues/{info.number}",
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
            logging.error(
                "Gitlab: %s: get_issue(%s, %s): %s", self.url, repo, item_id, exc
            )
            return None
        return self._to_item(info, repo)

    def _to_item(self, info: Any, repo: str) -> Item | None:
        return Item(
            id=info.iid,
            status=info.state,
            title=info.title,
            created=info.created_at,
            updated=info.updated_at,
            url=f"{self.url}/{repo}/-/issues/{info.iid}",
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
        except (BaseRedmineError, RequestException) as exc:
            logging.error("Redmine: %s: get_issue(%d): %s", self.url, item_id, exc)
            return None
        return self._to_item(info)

    def _to_item(self, info: Any) -> Item | None:
        return Item(
            id=info.id,
            status=info.status.name,
            title=info.subject,
            created=info.created_on,
            updated=info.updated_on,
            url=f"{self.url}/issues/{info.id}",
            extra=info.raw(),
        )


def parse_args() -> argparse.Namespace:
    """
    Parse command line options
    """
    argparser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    argparser.add_argument(
        "-c",
        "--creds",
        default=DEFAULT_CREDENTIALS_FILE,
        help="path to credentials file",
    )
    argparser.add_argument("-f", "--format", help="output in Jinja2 format")
    argparser.add_argument(
        "-l",
        "--log",
        choices=["debug", "info", "warning", "error", "critical"],
        default="warning",
        help="log level",
    )
    argparser.add_argument(
        "-o", "--output", choices=["text", "json"], default="text", help="output type"
    )
    argparser.add_argument(
        "-t", "--time", default="%a %b %d %H:%M:%S %Z %Y", help="time format"
    )
    argparser.add_argument(
        "--version", action="version", version=f"{sys.argv[0]} VERSION"
    )
    argparser.add_argument("url", nargs="+")
    return argparser.parse_args()


HOST_TO_CLS = {
    "bugzilla.suse.com": MyBugzilla,
    "progress.opensuse.org": MyRedmine,
    "gitlab.suse.de": MyGitlab,
    "gitlab.com": MyGitlab,
    "github.com": MyGithub,
}


def main() -> None:  # pylint: disable=too-many-branches
    """
    Main function
    """
    with open(args.creds, encoding="utf-8") as file:
        if os.fstat(file.fileno()).st_mode & 0o77:
            sys.exit(f"ERROR: {args.creds} has insecure permissions")
        creds = json.load(file)

    host_items: dict[str, list[dict]] = {}
    for arg in args.url:
        item = get_item(arg)
        if item is None:
            continue
        if item["host"] not in host_items:
            host_items[item["host"]] = [item.__dict__]
        else:
            host_items[item["host"]].append(item.__dict__)

    all_items = []
    keys = {
        "url": "<70",
        "status": "<10",
        # "created": "<30",
        "updated": "<30",
        "title": "",
    }
    # args.format = "  ".join(f'{{{{"{{:{align}}}".format({key})}}}}' for key, align in keys.items())
    if args.format is None and args.output == "text":
        print("  ".join([f"{key.upper():{align}}" for key, align in keys.items()]))

    clients: dict[str, Any] = {}
    for host in host_items:
        clients[host] = HOST_TO_CLS[host](f"https://{host}", creds[host])

    if len(clients) == 0:
        sys.exit(0)

    with ThreadPoolExecutor(max_workers=len(clients)) as executor:
        iterator = executor.map(
            lambda host: clients[host].get_items(host_items[host]), clients
        )
        for items in iterator:
            for item in items:
                if item is None:
                    continue
                item.created = dateit(item.created, args.time)
                item.updated = dateit(item.updated, args.time)
                if args.output == "text":
                    if args.format:
                        print(Template(args.format).render(item.__dict__))
                    else:
                        print(
                            "  ".join(
                                [f"{item[key]:{align}}" for key, align in keys.items()]
                            )
                        )
                elif args.output == "json":
                    all_items.append(item.__dict__)

    if args.output == "json":
        print(json.dumps(all_items, default=str, sort_keys=True))


if __name__ == "__main__":
    args = parse_args()
    logging.basicConfig(
        format="%(levelname)-8s %(message)s", stream=sys.stderr, level=args.log.upper()
    )
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
