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
ROOTFS_SIZE = "32G"    # sparse; Droidian's installer uses 8G, but with GNOME runtimes preinstalled that is 100% full on day one
USERDATA_SIZE = "40G"  # sparse; the initrd should grow it to the partition on first boot (see halium resize patch below)

CMDLINE = ("console=ttyMSM0,115200n8 earlycon=msm_geni_serial,0xa90000 androidboot.hardware=qcom "
           "androidboot.console=ttyMSM0 androidboot.memcg=1 lpm_levels.sleep_disabled=1 "
           "video=vfb:640x400,bpp=32,memsize=3072000 msm_rtb.filter=0x237 service_locator.enable=1 "
           "androidboot.usbcontroller=a600000.dwc3 swiotlb=2048 loop.max_part=7 "
           "cgroup.memory=nokmem,nosocket reboot=panic_warm kpti=off buildvariant=user "
           "printk.devkmsg=on loglevel=7 console=tty0 androidboot.selinux=permissive systemd.log_target=kmsg systemd.log_level=info")

USB_DEBUG_SH = r"""#!/bin/bash
# bitra bring-up (temporary): host-side USB CDC-NCM gadget + DHCP + unauthenticated root telnet.
# Early (sysinit.target) and independent of the Android container / android-mount.service.
# REMOVE before any real use (no authentication!).
BB=/usr/local/sbin/busybox-bitra
G=/sys/kernel/config/usb_gadget/g1
log() { echo "bitra-usb-debug: $*" > /dev/kmsg; }
mountpoint -q /sys/kernel/config || mount -t configfs none /sys/kernel/config
if [ -d $G ] && [ -n "$(cat $G/UDC 2>/dev/null)" ] && [ -d /sys/class/net/usb0 ]; then
    log "gadget already bound (created by the initramfs); reusing it"
else
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
    log "gadget created"
fi
$BB ifconfig usb0 192.168.2.15 netmask 255.255.255.0 up
$BB ifconfig usb0:1 10.15.19.82 netmask 255.255.255.0 up 2>/dev/null
printf 'start 192.168.2.20\nend 192.168.2.30\ninterface usb0\nlease_file /run/bitra-udhcpd.leases\noption subnet 255.255.255.0\n' > /run/bitra-udhcpd.conf
touch /run/bitra-udhcpd.leases
$BB udhcpd /run/bitra-udhcpd.conf
$BB telnetd -b 0.0.0.0:23 -l /bin/bash
log "up: usb0 192.168.2.15 (+10.15.19.82), telnet :23"
exit 0
"""
USB_DEBUG_UNIT = """[Unit]
Description=bitra bring-up USB NCM gadget + debug telnet (temporary)
DefaultDependencies=no
After=systemd-remount-fs.service
Before=sysinit.target

[Service]
Type=oneshot
RemainAfterExit=yes
TimeoutStartSec=90
ExecStart=/usr/sbin/bitra-usb-debug

[Install]
WantedBy=sysinit.target
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


DBG_INIT = r"""#!/bin/sh
# bitra: interactive bisect init. Brings up the USB NCM shell, then WAITS. The real Droidian init is /init.droidian.
export PATH=/sbin:/usr/sbin:/bin:/usr/bin
mkdir -p /sys /proc /dev /tmp /run
mount -t sysfs sysfs /sys; mount -t proc proc /proc
mount -t devtmpfs devtmpfs /dev; mkdir -p /dev/pts; mount -t devpts devpts /dev/pts
mount -t tmpfs tmpfs /run
echo "bitra: dbg init, starting gadget" > /dev/kmsg
/scripts/init-premount/bitra-usb
echo "bitra: gadget done; shell on 192.168.2.15:23. Run: sh -x /init.droidian > /tmp/d.log 2>&1 &" > /dev/kmsg
while true; do echo "bitra: dbg alive $(cut -d' ' -f1 /proc/uptime)" > /dev/kmsg; sleep 10; done
"""


COLLECT_SH = r"""#!/bin/bash
# bitra: collect bring-up logs into /tmp/bringup.tgz (then send to the Mac, see end of output)
D=/tmp/bringup; rm -rf $D; mkdir -p $D
dmesg > $D/dmesg.txt
journalctl -b --no-pager > $D/journal.txt
systemctl --failed --no-pager > $D/failed.txt
systemctl list-units --no-pager > $D/units.txt
mount > $D/mounts.txt
ps aux > $D/ps.txt
lxc-ls -f > $D/lxc.txt 2>&1
A="lxc-attach -n android --"
$A /system/bin/logcat -d -b all > $D/logcat.txt 2>&1
$A /system/bin/getprop > $D/getprop.txt 2>&1
$A /system/bin/ls -l /dev/dri /dev/kgsl-3d0 /dev/graphics > $D/gfxdev.txt 2>&1
$A /system/bin/cat /proc/self/cgroup > $D/cgroup.txt 2>&1
{ ip addr; echo; ip -4 route; echo; ip rule; echo; nmcli -f all device show wlan0; nmcli con show; } > $D/net.txt 2>&1
{ rfkill list; echo; bluetoothctl show; echo; bluetoothctl devices; echo; systemctl status bluetooth bluebinder bitra-bt-recover --no-pager; } > $D/bt.txt 2>&1
gsettings list-recursively org.gnome.settings-daemon.plugins.power > $D/power-gsettings.txt 2>&1
journalctl -b --no-pager -u bitra-bt-recover -u bluetooth -u bluebinder > $D/bitra-units.txt 2>&1
tar czf /tmp/bringup.tgz -C $D .
echo "done: /tmp/bringup.tgz ($(stat -c %s /tmp/bringup.tgz) bytes)"
echo "send:  Mac: nc -l 9000 > bringup.tgz     phone: /usr/local/sbin/busybox-bitra nc <mac-ip> 9000 < /tmp/bringup.tgz"
"""

UDEV_RULES = """# bitra: device nodes libhybris (running as the droidian user) needs; normally shipped by the adaptation package
ACTION=="add", KERNEL=="ion", MODE="0666"
ACTION=="add", KERNEL=="kgsl-3d0", MODE="0666"
ACTION=="add", KERNEL=="kgsl", MODE="0666"
"""

DEVNAME = "Droidian for Bitra"

BT_RECOVER = r"""#!/bin/sh
# bitra: bluetooth comes up before the vendor HAL has settled after boot (HAL restarts once) -> adapter stays down.
# Retry power-on for up to ~2 min; if still failing, restart bluebinder+bluetooth once.
for i in $(seq 1 24); do
    bluetoothctl show 2>/dev/null | grep -q "Powered: yes" && exit 0
    bluetoothctl power on >/dev/null 2>&1
    sleep 5
    if [ "$i" = 8 ]; then systemctl restart bluebinder; sleep 8; systemctl restart bluetooth; sleep 4; fi
