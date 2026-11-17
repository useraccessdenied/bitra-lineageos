# Attribution

This repository only tracks our changes. The real work belongs to the upstream maintainers.
Our forks keep upstream history and authorship intact and add commits on branches `bitra/a16` and `bitra/a17`.

| Component | Upstream / credit |
|---|---|
| LineageOS 23.2 / 24.0 | LineageOS Project — https://github.com/LineageOS |
| Device trees `bitra`, `sm8250-common`, `hardware/oplus`, kernel (A16) | AxionAOSP-devices maintainers — https://github.com/AxionAOSP-devices |
| Device trees, `hardware/oplus`, `hardware/dolby`, RealmeAddons, kernel "Entropy" (A17) | SM8250-Common maintainers — https://github.com/SM8250-Common |
| `proprietary_vendor_oplus_camera` (OplusCamera blobs/config), SM8250-common vendor (A17) | bijoyv9 — https://gitlab.com/bijoyv9 |
| Proprietary vendor blobs | Extracted from Realme/Oplus stock firmware by the maintainers above; property of their owners; **not redistributed here** |
| KernelSU, ReSukiSU (manager/driver) | tiann/KernelSU authors; ReSukiSU — https://github.com/ReSukiSU/ReSukiSU (pinned as a submodule, GPL-2.0) |
| SUSFS | simonpunk and contributors; integrated via SM8250-Common's `sus` branch (commits 3be72cd6a, 13ae07457) |
| Droidspaces kernel patches/config | Droidspaces-OSS — https://github.com/ravindu644/Droidspaces-OSS |
| AxionOS (reference ROM comparison) | AxionAOSP team — comparison only, no files redistributed |

Kernel changes remain under the kernel's GPL-2.0 license; Android/Lineage code under Apache-2.0 unless noted. If you are a
maintainer above and want credit changed or something removed, open an issue.
