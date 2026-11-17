#!/usr/bin/env python3
"""Build the Droidian install artifacts for bitra, rootless and host-native (stdlib only).

Inputs (already downloaded/built, see docs/14):
  downloads/droidian-ref/rootfs-api30/rootfs.img        official Droidian api30 rootfs (sha256 verified)
  downloads/droidian-ref/bahamut/boot.img               official Droidian boot image; only its initramfs is reused
  firmware/stock-a13/{vendor,odm}.raw                    stock vendor/odm (for super.img)
  roms/droidian/kernel-out/arch/arm64/boot/Image         our Halium/Droidian kernel
  releases/droidian-kernel/dtb                           dtb (same bytes Lineage uses)
Outputs in releases/droidian-install/:
  super.img      (lpmake, sparse; stock vendor+odm)         [stage "super"]
  userdata.img   (ext4 containing rootfs.img, sparse)        [stage "userdata"]
  boot.img       (our kernel + patched Droidian initramfs)   [stage "boot"]
Rootfs patches (applied with debugfs, no root, original download untouched):
  * bitra-usb-debug.service: host-side USB CDC-NCM gadget (macOS has no RNDIS), 10.15.19.82/24, udhcpd, busybox telnetd :23
  * mount-android.sh: expose dynamic partitions (odm, ...) as /dev/disk/by-partlabel/* so the fstab loop finds them
Initramfs patch: scripts/panic/telnet RNDIS -> NCM (so the initrd debug shell works from a Mac).

  python3 scripts/build_droidian_install.py [--stage all|super|rootfs|userdata|boot]
"""
import argparse, gzip, hashlib, io, os, shutil, stat, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOS = ROOT / "roms/lineageos/a16/out/host/linux-x86/bin"
OUT = ROOT / "releases/droidian-install"
WORK = ROOT / "roms/droidian/work"
ROOTFS_SRC = ROOT / "downloads/droidian-ref/rootfs-api30/rootfs.img"
BAHAMUT_BOOT = ROOT / "downloads/droidian-ref/bahamut/boot.img"
STOCK = ROOT / "firmware/stock-a13"
KERNEL = ROOT / "roms/droidian/kernel-out/arch/arm64/boot/Image"
DTB = ROOT / "releases/droidian-kernel/dtb"
BUSYBOX = ROOT / "roms/lineageos/a17/kernel/realme/sm8250/KernelSU/userspace/ksud/bin/aarch64/busybox"
MKBOOTIMG = ROOT / "roms/lineageos/a16/system/tools/mkbootimg/mkbootimg.py"
ROOTFS_SIZE = "8G"     # same as Droidian's recovery installer
USERDATA_SIZE = "14G"  # grows to fill the partition on first boot (initrd resize2fs)

CMDLINE = ("console=ttyMSM0,115200n8 earlycon=msm_geni_serial,0xa90000 androidboot.hardware=qcom "
           "androidboot.console=ttyMSM0 androidboot.memcg=1 lpm_levels.sleep_disabled=1 "
           "video=vfb:640x400,bpp=32,memsize=3072000 msm_rtb.filter=0x237 service_locator.enable=1 "
           "androidboot.usbcontroller=a600000.dwc3 swiotlb=2048 loop.max_part=7 "
           "cgroup.memory=nokmem,nosocket reboot=panic_warm kpti=off buildvariant=user "
           "printk.devkmsg=on loglevel=7 selinux=0 androidboot.selinux=permissive")

