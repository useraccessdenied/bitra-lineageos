# 17 — Droidian bring-up #3–#6 (2026-11-18): UI, touch, audio, radios, Wi-Fi

State: Phosh runs on the device (hwcomposer/libhybris, stock A13 vendor, Android 11 GSI container). Everything below is in
`scripts/build_droidian_install.py` (rootfs patches via rootless `debugfs -w`) and `scripts/audio_sanitize.py`.
Latest image: `releases/droidian-install/userdata.img` (see SHA256SUMS; not tracked). User-verified on the phone unless marked.

## Fixed / working
| Area | Cause | Fix |
|---|---|---|
| Touch dead in Phosh | Oplus touchpanel declared ABS_MT_WIDTH_MAJOR/PRESSURE via `set_bit()` only (range 0..0); libinput rejects it | Kernel: `input_set_abs_params()` for both axes in `touchpanel_common_driver.c` (branch `droidian`) |
| Touch dead until screen off/on | plymouth modeset sends DRM blank=1 to the touchpanel notifier (tp suspend), never UNBLANK | `bitra-touch-resume.service`: after phosh is up, `echo 1 > /sys/kernel/oplus_display/notify_panel_blank` (6 s and 10 s) — verified |
| Audio (no mic/speaker) | `module-droid-card` could not parse stock `audio_policy_configuration.xml` (xi:include of missing `/odm/etc/virtual_audio_policy_configuration.xml`); audio HAL service never started in the container | `scripts/audio_sanitize.py`: inlined policy overlay at `/odm/etc` + `bitra-audio-hal` init rc — verified, speaker + mic work |
| Bluetooth after boot | adapter stays down until HAL settles | `bitra-bt-recover.service` (retry power-on, restart bluebinder/bluetooth once), `bluebinder` RestartSec=3 — partly (see open) |
| Cellular offline | modem not Online at boot | `bitra-modem-online.service` (busctl SetProperty Online on /ril_0,/ril_1) |
| Device name "Kona for arm64" | first-boot runonce takes `ro.product.vendor.model` | `preferred-hostname`, `/etc/machine-info`, BT `main.conf` Name = "Droidian for Bitra" |
| Auto-brightness far too dim | ALS under the OLED reads low (~300 lux in a lit room) | gsettings override `ambient-brightness-points={1: 12, 20: 35, 100: 62, 300: 85, 1000: 95, 3000: 100}` (compiled into gschemas) — user: optimal |
| No crash logs after hang | Droidian ships journald `Storage=volatile`; pstore empty | `/etc/systemd/journald.conf.d/10-journald-volatile.conf` override (persistent) |
| Wi-Fi connected, no internet | NetworkManager l3cfg: `unable to configure IPv4 route` (subnet + default) although `ip route add` works | WORKAROUND `bitra-net-watch.service` (3 s poll, adds subnet + default via DHCP gateway) — works |

## Open / known
- **Wi-Fi route workaround is dirty.** Real cause unknown: NM fails ~10 s after DHCP, during a system stall (rpmh "TCS Busy" spam); netmgrd/ipacm run in the shared netns; ip rule 220 origin unknown. Replace the poller once understood. (An NM dispatcher script did not fix it.)
- **Bluetooth**: Settings toggle off→on does not power on, Phosh QuickSettings toggle does (Settings probably goes via rfkill); remote devices see the MAC, not the name, although main.conf/Alias are set. Data needed: `rfkill list`, `bluetoothctl show`, `journalctl -u bluetooth -u bluebinder`. `bitra-collect` now gathers these (bt.txt, net.txt, power-gsettings.txt).
- **Splash**: plymouth logo vanishes after ~2 s, blank screen until Phosh. `plymouth quit --retain-splash` drop-in had no effect (likely hwcomposer re-initialising the panel). Cosmetic; skipped.
- Unexplained device hang during a manual audio-HAL start test (no log; persistent journal now on).
- Cellular "Default" connection fails: user has no data plan (ignore). Torch toggle, sensors, fingerprint, NFC untested.
- `bitra-usb-debug` (telnet) is a temporary debug service — remove before real use.
- Not yet a proper adaptation package; everything lives in the image-build script.

## Tips learned
- `lxc-attach` swallows stdin: use `</dev/null`; container lacks `ps`/`start` on PATH (`/system/bin/ps`).
- Stock `*_dlkm` modprobe (module_layout) failures are harmless.
- Shell choice: Phosh is the supported one; Lomiri possible later (needs Droidian packages/porting).
