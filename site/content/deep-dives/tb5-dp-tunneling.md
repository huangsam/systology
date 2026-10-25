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

**Context:** Modern single-cable workstation topologies rely on **Thunderbolt 5 (USB4 v2)** to multiplex PCIe, SuperSpeed USB, and high-bandwidth DisplayPort 2.1 streams over an 80 Gb/s (up to 120 Gb/s asymmetric) physical link. Rather than dedicating fixed physical wires on the USB-C connector to video (as in traditional DisplayPort Alt Mode), Thunderbolt 5 encapsulates DisplayPort packets inside time-slotted **Thunderbolt DisplayPort Tunnels** managed by host-side `DP-In` adapters and dock-side `DP-Out` adapters. Inside multi-port docks, these tunneled DisplayPort streams are either routed directly to downstream Thunderbolt USB-C receptacles or passed through active **DisplayPort-to-HDMI branch protocol converters** (such as Synaptics `VMMxxxx` silicon) to drive legacy HDMI 2.0/2.1 monitors.

**Motivation:** When connecting a 4K @ 60Hz HDR monitor (**LG HDR 4K**) via HDMI to an **Anker Prime Thunderbolt 5 Docking Station** (`Intel JHL9580` Barlow Ridge controller), the display worked out of the box on **M1 Pro** and **M3 Max** MacBook Pros—and worked when plugged directly into the built-in HDMI port of an **M5 Max** MacBook Pro—yet consistently produced a **black screen** when connected through the dock's HDMI port on the **M5 Max**. Standard OS-level display preferences (`System Settings → Displays`) reported the monitor as active, online, and running at `2560 x 1440 @ 60.00Hz` (HiDPI scaled via a `5120 x 2880` backing framebuffer), masking a silent kernel-level split-brain between the **Thunderbolt 5 tunnel allocation layer** and the **Display Co-Processor (DCP) data plane**.

## The Local Implementation

> [!NOTE]
> **Test Environment:** All hardware register captures and live kernel state transitions were collected on an **Apple M5 Max (`T6050`, 40-core GPU)** running **macOS 26.x (`Darwin Kernel 25.6.0`)**, connected over an 80 Gb/s Thunderbolt 5 link to an **Anker Prime Docking Station (14-in-1, 8K, Thunderbolt 5)** (`VID: 0x291A`, `PID: 0x83B5`, Intel `JHL9580` FW `64.1`, MCU `1.11.0`) driving an **LG HDR 4K** display (`0x1E6D:0x7706` on HDMI; `0x1E6D:0x7707` on DisplayPort).

### Three Signal Paths Across Two Silicon Generations

To isolate why only the `{M5 Max + Anker TB5 Dock + HDMI Port}` tuple failed at 4K @ 60Hz, we traced all three physical topologies in the IOKit registry (`ioreg -lw0`):

| Signal Path | Host Router / Link Mode | Tunnel / Link Allocation | Downstream Silicon | 4K @ 60Hz Result |
|---|---|---|---|---|
| **Built-in HDMI (`Port-HDMI@1`)** | Direct SoC (`AppleATCDPPort`) | 4 Lanes × 8.1 Gbps (HBR3) = **25.92 Gbps** | Built-in `pHDMIg` (`00-10-FA`) | **Pass** (12 bpc, 594 MHz) |
| **Dock HDMI (`IOThunderboltPort@C`)** | `IOThunderboltSwitchType7` (80 Gb/s) | **2 Lanes** × 5.4 Gbps (HBR2) = **8.64 Gbps** | Synaptics `SYNAq` (`90-CC-24`) | **Fail** (Black Screen / `HPD_IRQ` Loop) |
| **Dock Rear USB-C (`IOThunderboltPort@B`)** | `IOThunderboltSwitchType7` (80 Gb/s) | Direct DP Tunnel → `Dp1.2` Sink | Native LG DP Sink (`00-E0-4C`) | **Pass** (10 bpc, 533.25 MHz CVT-RB) |

