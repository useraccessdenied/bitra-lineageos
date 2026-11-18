#!/usr/bin/env python3
"""Audio overlays for Droidian on bitra (stdlib only).

Bringup #6: PulseAudio's module-droid-card logs "Failed to parse any configuration" and no sinks/sources appear.
pa-droid probes /odm/etc, /vendor/etc/audio, /vendor/etc, /system/etc for audio_policy_configuration.xml and picks the
first hit (/vendor/etc/audio/...). That stock file xi:includes /odm/etc/virtual_audio_policy_configuration.xml (absent) and
volume tables. We provide /odm/etc/audio_policy_configuration.xml (probed first) with all includes inlined/removed.
Also the stock vendor.audio-hal never starts in the container (no init.svc property), so a differently-named service is added.

  python3 scripts/audio_sanitize.py [--vendor DIR] [--out DIR]
"""
import argparse, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STOCK = ROOT / "firmware" / "stock-a13"

RC = """# bitra: the stock vendor.audio-hal service is never started in the Droidian container; start the audio HAL explicitly
service bitra-audio-hal /vendor/bin/hw/android.hardware.audio.service
    class hal
    user audioserver
    group audio camera drmrpc inet media mediadrm net_bt net_bt_admin net_bw_acct wakelock
    capabilities BLOCK_SUSPEND
    ioprio rt 4
"""


def module_of(p: Path):
    t = p.read_text(encoding="utf-8")
    m = re.search(r"<module\b.*?</module>", t, re.S)
    return m.group(0) if m else ""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vendor", default=str(STOCK / "v-extract" / "vendor"))
    ap.add_argument("--out", default=str(ROOT / "roms" / "droidian" / "work" / "overlays"))
    a = ap.parse_args()
    v, out = Path(a.vendor), Path(a.out)
    src = (v / "etc/audio/audio_policy_configuration.xml").read_text(encoding="utf-8")

    def inline(m):
        href = m.group(1)
        if href.endswith(("r_submix_audio_policy_configuration.xml", "bluetooth_qti_hearing_aid_audio_policy_configuration.xml")):
            return module_of(v / "etc" / Path(href).name)
        return ""          # virtual audio (absent), volumes (not used by PulseAudio)
    new = re.sub(r'<xi:include\s+href="([^"]+)"\s*(?:/>|>.*?</xi:include>)', inline, src, flags=re.S)
    new = new.replace(' xmlns:xi="http://www.w3.org/2001/XInclude"', "")
    assert "xi:include" not in new
    for rel, text in (("odm/etc/audio_policy_configuration.xml", new), ("vendor/etc/init/bitra-audio.rc", RC)):
        p = out / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        print("wrote", p, len(text))


if __name__ == "__main__":
    main()
