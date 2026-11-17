#!/usr/bin/env python3
"""List / extract members of a remote zip via HTTP Range requests (stdlib only; no full download).
  remote_zip.py URL                       # list members
  remote_zip.py URL --get NAME [--out DIR]  # extract one member
Treats the zip as untrusted data; extracted files go to --out (default: ./remote-zip-out)."""
import argparse, io, sys, urllib.request, zipfile
from pathlib import Path

class RangeFile(io.RawIOBase):
    def __init__(self, url):
        self.url, self.pos = url, 0
        r = urllib.request.urlopen(urllib.request.Request(url, headers={"Range": "bytes=0-0"}))
        self.size = int(r.headers["Content-Range"].split("/")[1]); r.close()
        self.final = r.geturl()
    def seekable(self): return True
    def readable(self): return True
    def tell(self): return self.pos
    def seek(self, off, whence=0):
        self.pos = off if whence == 0 else self.pos + off if whence == 1 else self.size + off
        return self.pos
    def read(self, n=-1):
        if n < 0 or self.pos + n > self.size: n = self.size - self.pos
        if n <= 0: return b""
        # block cache: fetch >= 4 MiB around the read so zipfile's many small reads cost few requests
        c0, c1 = getattr(self, "_c", (0, 0))
        if not (c0 <= self.pos and self.pos + n <= c1):
            start = self.pos; length = max(n, 4 << 20)
            if start + length > self.size: length = self.size - start
            req = urllib.request.Request(self.final, headers={"Range": f"bytes={start}-{start + length - 1}"})
            with urllib.request.urlopen(req, timeout=60) as r: self._buf = r.read()
            self._c = (start, start + len(self._buf)); c0 = start
        data = self._buf[self.pos - c0: self.pos - c0 + n]
        self.pos += len(data); return data
    def readinto(self, b):
        d = self.read(len(b)); b[:len(d)] = d; return len(d)

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("url"); ap.add_argument("--get"); ap.add_argument("--out", default="remote-zip-out")
a = ap.parse_args()
rf = RangeFile(a.url)
tail = min(rf.size, 8 << 20)   # central directory is at the end: prefetch it
rf.seek(rf.size - tail); rf.read(1); rf._c = (rf.size - tail, rf.size); rf._buf = urllib.request.urlopen(urllib.request.Request(rf.final, headers={"Range": f"bytes={rf.size - tail}-{rf.size - 1}"})).read()
z = zipfile.ZipFile(rf)
if not a.get:
    for i in z.infolist(): print(f"{i.file_size:>12}  {i.filename}")
else:
    info = z.getinfo(a.get); dest = Path(a.out) / Path(a.get).name; dest.parent.mkdir(parents=True, exist_ok=True)
    with z.open(info) as s, dest.open("wb") as d:
        while chunk := s.read(1 << 20): d.write(chunk)
    print(dest, info.file_size)
