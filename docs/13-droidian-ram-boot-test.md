# 13 — Droidian stage 2: RAM-only boot test (Mac test machine)

Artifacts: `releases/droidian-debug/debug-boot.img` (58 MiB; our Droidian-config kernel + busybox initramfs, stock header-v2 offsets), `SHA256SUMS`.
Built by `python3 scripts/build_debug_initramfs.py`. Nothing is flashed: `fastboot boot` loads the image into RAM once; a reboot returns to the installed ROM.
The init brings up a USB **CDC-NCM** gadget (macOS-native, unlike RNDIS), vendor 1d6b:0104, product "halium-debug", serial "bitra0001", IP 192.168.2.15, shell on tcp/23 (`nc -e`) and busybox telnetd on tcp/2323.

## On the Mac
1. Copy the image over and verify: `shasum -a 256 debug-boot.img` must equal the line in SHA256SUMS.
2. Reboot the phone to the bootloader (from running Android: `adb reboot bootloader`), then `fastboot devices` and `fastboot getvar unlocked` (expect `yes`).
3. `fastboot boot debug-boot.img`  (if the bootloader answers "unknown command"/"not supported", tell me the exact text; do NOT flash anything.)
4. Wait 20-40 s, then look for the USB device:
   - `system_profiler SPUSBDataType | grep -B4 -A12 -i halium-debug`   (or `ioreg -p IOUSB -l -w0 | grep -i -A8 halium`)
   - GUI: Apple menu > hold Option > System Information > USB.
   - Network side: `networksetup -listallhardwareports` and `ifconfig -a` — a new `enN` interface appears with `status: active`.
5. Give the Mac an address and test: `sudo ifconfig enN 192.168.2.20 netmask 255.255.255.0 up` (replace enN) ; `ping -c3 192.168.2.15` ; `nc 192.168.2.15 23` -> a root shell (try `uname -a`, `cat /proc/cmdline`, `dmesg | tail -50`, `ls /sys/class/udc`).
6. Afterwards: long-press power (or `fastboot reboot`) to return to Lineage. If the phone rebooted by itself, boot Android and run `adb shell su -c "ls -l /sys/fs/pstore"`; the previous boot's kernel log (console-ramoops*) is the key debugging data — `adb shell su -c "cat /sys/fs/pstore/console-ramoops-0"`.

## What to report back
- Result of step 3 (exact fastboot output). 
- Did the screen show anything / did the phone reboot / hang?
- Does `halium-debug` show up in USB (vendor id 0x1d6b)? Does `ping` work?
- If no USB device: the pstore log from step 6.
