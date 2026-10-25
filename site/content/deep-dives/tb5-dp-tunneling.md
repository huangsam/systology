---
title: "Thunderbolt 5 DisplayPort Tunneling"
description: "Debugging a DisplayPort tunnel lane-masking bug on Apple Silicon."
summary: "An IOKit investigation into how Thunderbolt 5 bandwidth allocation masks a 4-lane DisplayPort tunnel to 2 lanes on M5 Max, starving downstream HDMI protocol converters."
tags: [bandwidth, encoding, monitoring, protocols, systems-programming]
categories: ["deep-dives"]
draft: false
date: "2026-10-24T23:30:00-07:00"
---


## Context & Motivation

**Context:** **Thunderbolt 5 (USB4 v2)** multiplexes PCIe, USB and DisplayPort 2.1 over an 80 Gb/s link. Video is not carried on dedicated wires as in DP Alt Mode. It travels in **DisplayPort tunnels** between a host `DP-In` adapter and a dock `DP-Out` adapter. Multi-port docks either hand the stream to a downstream USB-C port or pass it through an active DP-to-HDMI converter (here a Synaptics `SYNAq`).

**Motivation:** An **LG HDR 4K** monitor on the HDMI port of an **Anker Prime TB5 dock** (Intel `JHL9580`) works from an **M1 Pro** and an **M3 Max**. It also works on the built-in HDMI port of an **M5 Max**. Through the dock's HDMI port on the M5 Max, it stays black, even though System Settings reports the display as active at 2560×1440 @ 60Hz.

## The Local Implementation

> [!NOTE]
> **Test environment:** Apple M5 Max (`T6050`) on macOS 26.x (Darwin 25.6.0), 80 Gb/s TB5 link to the Anker Prime dock (`JHL9580` FW 64.1). All findings come from this single host/dock/monitor combination, via `ioreg -lw0`.

### Three Signal Paths

| Signal Path | Tunnel / Link Allocation | Downstream Silicon | 4K @ 60Hz |
|---|---|---|---|
| **Built-in HDMI** | Direct SoC link, 4 lanes × HBR3 (25.92 Gbps) | Built-in `pHDMIg` | **Pass** |
| **Dock HDMI** (`Port@C`) | **2 lanes** × HBR2 (8.64 Gbps) | Synaptics `SYNAq` | **Fail** (black, `HPD_IRQ` loop) |
| **Dock USB-C** (`Port@B`) | Direct DP tunnel | Native monitor DP sink | **Pass** (533 MHz CVT-RB) |

{{< mermaid >}}
graph LR
    DCP["M5 Max DCP<br>Believes 4 lanes"] --> DPIn["TB5 DP-In Adapter<br>Tunnel: 2 lanes (8.64 Gbps)"]
    DPIn -->|Port C| SYNA["Synaptics SYNAq<br>Needs more than 8.64 Gbps"]
    SYNA -.->|HPD_IRQ loop| HDMI["LG 4K HDMI<br>594 MHz (black screen)"]
    DPIn -->|Port B| DP["LG 4K DisplayPort<br>533 MHz (pass)"]
{{< /mermaid >}}

### Likely Cause: Tunnel and Display Engine Disagree

The link negotiates with **DisplayPort Bandwidth Allocation Mode** (`DPI BWAM Support = Yes`). Both ends advertise 4 lanes (`0xc7` in byte 1 of the DP capability words). The cached *common* capability is masked down to `0x47`, which is 2 lanes:

```text
AppleThunderboltDPInAdapterOS2
  Cached Local DP Capabilities  = <15c72335>
  Remote DP Capabilities        = <05c7a335>
  Cached Common DP Capabilities = <85472235>   # byte 1: c7 -> 47
AppleThunderboltDPOutAdapterOS2
  Established DP Link Rate = 2   (HBR2)
  Established DP Lane Count = 2
```

A 2-lane HBR2 tunnel carries at most $2 \times 5.4 \times 0.8 = 8.64$ Gbps after 8b/10b coding. Meanwhile the higher-level `IOPortTransportStateDisplayPort` object still reports `LaneCount = 4` (17.28 Gbps) to the display co-processor. The co-processor therefore picks uncompressed CEA-861 3840×2160 @ 60Hz (594 MHz pixel clock, `DPTimingModeId = 77`) with no DSC:

$$594\text{ MHz} \times 24\text{ bpp} \approx 14.3\text{ Gbps}\ (17.8\text{ Gbps at 10 bpc})$$

