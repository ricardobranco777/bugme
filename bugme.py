#!/usr/bin/env python3
"""
Bugme
"""

import argparse
import logging
import html
import os
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from operator import itemgetter
from typing import Any

from scantags import scan_tags
from services import get_item, Item, MyBugzilla, MyGithub, MyGitlab, MyJira, MyRedmine
from utils import dateit


VERSION = "1.9.4"

DEFAULT_CREDENTIALS_FILE = os.path.expanduser("~/creds.json")


def parse_args() -> argparse.Namespace:
    """
    Parse command line options
    """
    argparser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        epilog="output fields for --fields: tag,url,status,created,updated,title,json",
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
        choices=["debug", "info", "warning", "error", "critical"],
        default="warning",
        help="log level",
    )
    argparser.add_argument(
        "-o",
        "--output",
        choices=["text", "html"],
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
        "-t", "--time", default="timeago", metavar="TIME_FORMAT", help="strftime format"
    )
    argparser.add_argument("--version", action="version", version=f"bugme {VERSION}")
    argparser.add_argument("url", nargs="*")
    return argparser.parse_args()


def get_items(creds: dict[str, dict[str, str]], urltags: list[str]) -> list[Item]:
    """
    Get items
    """
    host_items: dict[str, list[dict]] = {}
    for urltag in urltags:
        item = get_item(urltag)
        if item is None:
            continue
        if item["host"] not in host_items:
            host_items[item["host"]] = []
        host_items[item["host"]].append(item.__dict__)

    host_to_cls = {
        "github.com": MyGithub,
        "progress.opensuse.org": MyRedmine,
    }

    clients: dict[str, Any] = {}
    for host in host_items:
        cls: Any = None
        if host.startswith("bugzilla"):
            cls = MyBugzilla
        elif host.startswith("gitlab"):
            cls = MyGitlab
        elif host.startswith("jira"):
            cls = MyJira
        else:
            cls = host_to_cls[host]
        clients[host] = cls(host, creds[host])

    if len(clients) == 0:
        sys.exit(0)

    all_items = []
    with ThreadPoolExecutor(max_workers=len(clients)) as executor:
        iterator = executor.map(
            lambda host: clients[host].get_items(host_items[host]), clients
        )
        for items in iterator:
            all_items.extend([it for it in items if it is not None])
    return all_items


def print_items(
    creds: dict[str, dict[str, str]],
    urltags: list[str] | None,
    time_format: str,
    output_format: str,
    output_type: str,
) -> None:
    """
    Print items
    """
    keys = {
        "tag": "<40",
        "url": "<60",
        "status": "<15",
        "created": "<15" if time_format == "timeago" else "<30",
        "updated": "<15" if time_format == "timeago" else "<30",
    }
    keys = {key: keys.get(key, "") for key in output_format.split(",")}

    # Print header
    if output_type == "html":
        header = "".join(f"<th>{key.upper()}</th>" for key in keys)
        print(f"<table><thead><tr>{header}</tr></thead><tbody>")
    else:
        output_format = "  ".join(f"{{{key}:{align}}}" for key, align in keys.items())
        if "json" not in keys:
            print(output_format.format(**{key: key.upper() for key in keys}))

    xtags = {}
    if not urltags:
        xtags = scan_tags()
        urltags = list(xtags.keys())

    items = get_items(creds, urltags)
    if args.sort in {"tag", "url"}:

        def sort_url(url: str) -> tuple[str, int]:
            base, item_id = re.split(r"([0-9]+)$", url)[:2]
            return base, int(item_id)

        items.sort(key=lambda it: sort_url(it["url"]), reverse=args.reverse)
    elif args.sort is not None:
        items.sort(key=itemgetter(args.sort), reverse=args.reverse)  # type:ignore

    for item in items:
        item.created = dateit(item.created, time_format)
        item.updated = dateit(item.updated, time_format)
        if output_type == "html":
            tag = item.tag
            item.tag = f'<a href="{item.url}">{item.tag}</a>'
            item.title = html.escape(item.title)
            tds = "".join(f"<td>{item[key]}</td>" for key in keys)
            print(f"<tr>{tds}</tr>")
            # print files in last column
            for info in xtags.get(tag, []):
                tds = "<td></td>" * (len(keys) - 1)
                href = f'<a href="{info["url"]}">{info["file"]} {info["lineno"]}</a>'
                print(f"<tr>{tds}<td>{href}</td></tr>")
        else:
            print(output_format.format(**item.__dict__))
            for info in xtags.get(item.tag, []):
                print("\t".join([info["file"], info["url"]]))

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

    print_items(creds, args.url, args.time, args.fields, args.output)


if __name__ == "__main__":
    args = parse_args()
    logging.basicConfig(
        format="%(levelname)-8s %(message)s", stream=sys.stderr, level=args.log.upper()
    )
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
