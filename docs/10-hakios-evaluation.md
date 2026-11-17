# 10 — HakiOS (XNU/iOS-on-Android) evaluation for bitra  (2026-11-09)

Project: https://hackios-web.vercel.app/en (OOSEX GANG); code https://github.com/oosexgang/hakios-xnu-kernel (APSL-2.0 for XNU parts, MIT rest).
Checked: site pages (via fetch agent), GitHub API (stars/commits/contributors/repos), Mu-Silicium Status.md. Not reproduced on hardware.

## Claims vs. what the evidence shows
| Claim (press / site) | Their own docs say | Verified by me |
|---|---|---|
| "iOS runs on Android phones" | "research project, not a ROM". Open XNU kernel (xnu-8796.121.2) + own loader + own drivers. User space = Apple files you lay out from your own IPSW (iOS 16.5 class). No Secure Enclave, no activation, no Apple ID/App Store | Repo exists, public, APSL-licensed |
| Works on POCO X5 Pro (SM7325/Snapdragon 778G) | display, touch, 8 CPUs, GL ES via Mesa, UFS read, audio, haptic, camera, Wi-Fi (Linux ath11k driver); partly: modem boots but no registration, battery level only; no: Bluetooth, charging | Self-reported; no screenshots/videos on pages read; needs that exact phone to verify |
| Metal, 100-104 fps | "partly", 120 not reached, other Metal apps not shown, numbers from synthetic gestures, one phone, UI faked to iPhone X/XR screen class | Unverified |
| Active, popular | repo created 2026-10-22, pushed daily to 2026-11-08, 1,039 commits in ~17 days, 2.7k stars, 425 forks | Confirmed via GitHub API. Contributors: one account 763 commits, one 183, an org account 85, a `claude` account 3 (so AI-assisted work is at least partly in the open). Pace suggests heavy AI/assisted generation: not proof of quality either way |
| Other devices | Infinix Hot 20 (MT6768) experimental; Pixel 6a, Nothing 3a, LG V60 seen in press only | Org has repos only for sm7325, mt6768, uefi, metal. No sm8250 repo |
| Money | site promotes a "$HackiOS" token (BNB Chain) "that funds the team" | Noted; team disowns a different meme coin. Treat with caution |
Early press (Oct 23) said "no code": the repo was only a day old then. Later articles reflect the published repo.

## Viability for bitra (SM8250 / Snapdragon 870, Adreno 650)
Needs, in order:
1. **UEFI**: Mu-Silicium has `Platforms/Realme/bitraPkg` (contributors Robotix22, kubawis128; state "Inactive", last touched 2026-08-29).
   Status: display OK, UFS OK, buttons OK, USB host OK, Windows/Linux boot OK; **USB device mode and PD not working**. This is a real head start.
2. **SoC layer for sm8250**: HakiOS only knows sc7280. Its tooling supports adding a new SoC (`--soc sm8250`) but that is new work: clocks/cpufreq/thermal/socinfo, UFS, modem/IPA/mailbox layout.
3. **Phone drivers rewritten for XNU**: touch (we have Synaptics S3908 + ST FTS; they have Goodix/FocalTech), GPU (Adreno 650 needs its own GMU/firmware path; theirs targets 642L), audio (WCD938x + TFA98xx), haptics (AW8697), camera (S5KGW1 etc.).
4. **Wi-Fi**: they reuse Linux ath11k on WCN6750 (on-SoC). Our DTS lists QCA6390, [K] a PCIe-attached chip on kona, so a PCIe path would be needed. Verify real chip first.
5. User space: iOS 16.5 files from an IPSW you provide. Apple's license terms likely forbid this use (their own docs say they give no legal opinion).
Cost/benefit: a full-featured outcome would be: screen, touch, Wi-Fi, maybe GPU. Cellular, camera, charging, fingerprint, Bluetooth are unlikely. Effort is comparable to a mainline Linux bring-up but the result is less useful.
Safety: runs from RAM via `fastboot boot`; Android is untouched on reboot [their claim; plausible for an unlocked bootloader].

## Recommendation
- Not a priority. Do it after LineageOS boots and the Linux/mainline bring-up (docs 08/09): the reusable part is the hardware knowledge (DTS data, firmware pull, UEFI), not code.
- Cheap first experiment later: build the `bitraPkg` UEFI image and see if it reaches the loader via `fastboot boot` (needs `fastboot boot` behavior verified on this ABL).
- Treat headline claims as unverified until reproduced or independently filmed.
