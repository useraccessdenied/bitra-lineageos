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
- **Wi-Fi routes: ROOT CAUSE FOUND (see below); kernel fix verified by RAM boot, not yet flashed.** `bitra-net-watch` is only a stop-gap until the fixed kernel is flashed.
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

## Wi-Fi route root cause (2026-11-18, found with bitra-agent)
- NM trace (`nmcli general logging level TRACE domains PLATFORM,IP4`, then `nmcli device reapply`): `do-add-ip4-route[192.168.1.0/24 dev wlan0 ... scope link]: failure 101 (Network is unreachable - Nexthop has invalid gateway)`; the default route then fails for lack of the on-link route. NM retries failed objects after 10 s (the "10 s gap" and the late warning).
- That kernel message only comes from the gateway branch of `fib_check_nh()` (net/ipv4/fib_semantics.c). A raw netlink replay (scratch script, veth pair) showed a subnet route with the NM message shape is accepted, but the same request with `RTA_GATEWAY=0.0.0.0` fails with exactly -101. This 4.19 tree has the 5.x-style `fc_gw_family` handling (set whenever the attribute is present), so a zero gateway is looked up as a real nexthop and fails unless some default route already exists (which is why it was timing dependent: it worked when e.g. a cellular default route was up).
- Fix: `net/ipv4/fib_frontend.c` `rtm_to_fib_config()`: ignore an all-zero `RTA_GATEWAY` (pre-5.2 semantics). Kernel branch `droidian`. Verified: two RAM boots (`ramboot`) with `bitra-net-watch` disabled: NM installs `192.168.1.0/24` and the default route itself, 0 "unable to configure IPv4 route" warnings.
- NM itself was never seen emitting the zero gateway (no strace on the phone); the evidence is the identical error from the replay plus the fix working.
- Side findings: (1) udev sometimes renames `wlan0` to `wlp1s0` (predictable names, race; p2p0/wifi-aware0 collide) - `bitra-net-watch` is hard-coded to wlan0; consider `net.ifnames=0` or a .link file. (2) `example.com` does not resolve on the user's home router (UDP DNS to the router/1.1.1.1/8.8.8.8 all time out for that name only); other names, NTP and HTTPS work. Not a phone bug.
- Next: flash boot-gz.img (`ssh mac flash boot ...`), then drop `bitra-net-watch` from scripts/build_droidian_install.py.