done
exit 0
"""
BT_RECOVER_UNIT = """[Unit]
Description=bitra: make sure Bluetooth powers on after boot
After=bluetooth.service bluebinder.service

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/bitra-bt-recover

[Install]
WantedBy=graphical.target
"""
MODEM_ONLINE = r"""#!/bin/sh
# bitra: oFono modems come up Online=false at boot; set Online=true once the RIL modems exist.
# Then force the preferred radio technology: at boot oFono reports TechnologyPreference "umts" (2G/3G, no LTE) no
# matter what is saved, the modem first registers on LTE and then falls back to GSM ~15 s later. Apply "lte"
# (= LTE preferred, falling back to 3G/2G), or whatever /etc/bitra-modem-pref contains (any|gsm|umts|lte).
PREF=lte
[ -r /etc/bitra-modem-pref ] && PREF=$(head -n1 /etc/bitra-modem-pref)
for i in $(seq 1 60); do
    ok=0
    for m in /ril_0 /ril_1; do
        busctl --system call org.ofono $m org.ofono.Modem SetProperty sv Online b true >/dev/null 2>&1 && ok=$((ok+1))
    done
    if [ "$ok" -ge 1 ]; then
        sleep 10
        for m in /ril_0 /ril_1; do busctl --system call org.ofono $m org.ofono.Modem SetProperty sv Online b true >/dev/null 2>&1; done
        for j in $(seq 1 30); do
            busctl --system call org.ofono /ril_0 org.ofono.RadioSettings SetProperty sv TechnologyPreference s "$PREF" >/dev/null 2>&1 && break
            sleep 2
        done
        exit 0
    fi
    sleep 5
