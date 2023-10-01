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
from services import (
    get_item,
    Item,
    MyBugzilla,
    MyGithub,
    MyGitlab,
    MyJira,
    MyRedmine,
    guess_service,
)
from utils import dateit, html_tag


VERSION = "2.0.0"

DEFAULT_CREDENTIALS_FILE = os.path.expanduser("~/creds.json")


def parse_args() -> argparse.Namespace:
    """
    Parse command line options
    """
    argparser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        epilog="output fields for --fields: tag,url,status,created,updated,title,assignee,creator",
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
        default="warning",
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
        choices=["tag", "url", "status", "created", "updated"],
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
    argparser.add_argument("--version", action="version", version=f"bugme {VERSION}")
    argparser.add_argument("url", nargs="*")
    return argparser.parse_args()


def get_items(
    creds: dict[str, dict[str, str]],
    urltags: list[str],
    statuses: list[str] | None,
    output_type: str,
) -> list[Item]:
    """
    Get items
    """
    host_items: dict[str, list[dict]] = defaultdict(list)
    for urltag in urltags:
        item = get_item(urltag)
        if item is None:
            continue
        host_items[item["host"]].append(item)

    options = {
        MyBugzilla: {
            "force_rest": True,
            "sslverify": os.environ.get("REQUESTS_CA_BUNDLE", True),
            "include_fields": "id assigned_to creator status summary creation_time last_change_time".split()
            if output_type != "json"
            else None,
        },
        MyGithub: {},
        MyGitlab: {
            "ssl_verify": os.environ.get("REQUESTS_CA_BUNDLE", True),
        },
        MyRedmine: {
            "raise_attr_exception": False,
        },
        MyJira: {},
    }

    clients: dict[str, Any] = {}
    for host in host_items:
        cls = guess_service(host)
        if cls is None:
            logging.error("Unknown: %s", host)
            sys.exit(1)
        clients[host] = cls(host, creds[host], **options[cls])

    if len(clients) == 0:
        sys.exit(0)

    all_items = []
    with ThreadPoolExecutor(max_workers=len(clients)) as executor:
        iterator = executor.map(
            lambda host: clients[host].get_items(host_items[host]), clients
        )
        for items in iterator:
            all_items.extend(
                [
                    item
                    for item in items
                    if item is not None
                    and (statuses is None or item.status in set(statuses))
                ]
            )
    return all_items


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


def print_item(
    item: Item,
    output_type: str,
    output_format: str,
    time_format: str,
    fields: dict[str, int],
):
    """
    Print item
    """
    if output_type == "html":
        info = {
            field: html.escape(item[field])
            if isinstance(item[field], str)
            else item[field]
            for field in fields
        }
        info["tag"] = html_tag("a", item.tag, href=item.url)
        info["url"] = html_tag("a", item.url, href=item.url)
        cells = "".join(html_tag("td", info[field]) for field in fields)
        print(html_tag("tr", cells, **{"class": "info"}))
        for info in item.files:
            info = {
                k: html.escape(v) if isinstance(v, str) else v for k, v in info.items()
            }
            author = html_tag("a", info["author"], href=f'mailto:{info["email"]}')
            date = html_tag("a", dateit(info["date"], time_format), href=info["commit"])
            cells = (
                html_tag("td", "") * (len(fields) - 3)
                + html_tag("td", author)
                + html_tag("td", date)
                + html_tag("td", html_tag("a", info["file"], href=info["url"]))
            )
            print(html_tag("tr", cells))
    elif output_type == "text":
        print(output_format.format(**item.__dict__))
        for info in item.files:
            print(
                "\t"
                + "\t".join([info["email"], info["commit"].split("/")[-1], info["url"]])
            )


def print_items(  # pylint: disable=too-many-arguments
    creds: dict[str, dict[str, str]],
    urltags: list[str] | None,
    time_format: str,
    output_format: str,
    output_type: str,
    statuses: list[str] | None,
    sort_key: str | None,
    reverse: bool,
) -> None:
    """
    Print items
    """
    xtags = {}
    if not urltags:
        xtags = scan_tags(directory=".", token=creds["github.com"]["login_or_token"])
        urltags = list(xtags.keys())
    items = get_items(creds, urltags, statuses, output_type)

    if sort_key in {"tag", "url"}:
        items.sort(key=Item.sort_key, reverse=reverse)
    elif sort_key is not None:
        items.sort(
            key=lambda it: (it[sort_key], *it.sort_key()),  # type:ignore
            reverse=reverse,
        )

    fields = {field: len(field) for field in output_format.split(",")}
    for item in items:
        item.created = dateit(item.created, time_format)
        item.updated = dateit(item.updated, time_format)
        item.files = xtags.get(item.tag, [])
        if output_type == "text":
            fields |= {
                field: max(width, len(item[field]))
                for field, width in fields.items()
                if field != "title"
            }

    if output_type == "json":
        print(json.dumps([it.__dict__ for it in items], sort_keys=True))
        return

    output_format = "  ".join(f"{{{field}:{align}}}" for field, align in fields.items())
    print_header(output_type, output_format, fields)
    for item in items:
        print_item(item, output_type, output_format, time_format, fields)
    if output_type == "html":
        print("</tbody></table>")


def main():
    """
    Main function
    """
    with open(args.creds, encoding="utf-8") as file:
        if os.fstat(file.fileno()).st_mode & 0o77:
            sys.exit(f"ERROR: {args.creds} has insecure permissions")
        creds = json.load(file)

    print_items(
        creds,
        args.url,
        args.time,
        args.fields,
        args.output,
        args.status,
        args.sort,
        args.reverse,
    )


if __name__ == "__main__":
    args = parse_args()
    if args.log == "none":
        logging.disable()
    else:
        logging.basicConfig(
            format="%(levelname)-8s %(message)s",
            stream=sys.stderr,
            level=args.log.upper(),
        )
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
