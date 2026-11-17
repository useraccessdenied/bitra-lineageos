#!/usr/bin/env bash
# Sync progress for a ROM dir. Usage: status.sh [dir=a16]
WS=/var/home/kapil/projects/bitra; D=$WS/roms/lineageos/${1:-a16}
total=$(cat $D/.repo/manifests/*.xml $D/.repo/local_manifests/*.xml 2>/dev/null | grep -c '<project ')
done_=$(find $D/.repo/project-objects -maxdepth 3 -name '*.git' 2>/dev/null | wc -l)
echo "projects with objects: $done_ / ~$total   size: $(du -sh $D/.repo 2>/dev/null | cut -f1)"
pgrep -f "repo/main.py.*sync" >/dev/null && echo "sync process: RUNNING" || echo "sync process: NOT running"
[ -f $D/.sync-complete ] && echo "SYNC COMPLETE"
echo "net rx now:"; a=$(awk '/:/ && $1!~/lo:/{s+=$2}END{print s}' /proc/net/dev); sleep 5; b=$(awk '/:/ && $1!~/lo:/{s+=$2}END{print s}' /proc/net/dev); echo "  $(( (b-a)/5/1024 )) KiB/s"
