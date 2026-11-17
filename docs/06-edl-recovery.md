# 06 — EDL (Qualcomm 9008) recovery on Linux

Findings 2026-11-09. Both tools exist and are actively maintained:

| Tool | Repo | Last push | Notes |
|---|---|---|---|
| **qdl** | github.com/linux-msm/qdl | 2026-11-05 | Official Linaro/linux-msm Firehose flasher in C; releases v2.9.1 (prebuilt Ubuntu x64 binary, also build from source). Takes `prog_*.elf` + rawprogram/patch XMLs. Not packaged in the repos I could query (dnf was not usable from here). |
| **edl** | github.com/bkerler/edl | 2026-09-19 | Python Sahara/Firehose/diag tool, v3.52.1. Has Oppo/Realme/OnePlus auth helpers (e.g. `edl --loader=... `), can dump/flash partitions, read GPT. |

Both need udev access to USB `05c6:9008` (Qualcomm HS-USB QDLoader 9008). No Qualcomm rules file is installed on this host (only mm-qcom-soc), so one is needed, e.g. `/etc/udev/rules.d/51-qcom-edl.rules`:
`SUBSYSTEM=="usb", ATTR{idVendor}=="05c6", ATTR{idProduct}=="9008", MODE="0660", TAG+="uaccess"`
(install with sudo, then `udevadm control --reload && udevadm trigger`).

## Our package
`firmware/EDL/` has `prog_firehose_ddr4_fwupdate.elf` and the 7.3 GB export zip (Android 13, `IMAGES/`, `RADIO/`). Open questions before a real recovery:
1. The zip is an "export"/OTA-style layout. Check for `rawprogram*.xml`/`patch*.xml` (qdl needs them); if absent, flash partitions by name with `edl` (`edl w <part> <img>`), or regenerate XMLs from the GPT.
2. Realme/Oppo devices usually need a **signed** programmer and may require OEM auth (VIP/digest) for most firehose commands. Unverified whether this `prog_firehose_ddr4_fwupdate.elf` is accepted by your unit without auth.
3. Which DDR type the unit has (ddr4 vs ddr5 images exist in firmware zips: xbl_ddr4/ddr5) — this programmer is DDR4.

Plan: install tools into `bin/` (qdl build from source, edl via venv), write the udev rule, but do **not** try EDL on the working phone — only test with `edl printgpt` equivalents when it is actually in 9008 mode.