Both figures are well above 8.64 Gbps. The stream stalls in the dock's `SYNAq` converter. The host shows `PixelClock = 0`, and `AppleATCDPINAdapterPort` logs `HPD_IRQ` retrains every 3.8–5.4 s until the dock unplugs. The USB-C path (`Port@B`) avoids the converter. It also negotiates a lighter 533 MHz reduced-blanking timing.

The tunnel is clearly 2 lanes while the display engine believes 4. I couldn't confirm which component is at fault, and a firmware or driver explanation is equally plausible.

### The "Silent Upscaling" Trap

Selecting `2560×1440 (low resolution)` should need only about 5.6 Gbps, yet it still gave a black screen. While the monitor's EDID advertises 4K60 (`MaxTotalPixelRate = 594000000`), the display co-processor keeps the **wire timing at 3840 wide** and scales on the GPU. The wire timing only dropped to a real 1440p60 (`DPTimingModeId = 46`) after **HDMI ULTRA HD Deep Color** was disabled on the monitor. That capped the advertised rate at 297 MHz.

### Why M1 Pro and M3 Max Work

They have USB4 v1 (40 Gb/s) host routers. The dock falls back to v1 mode, where macOS appears to use legacy DP tunnel allocation without BWAM. That grants 4 lanes of HBR2 (17.28 Gbps), enough for 4K60 at 8 bpc (about 14.3 Gbps).

## Comparison to Industry Standards

| Layer | Expected (USB4 v2 / DP tunneling) | Observed (macOS + `JHL9580`) |
|---|---|---|
| **Lane negotiation** | Intersect local and remote capability, giving 4 lanes | Common capability masked to 2 lanes under BWAM |
| **State propagation** | Display engine sees the established tunnel bandwidth | Transport state still reports 4 lanes |
| **Bandwidth mitigation** | Engage DSC or 4:2:0 when the tunnel is below the mode rate | Attempts uncompressed 594 MHz over the 2-lane tunnel |
| **Downscaling** | A lower resolution lowers the wire clock | Wire stays at 3840 while EDID offers 594 MHz |

The "expected" column reflects my reading of the [USB4 specification](https://www.usb.org/document-library/usb4r-specification-v20) (DP IN/OUT adapter capability registers and DP bandwidth allocation mode) and the [DisplayPort standard](https://vesa.org/vesa-standards/) (8b/10b coding, DSC). It is not tied to specific clauses. The Linux [`thunderbolt` driver](https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/tree/drivers/thunderbolt/tunnel.c) (`tb_dp_xchg_caps()`) is an open reference for how the `DP_LOCAL_CAP`/`DP_REMOTE_CAP`/`DP_COMMON_CAP` exchange is implemented.

## Risks & Mitigations

- **Converter starvation on dock HDMI:** 594 MHz timings over a 2-lane tunnel cause continuous `HPD_IRQ` drops.
    - *Mitigation:* Use a **DisplayPort-to-USB-C cable** on a rear dock USB-C port. This bypasses `SYNAq`. It gave 4K HiDPI @ 60Hz, 10-bit.
- **Wire timing locked to 4K60:** Changing the macOS resolution does not reduce link bandwidth.
    - *Mitigation:* Over HDMI, either set 30Hz, disable HDMI ULTRA HD Deep Color on the monitor, or force YCbCr 4:2:0 with BetterDisplay.
- **Wedged secondary display pipelines:** Rapid hot-plugging between built-in HDMI and dock ports can leave `dispext1,t605x` stuck at `DisplayClock = 0`.
    - *Mitigation:* Connect only one video path per monitor, then power-cycle the dock for 10 seconds.
- **Early OS upgrade regressions:** Upgrading to a `.0` or `.1` release for a driver fix risks wider regressions, and the dock's own limits remain.
    - *Mitigation:* Use the DP-to-USB-C path on a stable OS, file Feedback Assistant telemetry naming `AppleThunderboltDPInAdapterOS2`, and wait for mature point releases and dock firmware.

## References

- [USB4 Specification v2.0](https://www.usb.org/document-library/usb4r-specification-v20), USB-IF: DP tunneling, DP adapter registers, bandwidth allocation mode.
- [VESA DisplayPort Standard](https://vesa.org/vesa-standards/): link rates, lane counts, 8b/10b coding, DSC.
- [Linux `drivers/thunderbolt/tunnel.c`](https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/tree/drivers/thunderbolt/tunnel.c): open-source DP tunnel setup and capability exchange.
- [Linux Thunderbolt/USB4 admin guide](https://docs.kernel.org/admin-guide/thunderbolt.html): background on tunnels and connection management.
