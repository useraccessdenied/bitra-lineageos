#!/usr/bin/env python3
"""Make the stock Android-13 odm/vendor VINTF manifests parseable by Droidian's Android-11 (api30) container.

Problem (bringup #2): Android 11's libvintf cannot parse `<hal format="aidl">...<version>1</version>` from the
newer odm manifests ("Could not parse text "1" in element <version>"). The whole device manifest is then rejected,
hwservicemanager considers NO HAL declared and every registerAsService() fails (-2147483648) -> display allocator/composer,
keymaster, wifi, nfc, drm HALs abort.
Fix: rewrite the AIDL <version>N</version> as <version>1.0</version> (major.minor, which R's libvintf parses) and keep everything else.
(An earlier version of this script deleted the AIDL <hal> entries, but Android 11's servicemanager DOES check that an AIDL
instance is declared: every AIDL vendor HAL -- vibrator, lights, rpmh, cammidas, misc, ... -- then aborted with
"Check failed: status == STATUS_OK", ~300 aborts per boot.) Output = overlay trees that the rootfs mounts over /odm and /vendor.

  python3 scripts/vintf_sanitize.py [--odm DIR] [--vendor DIR] [--out DIR]
Inputs are the extracted stock trees (firmware/stock-a13/{o-extract/odm,v-extract/vendor}); stdlib only.
"""
import argparse, os, sys, xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STOCK = ROOT / "firmware" / "stock-a13"


def sanitize_tree(src: Path, dst: Path, label: str, report):
    vintf = src / "etc" / "vintf"
    if not vintf.is_dir():
        return
    for dirpath, _dirs, files in os.walk(vintf):
        for fn in files:
            p = Path(dirpath) / fn
            if p.is_symlink() or not fn.endswith(".xml"):
                continue
            rel = p.relative_to(src)
            try:
                tree = ET.parse(p)
            except ET.ParseError as e:
                report.append(f"{label}:{rel}: XML parse error ({e}); copied unchanged")
                continue
            root = tree.getroot()
            if root.tag != "manifest":          # compatibility matrices etc: leave alone
                continue
            removed = []
            for hal in list(root.findall("hal")):
                if hal.get("format") == "aidl":
                    name = (hal.findtext("name") or "?").strip()
                    # Keep the entry (see module docstring), only make its <version> parseable for R's libvintf.
                    # Tested on the device: version "1.0" + the original <fqname>. Dropping <version> or rewriting
                    # <fqname> as <interface> made the WHOLE device manifest unparseable (everything fails, phosh dies).
                    for v in hal.findall("version"):
                        hal.remove(v)
                    ET.SubElement(hal, "version").text = "1.0"
                    removed.append(name)
            # qcrild registers vendor.qti.hardware.radio.ims@1.7::IImsRadio/imsradio{0,1}, but the stock odm manifests only
            # declare 1.6; Android 11's hwservicemanager then refuses it ("must be in VINTF manifest") and IMS/VoLTE is dead.
            # A declared 1.7 also satisfies requests for 1.6.
            ims_bumped = False
            for hal in root.findall("hal"):
                if (hal.findtext("name") or "").strip() == "vendor.qti.hardware.radio.ims":
                    for v in hal.findall("version"):
                        if (v.text or "").strip() == "1.6":
                            v.text = "1.7"; ims_bumped = True; removed.append("radio.ims 1.6->1.7")
            if not removed:
                continue
            out = dst / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            ET.indent(tree) if hasattr(ET, "indent") else None
            tree.write(out, encoding="utf-8", xml_declaration=False)
            left = len(root.findall("hal"))
            report.append(f"{label}:{rel}: kept {len(removed)} aidl hal(s) with version 1.0 {removed}; {left} hals total")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--odm", default=str(STOCK / "o-extract" / "odm"))
    ap.add_argument("--vendor", default=str(STOCK / "v-extract" / "vendor"))
    ap.add_argument("--out", default=str(ROOT / "roms" / "droidian" / "work" / "overlays"))
    a = ap.parse_args()
    out = Path(a.out)
    report = []
    for label, src in (("odm", a.odm), ("vendor", a.vendor)):
        if Path(src).is_dir():
            sanitize_tree(Path(src), out / label, label, report)
        else:
            print(f"skip {label}: {src} not found", file=sys.stderr)
    print("\n".join(report) if report else "nothing to change")
    print(f"\noverlays written under {out}")


if __name__ == "__main__":
    main()
