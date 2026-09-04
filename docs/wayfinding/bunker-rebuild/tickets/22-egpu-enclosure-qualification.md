---
status: open
type: task
blocked-by: []
---

# eGPU enclosure qualification

## Question

Qualify the two purchased Sonnet enclosures on the Dell XPS 14 DA14260 with the existing RTX 2070, then decide which enclosure to keep before its return window closes:

- **Sonnet eGFX Breakaway Box 550** (`GPU-550W-TB3`), open-box with cosmetic dents and no Thunderbolt cable
- **Sonnet Breakaway Box 850 T5** (`GPU-850T5`), new

The 550 is the mature, inexpensive control. On this TB4 host it should expose effectively the same 32 Gbps PCIe tunnel as the 850 T5, but provides only 87W host charging and cannot follow a future RTX 5080 onto TB5. The 850 T5 provides 100W charging, fits the RTX 5080 Founders Edition, and preserves TB5, but costs more and has little long-term field history. Windows reliability is the deciding requirement; Linux compatibility is valuable but may fall back to an Intel-only daily configuration with the eGPU attached only before booting Windows.

### External gates

- Both enclosures and the XPS have arrived.
- Record each enclosure's return deadline before testing.
- Identify the exact RTX 2070 model and verify it fits the 550's 312 x 160 x 55mm card envelope before installation.
- Confirm the 550 includes its AC power cord and that its dents do not obstruct the sliding tray, card, fan, or cover.

### Controlled setup

Use the same components and settings for both enclosures wherever physically possible:

- Same XPS Thunderbolt port
- Same short certified TB4 cable, since the 550 does not include one
- Same RTX 2070 and GPU power leads
- Same direct RTX DisplayPort connection to the AW3423DW
- Same NVIDIA driver, Windows build, power plan, resolution, refresh rate, game settings, and ambient conditions
- Sabrent connected separately; disable its Intel-driven copy of the monitor in Windows

Do not flash the monitor until both enclosures have passed the Dell updater's compatibility and detection stage. The firmware itself can only be flashed once.

### Inspection and functional checks

For each enclosure, record:

1. Physical condition, card fit, cable fit, fan behavior, and subjective noise
2. Negotiated Thunderbolt/USB4 and PCIe link topology
3. Laptop charging rate and any Dell slow-charger warning
4. Cold-boot detection across at least ten full shutdown cycles
5. Windows sleep and wake behavior across at least five cycles
6. Clean shutdown, disconnect, reconnect, and subsequent boot
7. NVIDIA idle performance state, clocks, temperature, and power draw
8. Windows Event Viewer WHEA, display-driver, PCIe, and Thunderbolt errors
9. Dell AW3423DW updater detection with the monitor connected directly by DisplayPort

Use full Windows shutdown rather than Fast Startup while qualifying enumeration. Do not change PCIe power-management settings preemptively; preserve the default configuration unless a reproduced failure gives a specific setting something to resolve.

### Performance checks

Capture enough evidence to distinguish measurement noise from a real enclosure difference:

1. PCIe host-to-device and device-to-host bandwidth
2. A repeatable synthetic graphics benchmark, at least three runs per enclosure
3. At least one representative game benchmark at 3440 x 1440, at least three runs per enclosure
4. Average frame rate, 1% lows, frame-time trace, GPU utilization, GPU power, CPU utilization, and temperature
5. Idle and loaded wall power if a power meter is available

Alternate enclosure order between runs after the first warm-up rather than completing every run on one enclosure first. Preserve raw results in an artifact linked from this ticket rather than reducing them immediately to one average.

### Linux smoke test

Linux is secondary but should receive a bounded cold-plug test on Omarchy:

1. Install and boot with Intel as Hyprland's primary renderer.
2. Cold-boot with each enclosure attached and authorized.
3. Confirm `lspci`, `boltctl`, `nvidia-smi`, and the external display.
4. Run one sustained real GPU workload.
5. Inspect the kernel journal for `NVRM`, `Xid`, PCIe AER, Thunderbolt, and fallen-off-bus errors.
6. Shut down before disconnecting.

Do not spend the return window debugging Linux if Windows is stable. If Linux fails, verify the Intel-only bypass: boot with the eGPU physically disconnected, use the Sabrent for peripherals and monitor video, and attach the eGPU only before Windows gaming boots.

### Output

A linked results artifact containing the raw measurements and failure log, followed by a keep/return decision that accounts for:

- Whether performance differs beyond run-to-run noise on the current TB4 host
- Windows enumeration, sleep, and sustained-load reliability
- Noise, idle power, charging, physical condition, and cabling
- Whether the 850 T5's future RTX 5080/TB5 path earns its additional cost
- Whether Linux can use the eGPU or should adopt the tested Intel-only bypass
