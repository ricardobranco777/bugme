#!/usr/bin/env python3
"""
Bugme
"""

import argparse
import logging
import html
import os
import json
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from scantags import scan_tags
from services import get_urltag, Issue
from services.guess import guess_service
from utils import dateit, html_tag


VERSION = "2.3.3"

DEFAULT_CREDENTIALS_FILE = os.path.expanduser("~/creds.json")


def parse_args() -> argparse.Namespace:
    """
    Parse command line options
    """
    argparser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        epilog="output fields for --fields: tag url status created updated title assignee creator",
    )
    argparser.add_argument(
        "-c",
        "--creds",
        default=DEFAULT_CREDENTIALS_FILE,
        help="path to credentials file",
    )
    argparser.add_argument(
        "-f", "--fields", default="tag,status,updated,title", help="output fields"
    )
    argparser.add_argument(
        "-l",
        "--log",
        choices=["none", "debug", "info", "warning", "error", "critical"],
        default="info",
        help="log level",
    )
    argparser.add_argument(
        "-o",
        "--output",
        choices=["text", "html", "json"],
        default="text",
        help="output type",
    )
    argparser.add_argument("-r", "--reverse", action="store_true", help="reverse sort")
    argparser.add_argument(
        "-s",
        "--sort",
        choices=[
            "tag",
            "url",
            "status",
            "created",
            "updated",
            "assignee",
            "creator",
        ],
        help="sort key",
    )
    argparser.add_argument(
        "-S",
        "--status",
        action="append",
        help="filter by status (may be specified multiple times)",
    )
    argparser.add_argument(
        "-t", "--time", default="timeago", metavar="TIME_FORMAT", help="strftime format"
    )
    argparser.add_argument("--user", action="store_true", help="get user issues")
    argparser.add_argument("--version", action="version", version=f"bugme {VERSION}")
    argparser.add_argument("url", nargs="*")
    return argparser.parse_args()


def get_clients(
    hostnames: list[str],
    creds: dict[str, dict[str, str]],
) -> dict[str, Any]:
    """
    Get clients
    """
    clients: dict[str, Any] = {}
    for host in hostnames:
        cls = guess_service(host)
        if cls is None:
            logging.error("Unknown: %s", host)
            sys.exit(1)
        clients[host] = cls(host, creds.get(host, {}))

    if len(clients) == 0:
        sys.exit(0)
    return clients


def get_user_issues(
    creds: dict[str, dict[str, str]],
    urltags: list[str] | None,
    statuses: list[str] | None,
) -> list[Issue]:
    """
    Get user issues
    """
    if not urltags:
        urltags = list(creds.keys())
    clients = get_clients(urltags, creds)
    all_issues = []
    with ThreadPoolExecutor(max_workers=len(clients)) as executor:
        iterator = executor.map(lambda host: clients[host].get_user_issues(), clients)
        for issues in iterator:
            all_issues.extend(
                [
                    issue
                    for issue in issues
                    if issue is not None
                    and (statuses is None or issue.status in set(statuses))
                ]
            )
    return all_issues


def get_issues(
    creds: dict[str, dict[str, str]],
    urltags: list[str],
    statuses: list[str] | None,
) -> list[Issue]:
    """
    Get issues
    """
    host_items: dict[str, list[dict]] = defaultdict(list)
    for urltag in urltags:
        item = get_urltag(urltag)
        if item is None:
            continue
        host_items[item["host"]].append(item)  # type: ignore

    clients = get_clients(list(host_items.keys()), creds)

    all_issues = []
    with ThreadPoolExecutor(max_workers=len(clients)) as executor:
        iterator = executor.map(
            lambda host: clients[host].get_issues(host_items[host]), clients
        )
        for issues in iterator:
            all_issues.extend(
                [
                    issue
                    for issue in issues
                    if issue is not None
                    and (statuses is None or issue.status in set(statuses))
                ]
            )
    return all_issues


def print_header(output_type: str, output_format: str, fields: dict[str, int]):
    """
    Print header
    """
    if output_type == "html":
        cells = "".join(html_tag("th", field.upper()) for field in fields)
        header = html_tag("thead", html_tag("tr", cells))
        print(f"<table>{header}<tbody>")
    elif output_type == "text":
        print(output_format.format(**{field: field.upper() for field in fields}))