{{< mermaid >}}
graph LR
    DCP["M5 Max DCP<br>Reports 4 Lanes"] --> DPIn["TB5 DP-In Adapter<br>Masks to 2 Lanes (8.64 Gbps)"]
    DPIn -->|Dock Port C| SYNA["Synaptics SYNAq<br>Needs 14.93 Gbps"]
    SYNA -.->|HPD_IRQ Loop| HDMI["LG 4K HDMI<br>594 MHz (Black Screen)"]
    DPIn -->|Dock Port B| DP["LG 4K DisplayPort<br>533.25 MHz (Pass)"]
{{< /mermaid >}}

### Control Plane vs. Data Plane Split-Brain in `AppleThunderboltDPInAdapterOS2`

When the M5 Max connects to the Anker dock, the host router (`IOThunderboltSwitchType7`) and dock router (`IOThunderboltSwitchIntelJHL9580`) negotiate an **80 Gb/s Thunderbolt 5 (USB4 v2)** link with **DisplayPort Bandwidth Allocation Mode (`DPI BWAM Support = Yes`)** enabled.

Inspecting the raw 32-bit DisplayPort Adapter Configuration Space capability registers (`DP_LOCAL_CAP`, `DP_REMOTE_CAP`, and `DP_COMMON_CAP`) on `AppleThunderboltDPInAdapterOS2` and `AppleThunderboltDPOutAdapterOS2` exposed the exact failure mechanism:

```text
+-o AppleThunderboltDPInAdapterOS2  <class AppleThunderboltDPInAdapterOS2, id 0x100000d13>
    {
      "Reserved Client" = "<0:0x00000001:0x0000000c>"
      "DP State" = 2
      "Cached Local DP Capabilities"  = <15c72335>
      "Remote DP Capabilities"        = <05c7a335>
      "Cached Common DP Capabilities" = <85472235>
      "DPI BWAM Support" = Yes
    }

+-o AppleThunderboltDPOutAdapterOS2  <class AppleThunderboltDPOutAdapterOS2, id 0x10001b59a>
    {
      "DP State" = 2
      "HPD State" = Yes
      "Cached Local DP Capabilities" = <05c7a335>
      "Remote DP Capabilities"       = <15c72335>
      "Established DP Link Rate"     = 2
      "Established DP Lane Count"    = 2
      "Established DP Bandwidth"     = 160
      "Cached Estimated Bandwidth"   = 1197
      "DPI BWAM Support"             = Yes
    }
```

1. **Capability Bitmask Truncation (`0xc7` → `0x47`):**
   * Both the M5 Max (`<15 c7 23 35>`) and the Anker dock (`<05 c7 a3 35>`) advertise `0xc7` in byte 1 (indicating support for **4 DisplayPort lanes**).
   * However, when `AppleThunderboltDPInAdapterOS2` computes the intersection under `DPI BWAM`, `Cached Common DP Capabilities` masks byte 1 down to `0x47` (**2 lanes**), provisioning a tunnel with **`Established DP Lane Count = 2`** and **`Established DP Link Rate = 2` (HBR2 = 5.4 Gbps/lane)**.
2. **Tunnel Payload Ceiling:**
   * Using standard DisplayPort 8b/10b encoding ($\eta = 0.80$), a 2-lane HBR2 tunnel has a hard payload ceiling of:

$$\text{Max Tunnel Payload} = 2\text{ lanes} \times 5.4\text{ Gbps/lane} \times 0.80 = 8.64\text{ Gbps}$$

3. **Unpropagated Constraint to the Display Engine (`Port@C` vs. `Port@B`):**
   * Despite the Thunderbolt tunnel only provisioning **2 lanes**, the higher-level DisplayPort transport state object (`IOPortTransportStateDisplayPort` at `Port-USB-C@1/CIO/DisplayPort@0`) reports **`LaneCount = 4`** at **`5.4 Gbps (HBR2)`** (**17.28 Gbps** assumed capacity) to the Display Co-Processor (`AppleMobileDispT605X-DCP`).
   * Believing it has 17.28 Gbps of headroom, the display engine selects uncompressed **CEA-861 3840x2160 @ 60Hz (`594 MHz` pixel clock, 10/12 bpc, `DPTimingModeId = 77`)** without enabling Display Stream Compression (DSC):