USB_DEBUG_SH = r"""#!/bin/bash
# bitra bring-up (temporary): host-side USB CDC-NCM gadget + DHCP + unauthenticated root telnet.
# Independent of the Android container. REMOVE before any real use (no authentication!).
BB=/usr/local/sbin/busybox-bitra
G=/sys/kernel/config/usb_gadget/g1
mountpoint -q /sys/kernel/config || mount -t configfs none /sys/kernel/config
mkdir -p $G
[ -n "$(cat $G/UDC 2>/dev/null)" ] && echo "" > $G/UDC
echo 0x1d6b > $G/idVendor
echo 0x0104 > $G/idProduct
mkdir -p $G/strings/0x409
echo "bitra" > $G/strings/0x409/manufacturer
echo "droidian-bitra" > $G/strings/0x409/product
echo "bitra0001" > $G/strings/0x409/serialnumber
rm -f $G/configs/c.1/* 2>/dev/null
mkdir -p $G/configs/c.1/strings/0x409 $G/functions/ncm.usb0
echo "NCM" > $G/configs/c.1/strings/0x409/configuration
ln -s $G/functions/ncm.usb0 $G/configs/c.1/ncm.usb0
for i in $(seq 1 30); do [ -n "$(ls /sys/class/udc 2>/dev/null)" ] && break; sleep 1; done
echo "$(ls /sys/class/udc | head -n1)" > $G/UDC
sleep 2
$BB ifconfig usb0 10.15.19.82 netmask 255.255.255.0 up
printf 'start 10.15.19.100\nend 10.15.19.110\ninterface usb0\nlease_file /run/bitra-udhcpd.leases\noption subnet 255.255.255.0\n' > /run/bitra-udhcpd.conf
touch /run/bitra-udhcpd.leases
$BB udhcpd /run/bitra-udhcpd.conf
$BB telnetd -b 0.0.0.0:23 -l /bin/bash
echo "bitra-usb-debug: up on usb0 10.15.19.82, telnet :23" > /dev/kmsg
"""
USB_DEBUG_UNIT = """[Unit]
Description=bitra bring-up USB NCM gadget + debug telnet (temporary)
After=local-fs.target sysinit.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/sbin/bitra-usb-debug

[Install]
WantedBy=multi-user.target
"""
ODM_SNIPPET = """    for dp in /dev/mapper/dynpart-*; do
        [ -e "$dp" ] || continue
        mkdir -p /dev/disk/by-partlabel
        [ -e "/dev/disk/by-partlabel/${dp##*/dynpart-}" ] || ln -s "$dp" "/dev/disk/by-partlabel/${dp##*/dynpart-}"
    done
"""


PREMOUNT_GADGET = r"""#!/bin/sh
# bitra: earliest possible USB CDC-NCM debug gadget in the Droidian initramfs (same recipe as debug-boot.img,
# which is known to enumerate on macOS). Runs before udev/mountroot so we get a shell even if boot hangs later.
PREREQ=""
prereqs() { echo "$PREREQ"; }
case "$1" in prereqs) prereqs; exit 0;; esac
echo "bitra-premount: starting USB NCM gadget" > /dev/kmsg
mkdir -p /config; mount -t configfs none /config
G=/config/usb_gadget/g1
mkdir -p $G
echo 0x1d6b > $G/idVendor
echo 0x0104 > $G/idProduct
mkdir -p $G/strings/0x409
echo bitra > $G/strings/0x409/manufacturer
echo droidian-initrd > $G/strings/0x409/product
echo bitra0001 > $G/strings/0x409/serialnumber
mkdir -p $G/configs/c.1/strings/0x409 $G/functions/ncm.usb0
echo NCM > $G/configs/c.1/strings/0x409/configuration
ln -s $G/functions/ncm.usb0 $G/configs/c.1/ncm.usb0
i=0
while [ -z "$(ls /sys/class/udc 2>/dev/null)" ] && [ $i -lt 20 ]; do sleep 1; i=$((i+1)); done
echo "$(ls /sys/class/udc | head -n1)" > $G/UDC
sleep 2
ifconfig usb0 192.168.2.15 netmask 255.255.255.0 up
printf 'start 192.168.2.20\nend 192.168.2.30\ninterface usb0\nlease_file /tmp/bitra-udhcpd.leases\noption subnet 255.255.255.0\n' > /tmp/bitra-udhcpd.conf
touch /tmp/bitra-udhcpd.leases
udhcpd /tmp/bitra-udhcpd.conf
telnetd -b 0.0.0.0:23 -l /bin/sh
echo "bitra-premount: usb0 192.168.2.15 telnet :23 up" > /dev/kmsg
exit 0
"""


def run(cmd, ok_codes=False):
    r = subprocess.run([str(c) for c in cmd], text=True, capture_output=True, stdin=subprocess.DEVNULL)
    if r.returncode and not ok_codes:
        sys.exit(f"FAILED: {' '.join(map(str, cmd))}\n{r.stdout}{r.stderr}")
    return r


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 22), b""):
            h.update(c)
    return h.hexdigest()


def debugfs_read(img, path):
    r = subprocess.run(["debugfs", "-R", f"cat {path}", str(img)], capture_output=True, stdin=subprocess.DEVNULL)
    if r.returncode or not r.stdout:
        sys.exit(f"cannot read {path} from {img}")
    return r.stdout


