---
title: "Why My Thunderbolt 5 Dock's HDMI Output Went Black"
description: "A hands-on investigation of a display problem with one Mac, dock, and monitor."
summary: "The dock's HDMI output went black on one Mac. Testing pointed to an interaction between macOS 26, the monitor's HDMI Deep Color setting, and the dock's HDMI converter; direct DisplayPort provided a workaround."
tags: [bandwidth, encoding, monitoring, protocols, systems-programming]
categories: ["deep-dives"]
draft: false
date: "2026-10-24T23:30:00-07:00"
---

## What Happened

My LG 4K monitor works through the HDMI port on an Anker Thunderbolt 5 dock when connected to my M1 Pro or M3 Max. It also works from the built-in HDMI port on my M5 Max. But through the dock's HDMI port on the M5 Max, the screen stays black—even though macOS lists the display as active at 2560×1440 and 60 Hz. Comparing connection paths and checking the system state as I changed settings pointed me to a reliable 4K workaround.

> [!NOTE]
> **Test setup:** Apple M5 Max (`T6050`), macOS 26.x, Anker Prime Thunderbolt 5 dock (`JHL9580`, firmware 64.1), and one LG 4K monitor. These observations are from this setup; they may not apply to other docks, monitors, or OS versions.

Thunderbolt carries video through the dock as well as data. The dock's HDMI port has an extra step: it converts the incoming DisplayPort video for HDMI. The dock's USB-C port can send DisplayPort directly to a monitor that has a DisplayPort input.

## What I Tried

| Connection | Result |
|---|---|
| M5 Max's built-in HDMI port | Works |
| Dock's HDMI port, with M5 Max | Black screen |
| Dock's USB-C port to the monitor's DisplayPort input, with M5 Max | Works at 4K, 60 Hz |
| Dock's HDMI port, with M1 Pro or M3 Max | Works |

{{< mermaid >}}
graph LR
    Mac["M5 Max"] -->|Dock HDMI| Converter["Dock converts video to HDMI"]
    Converter -.->|Black screen| HDMI["LG monitor"]
    Mac -->|Dock USB-C to DisplayPort| DP["LG monitor"]
    DP -->|Works| Pass["4K at 60 Hz"]
{{< /mermaid >}}

## What the System Information Suggested

I recorded macOS `ioreg` snapshots as I changed the connection and display settings. This was a focused troubleshooting process: I compared connection paths and settings, then checked what macOS reported after each change. I used a model to help interpret the snapshots throughout. I verified the practical results by testing them; I have not independently verified every interpretation of the undocumented properties.

The strongest clue was a mismatch in the reported connection details:

- The dock's DisplayPort output adapter reported an established link with **2 lanes** and a link rate value of `2`. I interpreted that rate as HBR2, but have not independently verified the mapping.
- A separate display-transport property reported `LaneCount = 4`.
- macOS continued to use a 3840×2160, 60 Hz output timing even when I selected 2560×1440 in Display Settings.
- During the black-screen failure, the display clock was reported as zero, and the system repeatedly logged `HPD_IRQ` events—display-link retraining attempts.

These values could fit a bandwidth problem: the display path may be trying to send more video data than the dock's HDMI route can carry. But I don't know whether the two lane-count properties describe the same thing, or which component—if any—is reporting the wrong value.

I initially read a change in the raw capability values, `0xc7` to `0x47`, as evidence that the available lanes had changed from four to two. I have not verified that interpretation of the undocumented bit fields, so I don't rely on those values as proof.

### The Resolution Setting Wasn't Changing the Signal

Selecting “2560×1440 (low resolution)” in macOS did not fix the black screen. The system information still showed a 3840-pixel-wide signal going to the monitor. In other words, changing the apparent resolution in macOS did not necessarily change the video signal sent over the cable.

After I turned off **HDMI ULTRA HD Deep Color** in the monitor's settings, the monitor advertised a lower maximum rate and macOS switched to a 2560×1440 signal at 60 Hz. The picture then appeared. This is evidence that the signal timing matters in this setup; it does not explain why the original 4K signal failed.

## What Worked

- **Reliable workaround:** Connect the dock's USB-C port to the monitor's DisplayPort input with a USB-C-to-DisplayPort cable. This avoids the dock's HDMI conversion path. I got 4K at 60 Hz with 10-bit color.
- **HDMI workaround for 1440p:** Turn off HDMI ULTRA HD Deep Color in the monitor's settings. This allowed a real 2560×1440, 60 Hz signal to work. It is not a fix for 4K over the dock's HDMI port.
- **What did not work:** Selecting 2560×1440 in macOS by itself still left the screen black.

The M1 Pro and M3 Max working through the same dock is another useful comparison, but I haven't established why they behave differently.

## My Working Explanation

My best explanation is an interaction between macOS 26, the monitor's HDMI ULTRA HD Deep Color setting, and the dock's Synaptics `SYNAq` HDMI converter. With Deep Color enabled, the monitor advertises a 4K-at-60-Hz timing with a higher pixel rate. macOS appears to keep using that timing even when its display settings show 2560×1440. That higher-rate signal fails on the dock's HDMI path.

Turning Deep Color off lowers the advertised rate, after which macOS sends a real 2560×1440 signal and the picture appears. Sending DisplayPort directly through the dock's USB-C port bypasses the `SYNAq` converter and gives me a reliable 4K picture. Together, these results point to a compatibility and bandwidth interaction in this setup—not a confirmed fault in any one component. I found the working 4K path within about an hour; what remains unresolved is which part of the interaction causes the HDMI failure.

## Technical Notes

These are the main `ioreg -lw0` values behind the investigation. The names and capability bytes are included for readers who want to inspect the evidence; I can't fully explain every field.

```text
AppleThunderboltDPInAdapterOS2
  Cached Local DP Capabilities  = <15c72335>
  Remote DP Capabilities        = <05c7a335>
  Cached Common DP Capabilities = <85472235>
  DPI BWAM Support              = Yes
AppleThunderboltDPOutAdapterOS2
  Established DP Link Rate = 2   (HBR2)
  Established DP Lane Count = 2
```

If the reported link rate of `2` means HBR2, then a two-lane link would carry roughly 8.64 Gbps after link coding. A 594 MHz 4K signal would require roughly 14.3 Gbps at 8 bits per color channel, or 17.8 Gbps at 10 bits per channel, before considering the details of the full display transport. That rough comparison is why I suspected a bandwidth mismatch; it is not a complete analysis of the dock's actual bandwidth allocation.

The registry also showed `LaneCount = 4` on an `IOPortTransportStateDisplayPort` object, while the dock's output adapter reported an established lane count of 2. The meaning and relationship of these properties are not clear to me.

## References

- [USB4 Specification v2.0](https://www.usb.org/document-library/usb4r-specification-v20)
- [Linux Thunderbolt/USB4 admin guide](https://docs.kernel.org/admin-guide/thunderbolt.html), for background on tunnels and connection management.
- [Linux Thunderbolt tunnel driver](https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/tree/drivers/thunderbolt/tunnel.c), an implementation reference. It does not confirm how Apple's undocumented properties should be interpreted.