done
exit 0
"""
MODEM_ONLINE_UNIT = """[Unit]
Description=bitra: set cellular modems Online at boot
After=ofono.service ofono2mm.service

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/bitra-modem-online

[Install]
WantedBy=graphical.target
"""
TOUCH_RESUME = r"""#!/bin/sh
# bitra: early in boot (plymouth modeset) the Oplus touchpanel driver gets a blank=POWERDOWN notifier and is suspended;
# no UNBLANK notifier follows, so touch stays dead until the first real screen off/on. Send the UNBLANK ourselves.
N=/sys/kernel/oplus_display/notify_panel_blank
[ -w "$N" ] || exit 0
for i in $(seq 1 60); do systemctl is-active --quiet phosh && break; sleep 1; done
for d in 6 10; do sleep $d; echo 1 > "$N"; done
exit 0
"""
TOUCH_RESUME_UNIT = """[Unit]
Description=bitra: resume the touchpanel after boot
After=phosh.service

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/bitra-touch-resume

[Install]
WantedBy=graphical.target
"""
WLAN_LINK = """# bitra: the cnss_pci Wi-Fi driver creates wlan0, p2p0 and wifi-aware0 together. With the default
# NamePolicy (...path) all three map to the same name "wlp1s0" and whichever udev worker is first wins,
# so wlan0 is randomly renamed. Droidian expects wlan0: keep the kernel names.
[Match]
OriginalName=wlan0 p2p0 wifi-aware0

[Link]
NamePolicy=keep
"""
PLYMOUTH_DROPIN = "[Service]\nExecStart=\nExecStart=-/usr/bin/plymouth quit --retain-splash\n"
HWC_PHOSH_DROPIN = """# bitra: Droidian's 20-phosh.conf has BindsTo=phosh.service (starts phosh, and stops the composer when phosh
# stops). Phosh's first start often exits within ~30 ms; the BindsTo stop then killed the composer and the
# restarted android-service waited its full 60 s (phoc at ~80 s instead of ~15 s). Wants= still starts phosh
# (BindsTo implied it) -- dropping BindsTo without a Wants= leaves phosh never started (black screen).
[Unit]
Wants=phosh.service
Before=phosh.service
"""
# Phosh/gmobile looks up the panel (and its cutouts) by device-tree compatible; this kernel's DT says
# "qcom,kona-mtp". The base rootfs' 50-notch.conf already overlays /var/lib/droidian/phosh-notch.
# Circle is deliberately larger than the camera hole (r=48 px at x=82,y=60): tuned on the device, r=28 and 38 still overlapped.
NOTCH_JSON = """{
  "name": "Realme GT Neo 2",
  "x-res": 1080,
  "y-res": 2400,
  "corner-radii": [80, 80, 80, 80],
  "width": 69,
  "height": 153,
  "cutouts" : [
    {
      "name": "camera",
      "path": "M 34 60  a 48 48 0 1 0 96 0  a 48 48 0 1 0 -96 0  Z"
    }
  ]
}
"""
# Oplus game optimiser HAL: SIGSEGV in FreqControl::releaseCpuAll() right at start, restarted by init every ~10 s
# (hundreds of crashes per boot). Nothing here uses it; same service block as the stock rc plus `disabled`
# (the overlay replaces the stock odm rc of the same name).
GAMEOPT_RC = """service gameopt_hal_service-1-0 /odm/bin/hw/vendor.oplus.hardware.gameopt-service
    class hal
    user system
    group system readproc root
    capabilities SYS_NICE
    interface vendor.oplus.hardware.gameopt.IGameOptHalService/default
    disabled
