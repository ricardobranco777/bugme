#!/bin/bash
#
# Scan a repo such as https://github.com/os-autoinst/os-autoinst-distri-opensuse for tags
#

if [[ $# -eq 0 || $# -gt 2 ]] ; then
	echo "Usage: $0 REPODIR [/path/to/creds.json]" >&2
	exit 1
fi

REPODIR="$1"
CREDS="${2:-"$HOME/creds.json"}"

IMAGE="${IMAGE:-registry.opensuse.org/home/rbranco/branches/devel/bci/tumbleweed/containerfile/bugme:latest}"
format="{{tag}} \t{{status}}\t{{url}}\t{{updated}}\t{{title}}"
format="$(echo -en "$format")"

command=(podman run --rm -v "$CREDS:$CREDS:ro" "$IMAGE" --creds "$CREDS" --format "$format")

set -eE

tmpfile="$(mktemp)"

cleanup() {
	rm -f "$tmpfile"
}

trap cleanup ERR EXIT HUP INT QUIT TERM

cd "$REPODIR"

declare -A tags

while read -r file tag ; do
	tags[$tag]+="$file "
done < <(find . -name \*.pm -exec grep -nEro -e '(bsc|poo|gh)#[0-9]+' -e 'gh#[^#]+#[0-9]+' {} + | sort -u | sed "s/:/ /")

"${command[@]}" "${!tags[@]}" > "$tmpfile" 2>&1

for tag in "${!tags[@]}" ; do
	grep -m1 "^$tag " "$tmpfile"
	for file in ${tags[$tag]} ; do
		echo -e "\t$file"
	done
done
