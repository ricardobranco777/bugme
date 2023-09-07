![Build Status](https://github.com/ricardobranco777/bugme/actions/workflows/ci.yml/badge.svg)

# bugme

Show bug and issue status

## Example usage

Copy [creds-example.json](creds-example.json) to `~/creds.json` and run.

```
$ ./bugme.py bsc#1213811 gh#containers/podman#19529 poo#133910
bsc#1213811     NEW             Tue Sep 05 16:21:37 CEST 2023   podman network unreachable after starting docker
gh#19529        closed          Tue Aug 08 10:56:56 CEST 2023   Unexpected error with --volumes-from
poo#133910      Resolved        Thu Aug 17 08:50:53 CEST 2023   We need a suite of tests to check volume operations in container runtimes
```

## Terminator plugin

Copy [terminator.py](terminator.py) to `~/.config/terminator/plugins/`

## Requirements

- Tested on Python 3.8+
- [requirements](requirements-dev.txt)