def stage_super():
    OUT.mkdir(parents=True, exist_ok=True)
    v, o = STOCK / "vendor.raw", STOCK / "odm.raw"
    cmd = [LOS / "lpmake", "--metadata-size", "65536", "--metadata-slots", "1", "--super-name", "super",
           "--device-size", "10200547328", "--alignment", "1048576", "--block-size", "4096",
           "--group", "qti_dynamic_partitions:10196353024",
           "--partition", f"vendor:readonly:{v.stat().st_size}:qti_dynamic_partitions",
           "--partition", f"odm:readonly:{o.stat().st_size}:qti_dynamic_partitions",
           "--image", f"vendor={v}", "--image", f"odm={o}", "--sparse", "--output", OUT / "super.img"]
    run(cmd)
    print("super.img ok")


def stage_rootfs():
    WORK.mkdir(parents=True, exist_ok=True)
    img = WORK / "rootfs.img"
    run(["cp", "--sparse=always", ROOTFS_SRC, img])
    run(["e2fsck", "-fy", img], ok_codes=True)
    run(["resize2fs", "-f", img, ROOTFS_SIZE])
    # patch mount-android.sh
    ma = debugfs_read(ROOTFS_SRC, "/usr/sbin/mount-android.sh").decode()
    key = '    dmsetup create --concise "$(parse-android-dynparts /dev/disk/by-partlabel/super)"\n'
    if key not in ma:
        sys.exit("mount-android.sh layout changed; update the patch")
    if "by-partlabel/${dp##" not in ma:
        ma = ma.replace(key, key + ODM_SNIPPET)
    tmp = WORK / "tmp"; tmp.mkdir(exist_ok=True)
    (tmp / "mount-android.sh").write_text(ma)
    (tmp / "bitra-usb-debug").write_text(USB_DEBUG_SH)
    (tmp / "bitra-usb-debug.service").write_text(USB_DEBUG_UNIT)
    shutil.copy(BUSYBOX, tmp / "busybox-bitra")
    cmds = []

    def put(local, dest, mode):
        d, n = os.path.split(dest)
        cmds.extend([f"cd {d}", f"rm {n}", f"write {local} {n}",
                     f"set_inode_field {n} mode 0{mode:o}", f"set_inode_field {n} uid 0", f"set_inode_field {n} gid 0"])
    cmds.append("mkdir /usr/local/sbin")
    put(tmp / "mount-android.sh", "/usr/sbin/mount-android.sh", 0o100755)
    put(tmp / "bitra-usb-debug", "/usr/sbin/bitra-usb-debug", 0o100755)
    put(tmp / "busybox-bitra", "/usr/local/sbin/busybox-bitra", 0o100755)
    put(tmp / "bitra-usb-debug.service", "/etc/systemd/system/bitra-usb-debug.service", 0o100644)
    cmds += ["cd /etc/systemd/system/multi-user.target.wants", "rm bitra-usb-debug.service",
             "symlink bitra-usb-debug.service /etc/systemd/system/bitra-usb-debug.service"]
    (WORK / "debugfs.cmds").write_text("\n".join(cmds) + "\n")
    r = run(["debugfs", "-w", "-f", WORK / "debugfs.cmds", img], ok_codes=True)
    bad = [l for l in (r.stdout + r.stderr).splitlines() if "File not found" in l and "rm" not in l]
    run(["e2fsck", "-fn", img], ok_codes=True)
    print("rootfs patched:", img)


def stage_userdata():
    img = WORK / "rootfs.img"
    if not img.exists():
        sys.exit("run --stage rootfs first")
    tree = WORK / "userdata-tree"
    shutil.rmtree(tree, ignore_errors=True); tree.mkdir(parents=True)
    run(["cp", "--sparse=always", img, tree / "rootfs.img"])
    # halium initramfs workaround (from Droidian's setup.sh)
    os.symlink("/halium-system/var/lib/lxc/android/android-rootfs.img", tree / "android-rootfs.img")
    raw = WORK / "userdata.raw"
    if raw.exists():
        raw.unlink()
    run(["truncate", "-s", USERDATA_SIZE, raw])
    run(["mke2fs", "-q", "-t", "ext4", "-O", "^metadata_csum,^64bit,^orphan_file", "-L", "userdata", "-d", tree, "-F", raw])
    OUT.mkdir(parents=True, exist_ok=True)
    run(["img2simg", raw, OUT / "userdata.img"])
    raw.unlink(); shutil.rmtree(tree, ignore_errors=True)
    print("userdata.img ok")


