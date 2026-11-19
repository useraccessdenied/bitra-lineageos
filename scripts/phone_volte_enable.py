#!/usr/bin/env python3
"""Enable VoLTE/IMS on the Droidian phone (run ON THE PHONE, as root; stdlib only; idempotent).

  python3 phone_volte_enable.py [--dry-run]

What it does (all of it is needed; found out on the Realme GT Neo 2, see docs/17):
  1. backs up the files of the packages it will upgrade to /root/volte-backup (tar + versions) -- rollback aid
  2. adds Droidian's `next-upgrade-gbinder` apt channel (signed with the phone's own Droidian key) PINNED TO PRIORITY 100,
     so only the packages named below ever come from it (the repo's origin is "Droidian", which the stock pin of 1002 would
     otherwise make win every upgrade)
  3. installs libgbinder/ofono/ofono-binder-plugin 1.1.25 + ofono-binder-plugin-ext-qti from it (HIDL Qualcomm IMS extension)
  4. sets `extPlugin = qti` in /etc/ofono/binder.conf
The image build (build_droidian_install.py) separately provides what must live in the rootfs: IImsRadio 1.7 in the VINTF overlay
(vintf_sanitize.py) and /usr/lib/droid-system-overlay/etc/init/init.disabled.rc without the imsdatadaemon/ims_rtp_daemon blocks.
Reboot afterwards. Check: busctl --system call org.ofono /ril_0 org.ofono.IpMultimediaSystem GetProperties
"""
import argparse, os, subprocess, sys, tarfile, time

REPO_URI = "http://droidian.g.droidian.org/next-upgrade-gbinder/"
SOURCES = f"""Types: deb
URIs: {REPO_URI}
Suites: trixie
Components: main
Signed-By: /etc/apt/trusted.gpg.d/droidian.gpg
"""
PREFS = """# bitra: keep the Droidian next-upgrade-gbinder channel (libgbinder/ofono/IMS plugin) opt-in: only explicitly named packages
Package: *
Pin: release l=Droidian (group-droidian-next-upgrade-gbinder channel)
Pin-Priority: 100
"""
GB = "1.1.45-1~git20260513155336.fad75da.next.upgrade.gbinder"
PKGS = {
    "libgbinder": GB, "libgbinder-tools": GB,
    "libgbinder-radio": "1.6.1-1~git20260513161926.ad6d438.next.upgrade.gbinder",
    "libofonobinderpluginext": "1.1.25-1~git20260513163533.9b9e8bd.next.upgrade.gbinder",
    "ofono-binder-plugin": "1.1.25-1~git20260513163533.9b9e8bd.next.upgrade.gbinder",
    "ofono": "1.29+git13-1~git20260513162426.22605f1.next.upgrade.gbinder",
    "ofono-scripts": "1.29+git13-1~git20260513162426.22605f1.next.upgrade.gbinder",
    "ofono-binder-plugin-ext-qti": "0.0.0+git20260513172526.599bb59.next.upgrade.gbinder",
}
CONF = "/etc/ofono/binder.conf"
BACKUP = "/root/volte-backup"
ENV = dict(os.environ, DEBIAN_FRONTEND="noninteractive")


def sh(cmd, check=True, **kw):
    r = subprocess.run(cmd, shell=isinstance(cmd, str), text=True, capture_output=True, stdin=subprocess.DEVNULL, env=ENV, **kw)
    if check and r.returncode:
        sys.exit(f"FAILED: {cmd}\n{r.stdout[-600:]}{r.stderr[-600:]}")
    return r


def installed(pkg):
    r = sh(["dpkg-query", "-W", "-f=${Version}", pkg], check=False)
    return r.stdout.strip() if r.returncode == 0 else None


def write(path, text, dry):
    if os.path.exists(path) and open(path).read() == text:
        print(f"ok      {path}")
        return
    print(f"write   {path}")
    if not dry:
        open(path, "w").write(text)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if os.geteuid() != 0:
        sys.exit("run as root")
    todo = {p: v for p, v in PKGS.items() if installed(p) != v}
    # 1. backup (only if something will change and no backup exists yet)
    if todo and not os.path.exists(f"{BACKUP}/ofono-gbinder-before.tgz"):
        print("backup  ->", BACKUP)
        if not a.dry_run:
            os.makedirs(BACKUP, exist_ok=True)
            names = [p for p in PKGS if installed(p) and p != "ofono-binder-plugin-ext-qti"] + ["ofono-configs-binder-common"]
            files = sorted({f for p in names for f in sh(["dpkg", "-L", p]).stdout.split() if os.path.isfile(f)})
            with tarfile.open(f"{BACKUP}/ofono-gbinder-before.tgz", "w:gz") as t:
                for f in files:
                    t.add(f)
            open(f"{BACKUP}/versions.txt", "w").write("\n".join(f"{p} {installed(p)}" for p in names) + "\n")
            if os.path.exists(CONF):
                open(f"{BACKUP}/binder.conf.orig", "w").write(open(CONF).read())
    # 2. repo + pin (pin file name sorts before 10-droidian: first match wins)
    write("/etc/apt/preferences.d/05-bitra-volte", PREFS, a.dry_run)
    write("/etc/apt/sources.list.d/bitra-volte.sources", SOURCES, a.dry_run)
    if todo:
        if a.dry_run:
            print("would apt-get update and install:", " ".join(f"{p}={v}" for p, v in todo.items()))
        else:
            sh(["apt-get", "update"], timeout=300)
            sh(["apt-get", "-s", "install", "--no-install-recommends"] + [f"{p}={v}" for p, v in todo.items()])
            r = sh(["apt-get", "install", "-y", "--no-install-recommends", "-o", "Dpkg::Options::=--force-confold"]
                   + [f"{p}={v}" for p, v in todo.items()], timeout=900)
            print(r.stdout[-400:])
    else:
        print("ok      packages already at the wanted versions")
    # 3. ofono config
    conf = open(CONF).read() if os.path.exists(CONF) else ""
    if "extPlugin" not in conf:
        print(f"edit    {CONF}: extPlugin = qti")
        if not a.dry_run:
            if "[slot1]" not in conf:
                sys.exit(f"{CONF} has no [slot1] section; add `extPlugin = qti` by hand")
            out, done = [], False
            for line in conf.splitlines():
                out.append(line)
                if line.strip() == "[slot1]" and not done:
                    out.append("extPlugin = qti"); done = True
            open(CONF, "w").write("\n".join(out) + "\n")
    else:
        print(f"ok      {CONF} has extPlugin")
    print("done -- reboot, then check IpMultimediaSystem (Registered/VoiceCapable/SmsCapable should be true on LTE)")


if __name__ == "__main__":
    main()