$$\text{Required Uncompressed 4K60 Payload (10 bpc)} = 594\text{ MHz} \times 30\text{ bits/pixel} = 17.82\text{ Gbps raw} \quad (\approx 14.93\text{ Gbps active})$$

   * On **`IOThunderboltPort@C`**, the stream is routed into the dock's internal Synaptics (`SYNAq`) DP-to-HDMI branch/MST converter, which enforces the 2-lane HBR2 (`8.64 Gbps`) cap and starves on the ~14.93 Gbps HDMI timing. The M5 Max display pipeline (`dispext0,t605x`) stalls with `"PixelClock" = 0` and `"DisplayClock" = 0`, while `AppleATCDPINAdapterPort(atc0-dpin0)` logs pairs of `Action = "IRQ"` (`HPD_IRQ` link-loss) retraining interrupts every **3.8 to 5.4 seconds** until the dock drops HPD (`Action = "Unplug"`).
   * By contrast, **`IOThunderboltPort@B`** (rear Thunderbolt 5 USB-C receptacle) bypasses the internal `SYNAq` HDMI branch chip entirely, establishing a direct DisplayPort tunnel to the monitor's native `Dp1.2` sink at a lower reduced-blanking pixel clock (`533.25 MHz` CVT-RB, `DPTimingModeId = 45`) without protocol conversion overhead.

### The "Silent Upscaling" Trap in `AppleMobileDispT605X-DCP`

A counter-intuitive behavior surfaced during live testing when attempting to lower the resolution in **System Settings → Displays**:
* Selecting **`2560 x 1440 (low resolution)` @ 60Hz** (which natively requires only ~5.6 Gbps and should easily fit inside 8.64 Gbps) **still resulted in a black screen** when `HDMI ULTRA HD Deep Color` was enabled on the monitor.
* Inspecting `dispext0,t605x` revealed why: as long as the monitor's EDID advertises `3840x2160 @ 60Hz` (`MaxTotalPixelRate = 594000000`) as its preferred native timing, Apple Silicon's DCP **locks the physical wire timing to `DisplayWidth = 3840` (`DPTimingModeId = 77`)** and performs all resolution changes via GPU scaling.
* Only when **HDMI ULTRA HD Deep Color** was disabled on the monitor's OSD—causing the monitor's EDID to cap `MaxTotalPixelRate` at `297000000` (297 MHz)—did `dispext0,t605x` actually lower the physical wire clock to native `2560 x 1440 @ 60Hz` (`DisplayWidth = 2560`, `DPTimingModeId = 46`, `subframe-interrupt-time-lines = 1381`), immediately lighting up the screen at 60Hz.

### Why M1 Pro and M3 Max Work Over the Same Dock

* **M1 Pro** and **M3 Max** use Thunderbolt 4 (**USB4 v1, 40 Gb/s**) host routers (`IOThunderboltSwitchType5`).
* When the Anker Prime Thunderbolt 5 dock connects to a TB4 host, its Intel `JHL9580` controller falls back to **USB4 v1 backward-compatibility mode**.
* In USB4 v1 mode, macOS uses legacy DisplayPort tunnel allocation rather than `DPI BWAM`, provisioning all **4 lanes of HBR2 (17.28 Gbps)** to `IOThunderboltPort@C`—allowing the Synaptics `SYNAq` converter to pass uncompressed 4K @ 60Hz without starvation.

## Comparison to Industry Standards