"""
PHOSH_RESTART_DROPIN = "[Service]\nRestartSec=1s\n"
BLUEBINDER_DROPIN = "[Service]\nRestartSec=3\n"

# Auto-brightness curve (lux -> %). The ALS sits under the OLED and reads low (~285 lux in a lit room, 6000+ with a torch),
# the default curve (0..1000 lux in 5 steps) therefore stays far too dim.
ALS_OVERRIDE = ("[org.gnome.settings-daemon.plugins.power]\n"
                "ambient-brightness-points={1: 12, 20: 35, 100: 62, 300: 85, 1000: 95, 3000: 100}\n")

TMPFILES = "w /sys/class/backlight/panel0-backlight/brightness - - - - 1600\n"

ODM_OVERLAY_BLOCK = """
# bitra: overlay with sanitized VINTF manifests (Android-11 libvintf cannot parse the stock Android-13 AIDL entries).
# Must run AFTER the fstab loop above, which mounts the real odm partition.
if [ -d /usr/lib/droid-odm-overlay ] && [ -n "${BIND_MOUNT_PATH}" ]; then
    echo "mounting bitra odm overlay"
    mount -t overlay overlay -o lowerdir=/usr/lib/droid-odm-overlay:${BIND_MOUNT_PATH}/odm ${BIND_MOUNT_PATH}/odm
