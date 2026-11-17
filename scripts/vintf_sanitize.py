#!/usr/bin/env python3
"""Make the stock Android-13 odm/vendor VINTF manifests parseable by Droidian's Android-11 (api30) container.

Problem (bringup #2): Android 11's libvintf cannot parse `<hal format="aidl">...<version>1</version>` from the
newer odm manifests ("Could not parse text "1" in element <version>"). The whole device manifest is then rejected,
hwservicemanager considers NO HAL declared and every registerAsService() fails (-2147483648) -> display allocator/composer,
keymaster, wifi, nfc, drm HALs abort.
Fix: drop the AIDL <hal> entries (AIDL services register with the plain binder servicemanager, which does not consult
VINTF on Android 11) and keep everything else. Output = overlay trees that the rootfs mounts over /odm and /vendor.

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
                    removed.append(name)
                    root.remove(hal)
            if not removed:
                continue
            out = dst / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            ET.indent(tree) if hasattr(ET, "indent") else None
            tree.write(out, encoding="utf-8", xml_declaration=False)
            left = len(root.findall("hal"))
            report.append(f"{label}:{rel}: removed {len(removed)} aidl hal(s) {removed}; {left} remain")


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