| Architectural Layer | Expected Specification Behavior (TB5 / DP 2.1) | Observed macOS + JHL9580 Behavior |
|---|---|---|
| **Tunnel Lane Negotiation** | Intersect `DP_LOCAL_CAP` (4L) and `DP_REMOTE_CAP` (4L) → **4 Lanes** (`0xc7`) | Masked to **2 Lanes** (`0x47`) in `Cached Common DP Capabilities` under `DPI BWAM` |
| **State Propagation** | Propagate `Established DP Lane Count = 2` to `IOPortTransportStateDisplayPort` | `IOPortTransportStateDisplayPort` reports stale/static `LaneCount = 4` to DCP |
| **Bandwidth Mitigation** | Automatically engage **DSC (Display Stream Compression)** or 4:2:0 chroma when tunnel < mode rate | Attempts uncompressed 594 MHz 4K60 over 2-lane HBR2 tunnel → `PixelClock = 0` stall |
| **Resolution Downscaling** | Selecting `2560x1440 (low-res)` lowers physical wire clock to 1440p60 (~241.5 MHz) | DCP keeps physical wire locked at `3840x2160` (`DPTimingModeId = 77`) if 594 MHz is in EDID |

## Risks & Mitigations

- **Protocol Converter Starvation on Dock HDMI Ports (`SYNAq`):** Routing high-pixel-clock CEA-861 HDMI timings (`594 MHz`) through an internal DP-to-HDMI branch converter over a 2-lane HBR2 Thunderbolt 5 tunnel causes continuous `HPD_IRQ` link drops.
    - *Mitigation (Hardware — Optimal):* Connect the monitor's **DisplayPort** input directly to one of the dock's **rear Thunderbolt 5 USB-C ports (`IOThunderboltPort@B` or `@13`)** using a **DisplayPort-to-USB-C cable**. This completely bypasses the internal Synaptics `SYNAq` HDMI branch chip, communicating directly with the monitor's native DP sink (`SinkDeviceID = "Dp1.2"`, `DPTimingModeId = 45`, `533.25 MHz` CVT-RB) at full **4K HiDPI (`Looks like 2560 x 1440`) @ 60Hz, 10-bit** across M5 Max, M3 Max, and M1 Pro.
- **Silent GPU Upscaling Locking Wire Timings (`DPTimingModeId = 77`):** Changing macOS display resolution in System Settings does not reduce physical DisplayPort/HDMI link bandwidth if the monitor's EDID still advertises 4K60 (`594 MHz`).
    - *Mitigation (Monitor OSD / Software):* If restricted to an HDMI cable on the dock, either set the refresh rate to **30Hz** (`DPTimingModeId = 57`, ~7.46 Gbps), disable **HDMI ULTRA HD Deep Color** on the monitor OSD so macOS switches the physical wire timing to `DPTimingModeId = 46` (`2560x1440 @ 60Hz`), or use **BetterDisplay** to force **YCbCr 4:2:0 (8-bit)** at 4K60 (~7.46 Gbps).
- **Wedged Secondary DCP Pipelines (`dispext1,t605x`) During Rapid Hot-Plugging:** Simultaneously connecting or rapidly swapping between the built-in HDMI port (`ufp0,0-dfp3,0`) and tunneled dock ports (`ufp1,0-dfp0,1`) can leave secondary `IOMobileFramebufferShim` instances stuck with `"NormalModeActive" = Yes` and `"DisplayClock" = 0`.
    - *Mitigation:* Disconnect redundant video paths to the same physical monitor and power-cycle the Thunderbolt dock for 10 seconds to reset `AppleT6050DisplayCrossbar` and clear stale DFP mappings.
- **Early Major OS Upgrade Regressions:** Upgrading to an early `.0` or `.1` major OS release to chase a kernel driver fix risks introducing broader regressions across WindowServer and developer toolchains, while the dock's own `JHL9580` (`FW 64.1`) / `SYNAq` HBR2 ceiling remains unchanged.
    - *Mitigation:* Use the native DP-to-USB-C hardware path on a stable OS release, file targeted kernel telemetry via Apple Feedback Assistant referencing `AppleThunderboltDPInAdapterOS2`, and defer major OS upgrades until mature point releases and updated dock firmware are available.
