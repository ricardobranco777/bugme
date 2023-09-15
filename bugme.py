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
from typing import Any, Generator

from jinja2 import Template

from scantags import scan_tags
from services import get_item, Item, MyBugzilla, MyGithub, MyGitlab, MyRedmine
from utils import dateit


VERSION = "1.9.1"

DEFAULT_CREDENTIALS_FILE = os.path.expanduser("~/creds.json")


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
        "-o",
        "--output",
        choices=["text", "markdown", "json"],
        default="text",
        help="output type",
    )
    argparser.add_argument("-t", "--time", default="timeago", help="strftime format")
    argparser.add_argument("--version", action="version", version=f"bugme {VERSION}")
    argparser.add_argument("url", nargs="*")
    return argparser.parse_args()


def get_items(
    creds: dict[str, dict[str, str]], urltags: list[str], time_format: str
) -> Generator[Item, None, None]:
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
        else:
            cls = host_to_cls[host]
        clients[host] = cls(host, creds[host])

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
                item.created = dateit(item.created, time_format)
                item.updated = dateit(item.updated, time_format)
                item.status = item.status.upper()
                yield item


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
    all_items = []
    keys = {
        "tag": "<40",
        "status": "<10",
        "updated": "<15",
        "title": "",
    }

    # Print header
    if output_format is None:
        output_format = "  ".join(
            f'{{{{"{{:{align}}}".format({key})}}}}' for key, align in keys.items()
        )
    if output_type == "markdown":
        print("| " + " | ".join(key.upper() for key in keys) + " |")
        print("| " + " | ".join("---" for key in keys) + " |")

    xtags = {}
    if not urltags:
        xtags = scan_tags()
        urltags = list(xtags.keys())

    for item in get_items(creds, urltags, time_format):
        if output_type == "json":
            all_items.append(item.__dict__)
        elif output_type == "markdown":
            tag = item.tag
            item.tag = f"[{item.tag}]({item.url})"
            item.title = item.title.replace("|", r"'\|")
            print("| " + " | ".join(item[key] for key in keys) + " |")
            if tag in xtags:
                for info in xtags[tag]:
                    print(
                        f'| | {info["author"]} | [{info["file"]}:{info["lineno"]}]({info["url"]}) | |'
                    )
        else:
            print(Template(output_format).render(item.__dict__))
            if item.tag in xtags:
                for info in xtags[item.tag]:
                    print(
                        "\t".join(
                            [info["author"], info["file"], info["lineno"], info["url"]]
                        )
                    )

    if output_type == "json":
        print(json.dumps(all_items, default=str, sort_keys=True))


def main():
    """
    Main function
    """
    with open(args.creds, encoding="utf-8") as file:
        if os.fstat(file.fileno()).st_mode & 0o77:
            sys.exit(f"ERROR: {args.creds} has insecure permissions")
        creds = json.load(file)

    print_items(creds, args.url, args.time, args.format, args.output)


if __name__ == "__main__":
    args = parse_args()
    if args.format and args.output != "text":
        sys.exit(f"ERROR: The --format option is not valid for output {args.output}")
    logging.basicConfig(
        format="%(levelname)-8s %(message)s", stream=sys.stderr, level=args.log.upper()
    )
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
