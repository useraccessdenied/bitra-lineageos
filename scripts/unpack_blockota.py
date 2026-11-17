#!/usr/bin/env python3
"""Unpack a block-based (new.dat.br + transfer.list) OTA zip into raw partition images. Read-only on the zip.
Usage: unpack_blockota.py ZIP OUTDIR [partition ...]   (default: all *.new.dat.br)
Handles transfer list v1-4 for full OTAs ('new', 'zero', 'erase'; no diffs). Needs a `brotli` binary
(host tool from the AOSP tree or system). Stdlib only."""
import re, shutil, subprocess, sys, zipfile, os
from pathlib import Path

BROTLI = shutil.which("brotli") or str(Path(__file__).resolve().parent.parent / "roms/lineageos/a16/out/host/linux-x86/bin/brotli")
BLOCK = 4096

def ranges(s):
    n = list(map(int, s.split(",")))
    assert n[0] == len(n) - 1
    return [(n[i], n[i + 1]) for i in range(1, len(n), 2)]

def unpack(zf, part, out: Path):
    tl = zf.read(f"{part}.transfer.list").decode().splitlines()
    ver = int(tl[0]); total = int(tl[1])
    skip = 4 if ver >= 2 else 2
    br = out / f"{part}.new.dat.br"; dat = out / f"{part}.new.dat"
    with zf.open(f"{part}.new.dat.br") as src, br.open("wb") as dst: shutil.copyfileobj(src, dst)
    subprocess.run([BROTLI, "-d", "-f", str(br), "-o", str(dat)], check=True); br.unlink()
    img = out / f"{part}.img"
    with dat.open("rb") as d, img.open("wb") as f:
        for line in tl[skip:]:
            cmd, _, arg = line.partition(" ")
            if cmd == "new":
                for a, b in ranges(arg):
                    f.seek(a * BLOCK); f.write(d.read((b - a) * BLOCK))
            elif cmd in ("zero", "erase"):
                for a, b in ranges(arg):
                    f.seek(a * BLOCK); f.write(b"\0" * ((b - a) * BLOCK))
            elif cmd in ("bsdiff", "imgdiff", "move", "stash", "free"):
                sys.exit(f"{part}: unsupported command {cmd} (incremental OTA?)")
        f.truncate(total * BLOCK)
    dat.unlink()
    print(f"{part}: {img} {img.stat().st_size >> 20} MiB")

def main():
    if len(sys.argv) < 3: sys.exit(__doc__)
    z, out = Path(sys.argv[1]), Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
    zf = zipfile.ZipFile(z)
    parts = sys.argv[3:] or sorted(re.match(r"(.+)\.new\.dat\.br$", n)[1] for n in zf.namelist() if n.endswith(".new.dat.br"))
    for p in parts: unpack(zf, p, out)

if __name__ == "__main__":
    main()