def print_issue(
    issue: Issue,
    output_type: str,
    output_format: str,
    fields: dict[str, int],
):
    """
    Print issue
    """
    if output_type == "html":
        info = {
            field: html.escape(issue[field])
            if isinstance(issue[field], str)
            else issue[field]
            for field in fields
        }
        info["tag"] = html_tag("a", issue.tag, href=issue.url)
        info["url"] = html_tag("a", issue.url, href=issue.url)
        cells = "".join(html_tag("td", info[field]) for field in fields)
        print(html_tag("tr", cells, **{"class": "info"}))
        for info in issue.files:
            info = {
                k: html.escape(v) if isinstance(v, str) else v for k, v in info.items()
            }
            author = html_tag("a", info["author"], href=f'mailto:{info["email"]}')
            date = html_tag("a", info["date"], href=info["commit"])
            cells = (
                html_tag("td", "") * (len(fields) - 3)
                + html_tag("td", author)
                + html_tag("td", date)
                + html_tag("td", html_tag("a", info["file"], href=info["url"]))
            )
            print(html_tag("tr", cells))
    elif output_type == "text":
        print(output_format.format(**issue.__dict__))
        for info in issue.files:
            print(
                "\t"
                + "\t".join([info["email"], info["commit"].split("/")[-1], info["url"]])
            )


def print_issues(  # pylint: disable=too-many-arguments,too-many-locals,too-many-branches
    creds: dict[str, dict[str, str]],
    urltags: list[str] | None,
    time_format: str,
    output_format: str,
    output_type: str,
    statuses: list[str] | None,
    sort_key: str | None,
    reverse: bool,
    user: bool,
) -> None:
    """
    Print issues
    """
    xtags = {}
    if user:
        issues = get_user_issues(creds, urltags, statuses)
    else:
        if not urltags:
            try:
                xtags = scan_tags(".", token=creds["github.com"]["login_or_token"])
            except OSError as exc:
                logging.error("%s", exc)
                return
            urltags = list(xtags.keys())
        issues = get_issues(creds, urltags, statuses)

    if sort_key in {"tag", "url"}:
        issues.sort(key=Issue.sort_key, reverse=reverse)
    elif sort_key is not None:
        issues.sort(
            key=lambda it: (it[sort_key], *it.sort_key()),  # type:ignore
            reverse=reverse,
        )

    fields = {field: len(field) for field in output_format.split(",")}
    for issue in issues:
        for field in "created", "updated":
            if field in fields:
                issue[field] = dateit(issue[field], time_format)
        issue.files = xtags.get(issue.tag, [])
        for info in issue.files:
            info["date"] = dateit(info["date"], time_format)  # type: ignore
        if output_type == "text":
            fields |= {
                field: max(width, len(issue[field]))
                for field, width in fields.items()
                if field != "title"
            }

    if output_type == "json":
        print(json.dumps([it.__dict__ for it in issues], default=str, sort_keys=True))
        return

    output_format = "  ".join(f"{{{field}:{align}}}" for field, align in fields.items())
    print_header(output_type, output_format, fields)
    for issue in issues:
        print_issue(issue, output_type, output_format, fields)
    if output_type == "html":
        print("</tbody></table>")


def main():
    """
    Main function
    """
    args = parse_args()
    if args.log == "none":
        logging.disable()
    else:
        logging.basicConfig(
            format="%(levelname)-8s %(message)s",
            stream=sys.stderr,
            level=args.log.upper(),
        )
    if os.getenv("DEBUG"):
        requests_log = logging.getLogger("urllib3")
        requests_log.setLevel(logging.DEBUG)
        requests_log.propagate = True

    with open(args.creds, encoding="utf-8") as file:
        if os.fstat(file.fileno()).st_mode & 0o77:
            sys.exit(f"ERROR: {args.creds} has insecure permissions")
        creds = json.load(file)

    print_issues(
        creds,
        args.url,
        args.time,
        args.fields,
        args.output,
        args.status,
        args.sort,
        args.reverse,
        args.user,
    )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
