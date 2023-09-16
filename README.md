![Build Status](https://github.com/ricardobranco777/bugme/actions/workflows/ci.yml/badge.svg)

# bugme

Show bug and issue status

Docker images available at:
- Alpine based using PyPI: `ghcr.io/ricardobranco777/bugme:latest`
- openSUSE based: `registry.opensuse.org/home/rbranco/bugme/containerfile/bugme`

Supported:
- bsc#: SUSE's Bugzilla
- gh#: Github
- gl#: Gitlab
- gsd#: SUSE's Gitlab
- poo#: openSUSE's Redmine

## Usage

```
usage: bugme.py [-h] [-c CREDS] [-f FORMAT] [-l {debug,info,warning,error,critical}] [-o {text,json}] [-t TIME] [--version] [url ...]

positional arguments:
  url

options:
  -h, --help            show this help message and exit
  -c CREDS, --creds CREDS
                        path to credentials file (default: ~/creds.json)
  -f FORMAT, --format FORMAT
                        output in Jinja2 format (default: None)
  -l {debug,info,warning,error,critical}, --log {debug,info,warning,error,critical}
                        log level (default: warning)
  -o {text,markdown,html,json}, --output {text,markdown,html,json}
                        output type (default: text)
  -t TIME, --time TIME  strftime format (default: timeago)
  --version             show program's version number and exit
```

## Example

Copy [creds-example.json](creds-example.json) to `~/creds.json` and run.

```
$ podman run --rm -v ~/creds.json:/root/creds.json:ro bugme bsc#1213811 gh#containers/podman#19529 poo#133910 gl#gitlab-org/gitlab#424503 gsd#qac/container-release-bot#7
URL                                                                     STATUS      UPDATED                         TITLE
https://bugzilla.suse.com/show_bug.cgi?id=1213811                       NEW         Tue Sep 05 16:21:37 CEST 2023   podman network unreachable after starting docker
https://github.com/containers/podman/issues/19529                       closed      Tue Aug 08 08:56:56 CEST 2023   Unexpected error with --volumes-from
https://progress.opensuse.org/issues/133910                             Resolved    Thu Aug 17 08:50:53 CEST 2023   We need a suite of tests to check volume operations in container runtimes
https://gitlab.com/gitlab-org/gitlab/-/issues/424503                    opened      Fri Sep 08 18:46:24 CEST 2023   Prepare UI/UX when monetisation transition period ends (cut-off)
https://gitlab.suse.de/qac/container-release-bot/-/issues/7             opened      Thu Sep 15 15:57:32 CEST 2022   Explore new schedule options
```

## Requirements

- Docker or Podman to run the Docker image.
- Python 3.11+ and [requirements](requirements-dev.txt) to run stand-alone.
