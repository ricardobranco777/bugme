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
from concurrent.futures import ThreadPoolExecutor
from operator import itemgetter
from typing import Any

from scantags import scan_tags
from services import get_item, Item, MyBugzilla, MyGithub, MyGitlab, MyJira, MyRedmine
from utils import dateit, html_tag


VERSION = "1.9.5"

DEFAULT_CREDENTIALS_FILE = os.path.expanduser("~/creds.json")


def parse_args() -> argparse.Namespace:
    """
    Parse command line options
    """
    argparser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        epilog="output fields for --fields: tag,url,status,created,updated,title",
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


def get_items(  # pylint: disable=too-many-locals
    creds: dict[str, dict[str, str]],
    urltags: list[str],
    statuses: list[str] | None,
    output_type: str,
) -> list[Item]:
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
        host_items[item["host"]].append(item)

    host_to_cls = {
        "github.com": MyGithub,
        "progress.opensuse.org": MyRedmine,
    }
    options = {
        MyBugzilla: {
            "force_rest": True,
            "sslverify": os.environ.get("REQUESTS_CA_BUNDLE", True),
            "include_fields": "id status summary creation_time last_change_time".split()
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
        cls: Any = None
        if host.startswith("bugzilla"):
            cls = MyBugzilla
        elif host.startswith("gitlab"):
            cls = MyGitlab
        elif host.startswith("jira"):
            cls = MyJira
        else:
            cls = host_to_cls[host]
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
        print(html_tag("tr", cells))
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
            info["date"] = dateit(info["date"], time_format)  # type: ignore
            print(f'\t{info["email"]}\t{info["date"]}\t{info["url"]}')


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
        xtags = scan_tags()
        urltags = list(xtags.keys())
    items = get_items(creds, urltags, statuses, output_type)

    fields = dict.fromkeys(output_format.split(","), 0)

    if output_type == "text":
        for item in items:
            fields.update(
                {
                    field: max(width, len(item[field]))
                    for field, width in fields.items()
                    if field not in {"created", "updated"}
                }
            )
        for field in set(fields.keys()) & {"created", "updated"}:
            fields.update(
                {
                    field: 15 if time_format == "timeago" else 35,
                }
            )

    output_format = "  ".join(
        f"{{{field}:<{align}}}" for field, align in fields.items()
    )
    print_header(output_type, output_format, fields)

    if sort_key in {"tag", "url"}:
        items.sort(key=Item.sort_key, reverse=reverse)
    elif sort_key is not None:
        items.sort(key=itemgetter(sort_key), reverse=reverse)  # type:ignore

    for item in items:
        item.created = dateit(item.created, time_format)
        item.updated = dateit(item.updated, time_format)
        item.files = xtags.get(item.tag, [])
        print_item(item, output_type, output_format, time_format, fields)

    if output_type == "html":
        print("</tbody></table>")
    elif output_type == "json":
        print(json.dumps([it.__dict__ for it in items], sort_keys=True))


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