fi
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
    if "bitra odm overlay" not in ma:
        ma = ma.rstrip("\n") + "\n" + ODM_OVERLAY_BLOCK
    tmp = WORK / "tmp"; tmp.mkdir(exist_ok=True)
    (tmp / "mount-android.sh").write_text(ma)
    (tmp / "bitra-usb-debug").write_text(USB_DEBUG_SH)
    (tmp / "bitra-collect").write_text(COLLECT_SH)
    (tmp / "bitra-usb-debug.service").write_text(USB_DEBUG_UNIT)
    (tmp / "70-bitra.rules").write_text(UDEV_RULES)
    (tmp / "bitra.conf").write_text(TMPFILES)
    shutil.copy(BUSYBOX, tmp / "busybox-bitra")
    cmds = []

    def put(local, dest, mode):
        d, n = os.path.split(dest)
        cmds.extend([f"cd {d}", f"rm {n}", f"write {local} {n}",
                     f"set_inode_field {n} mode 0{mode:o}", f"set_inode_field {n} uid 0", f"set_inode_field {n} gid 0"])
    cmds.append("mkdir /usr/local/sbin")
    for n, t in (("bitra-bt-recover", BT_RECOVER), ("bitra-modem-online", MODEM_ONLINE),
                 ("bitra-bt-recover.service", BT_RECOVER_UNIT), ("bitra-modem-online.service", MODEM_ONLINE_UNIT),
                 ("preferred-hostname", DEVNAME + "\n"), ("bluebinder-dropin.conf", BLUEBINDER_DROPIN),
                 ("bitra-touch-resume", TOUCH_RESUME), ("bitra-touch-resume.service", TOUCH_RESUME_UNIT),
                 ("plymouth-dropin.conf", PLYMOUTH_DROPIN), ("10-bitra-wlan.link", WLAN_LINK),
                 ("hwc-20-phosh.conf", HWC_PHOSH_DROPIN), ("phosh-zz-bitra.conf", PHOSH_RESTART_DROPIN),
                 ("qcom,kona-mtp.json", NOTCH_JSON), ("gameopt.rc", GAMEOPT_RC)):
        (tmp / n).write_text(t)
    cmds += ["mkdir /usr/lib/droidian/device", "mkdir /etc/systemd/system/bluebinder.service.d"]
    put(tmp / "preferred-hostname", "/usr/lib/droidian/device/preferred-hostname", 0o100644)
    put(tmp / "bluebinder-dropin.conf", "/etc/systemd/system/bluebinder.service.d/bitra.conf", 0o100644)
    put(tmp / "bitra-bt-recover", "/usr/local/sbin/bitra-bt-recover", 0o100755)
    put(tmp / "bitra-modem-online", "/usr/local/sbin/bitra-modem-online", 0o100755)
    put(tmp / "bitra-bt-recover.service", "/etc/systemd/system/bitra-bt-recover.service", 0o100644)
    put(tmp / "bitra-modem-online.service", "/etc/systemd/system/bitra-modem-online.service", 0o100644)
    cmds += ["mkdir /etc/systemd/network"]
    put(tmp / "10-bitra-wlan.link", "/etc/systemd/network/10-bitra-wlan.link", 0o100644)
    cmds += ["mkdir /etc/systemd/system/plymouth-quit.service.d"]
    put(tmp / "plymouth-dropin.conf", "/etc/systemd/system/plymouth-quit.service.d/bitra.conf", 0o100644)
    cmds += ["mkdir /etc/systemd/system/android-service@hwcomposer.service.d", "mkdir /etc/systemd/system/phosh.service.d"]
    put(tmp / "hwc-20-phosh.conf", "/etc/systemd/system/android-service@hwcomposer.service.d/20-phosh.conf", 0o100644)
    put(tmp / "phosh-zz-bitra.conf", "/etc/systemd/system/phosh.service.d/zz-bitra.conf", 0o100644)
    cmds += ["mkdir /var/lib/droidian", "mkdir /var/lib/droidian/phosh-notch"]
    put(tmp / "qcom,kona-mtp.json", "/var/lib/droidian/phosh-notch/qcom,kona-mtp.json", 0o100644)
    put(tmp / "bitra-touch-resume", "/usr/local/sbin/bitra-touch-resume", 0o100755)
    put(tmp / "bitra-touch-resume.service", "/etc/systemd/system/bitra-touch-resume.service", 0o100644)
    cmds += ["cd /etc/systemd/system/graphical.target.wants", "rm bitra-touch-resume.service",
             "symlink bitra-touch-resume.service /etc/systemd/system/bitra-touch-resume.service"]
    cmds += ["cd /etc/systemd/system/graphical.target.wants", "rm bitra-bt-recover.service", "rm bitra-modem-online.service",
             "symlink bitra-bt-recover.service /etc/systemd/system/bitra-bt-recover.service",
             "symlink bitra-modem-online.service /etc/systemd/system/bitra-modem-online.service"]
    put(tmp / "mount-android.sh", "/usr/sbin/mount-android.sh", 0o100755)
    # Bluetooth name: set it explicitly (the computed default is lost via bluebinder -> remote shows the MAC address)
    bt = debugfs_read(ROOTFS_SRC, "/etc/bluetooth/main.conf").decode()
    if "[General]\n" not in bt:
        sys.exit("bluetooth main.conf layout changed; update the patch")
    (tmp / "main.conf").write_text(bt.replace("[General]\n", f"[General]\nName = {DEVNAME}\n", 1))
    put(tmp / "main.conf", "/etc/bluetooth/main.conf", 0o100644)
    mi = debugfs_read(ROOTFS_SRC, "/etc/machine-info").decode().rstrip("\n") + f'\nPRETTY_HOSTNAME="{DEVNAME}"\n'
    (tmp / "machine-info").write_text(mi)
    put(tmp / "machine-info", "/etc/machine-info", 0o100644)
    # ofono2mm bug: KeyError 'PinRequired' when oFono has not published it yet -> modem stuck in "failed" (no IMEI/SIM in UI)
    mm = debugfs_read(ROOTFS_SRC, "/usr/lib/ofono2mm/ofono2mm/mm_modem.py").decode()
    bad = "self.ofono_interface_props['org.ofono.SimManager']['PinRequired'].value == 'none'"
    good = "self.ofono_interface_props['org.ofono.SimManager'].get('PinRequired', Variant('s', 'none')).value == 'none'"
    if bad not in mm:
        sys.exit("ofono2mm layout changed; update the patch")
    (tmp / "mm_modem.py").write_text(mm.replace(bad, good))
    put(tmp / "mm_modem.py", "/usr/lib/ofono2mm/ofono2mm/mm_modem.py", 0o100644)
    put(tmp / "bitra-usb-debug", "/usr/sbin/bitra-usb-debug", 0o100755)
    put(tmp / "busybox-bitra", "/usr/local/sbin/busybox-bitra", 0o100755)
    put(tmp / "bitra-collect", "/usr/local/sbin/bitra-collect", 0o100755)
    put(tmp / "70-bitra.rules", "/usr/lib/udev/rules.d/70-bitra.rules", 0o100644)
    put(tmp / "bitra.conf", "/etc/tmpfiles.d/bitra.conf", 0o100644)
    put(tmp / "bitra-usb-debug.service", "/etc/systemd/system/bitra-usb-debug.service", 0o100644)
    # sanitized VINTF overlays (run scripts/vintf_sanitize.py first)
    ov = WORK / "overlays"
    if ov.is_dir():
        targets = {"odm": "/usr/lib/droid-odm-overlay", "vendor": "/usr/lib/droid-vendor-overlay"}
        for kind, base in targets.items():
            kroot = ov / kind
            if not kroot.is_dir():
                continue
            seen = {base}
            cmds.append(f"mkdir {base}")
            for f in sorted(kroot.rglob("*")):
                rel = f.relative_to(kroot)
                if f.is_dir():
                    continue
                cur = base
                for part in [x for x in (base + "/" + str(rel)).split("/")[:-1][len(base.split("/")):] if x]:
                    cur += "/" + part
                    if cur not in seen:
                        cmds.append(f"mkdir {cur}"); seen.add(cur)
                d, n = os.path.split(base + "/" + str(rel))
                cmds.extend([f"cd {d}", f"rm {n}", f"write {f} {n}", f"set_inode_field {n} mode 0100644",
                             f"set_inode_field {n} uid 0", f"set_inode_field {n} gid 0"])
    # Wi-Fi: the qcacld driver requests wlan/qca_cld/WCNSS_qcom_cfg.ini; stock vendor points it at persist (absent here).
    # ueventd searches /odm/firmware before /vendor/firmware, so provide the OEM config through the odm overlay.
    wifi_ini = STOCK / "o-extract/odm/vendor/etc/wifi/WCNSS_qcom_cfg.ini"
    if wifi_ini.is_file():
        for d in ("/usr/lib/droid-odm-overlay", "/usr/lib/droid-odm-overlay/firmware", "/usr/lib/droid-odm-overlay/firmware/wlan",
                  "/usr/lib/droid-odm-overlay/firmware/wlan/qca_cld"):
            cmds.append(f"mkdir {d}")
        cmds.extend(["cd /usr/lib/droid-odm-overlay/firmware/wlan/qca_cld", "rm WCNSS_qcom_cfg.ini",
                     f"write {wifi_ini} WCNSS_qcom_cfg.ini", "set_inode_field WCNSS_qcom_cfg.ini mode 0100644",
                     "set_inode_field WCNSS_qcom_cfg.ini uid 0", "set_inode_field WCNSS_qcom_cfg.ini gid 0"])
    for d in ("/usr/lib/droid-odm-overlay", "/usr/lib/droid-odm-overlay/etc", "/usr/lib/droid-odm-overlay/etc/init"):
        cmds.append(f"mkdir {d}")
    put(tmp / "gameopt.rc", "/usr/lib/droid-odm-overlay/etc/init/vendor.oplus.hardware.gameopt-service.rc", 0o100644)
    # gsettings override + recompiled schema cache (glib-compile-schemas on the host)
    sd = tmp / "schemas"; shutil.rmtree(sd, ignore_errors=True); sd.mkdir()
    sch = "/usr/share/glib-2.0/schemas"
    for l in subprocess.run(["debugfs", "-R", f"ls -p {sch}", str(ROOTFS_SRC)], capture_output=True, text=True).stdout.splitlines():
        n = l.split("/")[5] if l.count("/") >= 6 else ""
        if n.endswith((".xml", ".override")):
            (sd / n).write_bytes(debugfs_read(ROOTFS_SRC, f"{sch}/{n}"))
    (sd / "90_bitra.gschema.override").write_text(ALS_OVERRIDE)
    run(["glib-compile-schemas", "--strict", sd])
    put(sd / "90_bitra.gschema.override", f"{sch}/90_bitra.gschema.override", 0o100644)
    put(sd / "gschemas.compiled", f"{sch}/gschemas.compiled", 0o100644)
    # persistent journal (crash analysis)
    cmds.append("mkdir /var/log/journal")
    # Droidian ships /usr/lib/systemd/journald.conf.d/10-journald-volatile.conf (Storage=volatile); same name in /etc wins
    (tmp / "10-journald-volatile.conf").write_text("[Journal]\nStorage=persistent\nSyncIntervalSec=5\nSystemMaxUse=256M\n")
    cmds.append("mkdir /etc/systemd/journald.conf.d")
    put(tmp / "10-journald-volatile.conf", "/etc/systemd/journald.conf.d/10-journald-volatile.conf", 0o100644)
    cmds += ["cd /etc/systemd/system/sysinit.target.wants", "rm bitra-usb-debug.service",
             "symlink bitra-usb-debug.service /etc/systemd/system/bitra-usb-debug.service"]
    (WORK / "debugfs.cmds").write_text("\n".join(cmds) + "\n")
    r = run(["debugfs", "-w", "-f", WORK / "debugfs.cmds", img], ok_codes=True)
    bad = [l for l in (r.stdout + r.stderr).splitlines() if "File not found" in l and "rm" not in l]
    run(["e2fsck", "-fn", img], ok_codes=True)
    print("rootfs patched:", img)