# ---- initramfs (newc cpio) patching -------------------------------------------------------------
def cpio_parse(data):
    ents, pos = [], 0
    while True:
        h = data[pos:pos + 110]
        assert h[:6] == b"070701", f"bad cpio magic at {pos}"
        f = [int(h[6 + 8 * i: 14 + 8 * i], 16) for i in range(13)]
        ino, mode, uid, gid, nlink, mtime, fsize, dmaj, dmin, rmaj, rmin, nsize, chk = f
        name = data[pos + 110: pos + 110 + nsize - 1].decode()
        pos = (pos + 110 + nsize + 3) & ~3
        body = data[pos: pos + fsize]
        pos = (pos + fsize + 3) & ~3
        if name == "TRAILER!!!":
            return ents
        ents.append([name, f, body])


def cpio_write(ents):
    out = io.BytesIO()

    def pad():
        out.write(b"\0" * ((4 - out.tell() % 4) % 4))
    for name, f, body in ents + [["TRAILER!!!", [0] * 13, b""]]:
        f = list(f); f[6] = len(body); f[11] = len(name) + 1
        out.write(b"070701" + b"".join(b"%08X" % v for v in f)); out.write(name.encode() + b"\0"); pad()
        out.write(body); pad()
    return out.getvalue()


def stage_boot():
    OUT.mkdir(parents=True, exist_ok=True)
    scratch = WORK / "bahamut-unpack"; shutil.rmtree(scratch, ignore_errors=True)
    run([LOS / "unpack_bootimg", "--boot_img", BAHAMUT_BOOT, "--out", scratch])
    ents = cpio_parse(gzip.decompress((scratch / "ramdisk").read_bytes()))
    hit = False
    for e in ents:
        if e[0] == "scripts/panic/telnet":
            s = e[2].decode()
            s = s.replace("mkdir $GADGET_DIR/g1/functions/rndis.usb0\n        mkdir $GADGET_DIR/g1/functions/rndis_bam.rndis",
                          "mkdir $GADGET_DIR/g1/functions/ncm.usb0")
            s = s.replace("ln -s $GADGET_DIR/g1/functions/rndis.usb0 $GADGET_DIR/g1/configs/c.1\n        ln -s $GADGET_DIR/g1/functions/rndis_bam.rndis $GADGET_DIR/g1/configs/c.1",
                          "ln -s $GADGET_DIR/g1/functions/ncm.usb0 $GADGET_DIR/g1/configs/c.1")
            assert "ncm.usb0" in s and "rndis_bam" not in s, "panic/telnet patch did not apply"
            e[2] = s.encode(); hit = True
    if not hit:
        sys.exit("scripts/panic/telnet not found in initramfs")
    # add the early gadget as the FIRST init-premount script
    tmpl = next(e for e in ents if e[0] == "scripts/init-premount/dropbear")
    f = list(tmpl[1]); f[0] = max(e[1][0] for e in ents) + 1; f[4] = 1
    ents.append(["scripts/init-premount/bitra-usb", f, PREMOUNT_GADGET.encode()])
    for e in ents:
        if e[0] == "scripts/init-premount/ORDER":
            e[2] = b'/scripts/init-premount/bitra-usb "$@"\n[ -e /conf/param.conf ] && . /conf/param.conf\n' + e[2]
    rd = WORK / "initrd.img"
    with gzip.GzipFile(rd, "wb", mtime=0, compresslevel=6) as g:
        g.write(cpio_write(ents))
    for name, kern in (("boot.img", KERNEL), ("boot-gz.img", KERNEL.with_name("Image.gz"))):
      boot = OUT / name
      run([sys.executable, MKBOOTIMG, "--header_version", "2", "--kernel", kern, "--ramdisk", rd, "--dtb", DTB,
         "--base", "0x0", "--kernel_offset", "0x8000", "--ramdisk_offset", "0x1000000", "--dtb_offset", "0x1f00000",
           "--tags_offset", "0x100", "--pagesize", "4096", "--os_version", "13.0.0", "--os_patch_level", "2024-10",
           "--cmdline", CMDLINE, "-o", boot])
      print(f"{name} ok ({boot.stat().st_size >> 20} MiB)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stage", default="all", choices=["all", "super", "rootfs", "userdata", "boot"])
    a = ap.parse_args()
    st = ["super", "rootfs", "userdata", "boot"] if a.stage == "all" else [a.stage]
    for s in st:
        print(f"== {s}", flush=True)
        {"super": stage_super, "rootfs": stage_rootfs, "userdata": stage_userdata, "boot": stage_boot}[s]()
    sums = ""
    for n in ("boot.img", "boot-gz.img", "super.img", "userdata.img"):
        if (OUT / n).exists():
            sums += f"{sha(OUT / n)}  {n}\n"
    (OUT / "SHA256SUMS").write_text(sums)
    print(sums)


if __name__ == "__main__":
    main()