def stage_livepatch():
    """tar.gz that can be unpacked over / on the running phone (rootfs is writable): odm/vendor VINTF overlays + mount-android.sh"""
    import tarfile
    ov = WORK / "overlays"
    OUT.mkdir(parents=True, exist_ok=True)
    ma = debugfs_read(ROOTFS_SRC, "/usr/sbin/mount-android.sh").decode()
    key = '    dmsetup create --concise "$(parse-android-dynparts /dev/disk/by-partlabel/super)"\n'
    ma = ma.replace(key, key + ODM_SNIPPET).rstrip("\n") + "\n" + ODM_OVERLAY_BLOCK
    tmp = WORK / "tmp"; tmp.mkdir(exist_ok=True)
    (tmp / "mount-android.sh.new").write_text(ma)
    (tmp / "bitra-collect").write_text(COLLECT_SH)
    out = OUT / "vintf-live-patch.tgz"

    def filt(ti):
        ti.uid = ti.gid = 0; ti.uname = ti.gname = "root"; return ti
    with tarfile.open(out, "w:gz") as t:
        t.add(tmp / "mount-android.sh.new", arcname="usr/sbin/mount-android.sh", filter=lambda ti: (filt(ti), setattr(ti, "mode", 0o755))[0])
        t.add(tmp / "bitra-collect", arcname="usr/local/sbin/bitra-collect", filter=lambda ti: (filt(ti), setattr(ti, "mode", 0o755))[0])
        for kind, base in (("odm", "usr/lib/droid-odm-overlay"), ("vendor", "usr/lib/droid-vendor-overlay")):
            for f in sorted((ov / kind).rglob("*")) if (ov / kind).is_dir() else []:
                if f.is_file():
                    t.add(f, arcname=f"{base}/{f.relative_to(ov / kind)}", filter=lambda ti: (filt(ti), setattr(ti, "mode", 0o644))[0])
    print(f"livepatch: {out} ({out.stat().st_size} bytes) sha256 {sha(out)}")


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
    # resize_userdata_if_needed() only knows /dev/mmcblk* and /dev/disk*, but mountroot resolves the partition with
    # `readlink -f` -> /dev/sda11 on this UFS phone, so the userdata filesystem was never grown (stayed 14 GB of 242 GB).
    sd_case = ("\t/dev/sd*)\n\t\tpblocks=$(grep -w ${path#/dev/} /proc/partitions | awk {'print $3'})\n\t\t;;\n")
    hit = False
    for e in ents:
        if e[0] == "scripts/halium":
            s = e[2].decode()
            assert "\t/dev/disk*)\n" in s, "halium resize_userdata_if_needed layout changed"
            if "/dev/sd*)" not in s:
                s = s.replace("\t/dev/disk*)\n", sd_case + "\t/dev/disk*)\n", 1)
            e[2] = s.encode(); hit = True
    if not hit:
        sys.exit("scripts/halium not found in initramfs")
    # add the early gadget as the FIRST init-premount script
    tmpl = next(e for e in ents if e[0] == "scripts/init-premount/dropbear")
    f = list(tmpl[1]); f[0] = max(e[1][0] for e in ents) + 1; f[4] = 1
    ents.append(["scripts/init-premount/bitra-usb", f, PREMOUNT_GADGET.encode()])
    marker = b"mkdir -m 0755 /run/initramfs\n"
    for e in ents:
        if e[0] == "init":
            assert marker in e[2], "init layout changed"
            e[2] = e[2].replace(marker, marker + b'echo "bitra: early init hook" > /dev/kmsg\n( /scripts/init-premount/bitra-usb >/dev/kmsg 2>&1 & )\n', 1)
    rd = WORK / "initrd.img"
    with gzip.GzipFile(rd, "wb", mtime=0, compresslevel=6) as g:
        g.write(cpio_write(ents))
    # bisect variant: Droidian initramfs, but /init is our gadget+wait script; real init kept as /init.droidian
    dbg = [list(e) for e in ents]
    for e in dbg:
        if e[0] == "init":
            e[0] = "init.droidian"; orig = e
    f = list(orig[1]); f[0] = max(x[1][0] for x in dbg) + 1; f[4] = 1
    dbg.append(["init", f, DBG_INIT.encode()])
    rd2 = WORK / "initrd-dbg.img"
    with gzip.GzipFile(rd2, "wb", mtime=0, compresslevel=6) as g:
        g.write(cpio_write(dbg))
    run([sys.executable, MKBOOTIMG, "--header_version", "2", "--kernel", KERNEL, "--ramdisk", rd2, "--dtb", DTB,
         "--base", "0x0", "--kernel_offset", "0x8000", "--ramdisk_offset", "0x2100000", "--dtb_offset", "0x1f00000",
         "--tags_offset", "0x100", "--pagesize", "4096", "--os_version", "13.0.0", "--os_patch_level", "2024-10",
         "--cmdline", CMDLINE, "-o", OUT / "boot-dbg.img"])
    print("boot-dbg.img ok")
    for name, kern in (("boot.img", KERNEL), ("boot-gz.img", KERNEL.with_name("Image.gz"))):
      boot = OUT / name
      run([sys.executable, MKBOOTIMG, "--header_version", "2", "--kernel", kern, "--ramdisk", rd, "--dtb", DTB,
         "--base", "0x0", "--kernel_offset", "0x8000", "--ramdisk_offset", "0x2100000", "--dtb_offset", "0x1f00000",
           "--tags_offset", "0x100", "--pagesize", "4096", "--os_version", "13.0.0", "--os_patch_level", "2024-10",
           "--cmdline", CMDLINE, "-o", boot])
      print(f"{name} ok ({boot.stat().st_size >> 20} MiB)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stage", default="all", choices=["all", "super", "rootfs", "userdata", "boot", "livepatch"])
    a = ap.parse_args()
    st = ["super", "rootfs", "userdata", "boot"] if a.stage == "all" else [a.stage]
    for s in st:
        print(f"== {s}", flush=True)
        {"super": stage_super, "rootfs": stage_rootfs, "userdata": stage_userdata, "boot": stage_boot, "livepatch": stage_livepatch}[s]()
    sums = ""
    for n in ("boot.img", "boot-gz.img", "boot-dbg.img", "super.img", "userdata.img"):
        if (OUT / n).exists():
            sums += f"{sha(OUT / n)}  {n}\n"
    (OUT / "SHA256SUMS").write_text(sums)
    print(sums)


if __name__ == "__main__":
    main()
