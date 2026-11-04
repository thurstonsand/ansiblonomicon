# Framework 13 Pro speaker tuning

`framework-speakers.conf` and `framework-speakers.irs` are the Dynamic profile with Balanced voicing for the Framework Laptop 13 Pro (Intel Core Ultra Series 3), Realtek ALC285 subsystem `F111000F`. They run inside PipeWire, with `lsp-plugins-lv2` from `loadout.toml`; EasyEffects and Calf are not required for this chain.

The filter attaches to the built-in analog sink. `../wireplumber/framework-speakers.lua` enables it only while that card's active route is `analog-output-speaker`, because the headphone jack shares the same sink. Other outputs bypass it. The filter starts disabled until WirePlumber has identified the route, and its playback cannot fall back to another device. Keep the real audio device selected as the output, not the filter itself.

## Source and regeneration

- Converter: [speaker-tuning-to-easyeffects](https://github.com/antoinecellerier/speaker-tuning-to-easyeffects), revision `a113b2ed1973de2322cf2d7e82da1f7870c55916`.
- Hardware report: [issue 73](https://github.com/antoinecellerier/speaker-tuning-to-easyeffects/issues/73).
- Input: [DEV_0285_SUBSYS_F111000F_PCI_SUBSYS_000FF111.xml](https://github.com/user-attachments/files/31421115/DEV_0285_SUBSYS_F111000F_PCI_SUBSYS_000FF111.xml), extracted by the reporter from Framework's Windows driver bundle. SHA256: `30c9c38fe21ac32e5785c5efcee0d20f7eb0cfd6271d59c721496de735f9b008`.

From a checkout of that converter revision, with the XML downloaded as `framework-13-pro.xml`:

```sh
uv run --no-project --with numpy --with scipy dolby_to_pipewire.py framework-13-pro.xml \
  --profile dynamic --variant balanced --prefix Framework13Pro \
  --output-dir ./generated --no-activate
```

Copy the generated conf and IRS to these source files. In the conf, change both IRS paths to `/home/thurstonsand/.config/pipewire/pipewire.conf.d/framework-speakers.irs`, add `filter.smart.disabled = true` to `capture.props`, and add `node.dont-fallback = true` and `node.linger = true` to `playback.props`. Preserve the provenance pointer in the header. Do not hand-edit the generated DSP controls. The impulse response SHA256 is `ea939f560370095584608498a0e38496a0cf096d066be769ac392ff02fad0b0c`.

This is an approximation of the Windows processing, not complete Dolby Atmos. The converter deliberately leaves dialog enhancement, autogain, and experimental virtual bass off. It retains the manufacturer's +4 dB loudness boost and includes a final limiter.

## Apply and verify

`mise omarchy -t omarchy-loadout,omarchy-config` deploys the dependencies and links. After changing the audio files, restart `pipewire`, `pipewire-pulse`, and `wireplumber` user services; this briefly interrupts audio. No microphone settings are owned by this tuning.

`pw-metadata -n filters` shows `filter.smart.disabled=false` on speakers and `true` on the headphone route. `wpctl status -n` shows the filter and the real output. Check the actual links with `pw-link -l` during playback: applications → filter → built-in sink on speakers, applications → built-in sink on headphones. Switching back must re-enable it. A temporary null sink can check that other outputs bypass the filter without needing a physical headset.

When measuring, use `pw-record --target 0` and explicitly connect the real sink's `monitor_FL`/`monitor_FR` ports with `pw-link`. Recording its monitor through PulseAudio gets redirected to the filter's input monitor by smart-filter routing, making an active filter appear to do nothing. A quiet four-tone test on this host measured approximately +3.98 dB at 250 Hz, +2.03 dB at 1 kHz, −4.74 dB at 3.5 kHz, and +1.96 dB at 8 kHz; this verifies processing, not perceived sound quality.

For a listening comparison, temporarily move the deployed `~/.config/pipewire/pipewire.conf.d/framework-speakers.conf` symlink outside that directory and restart the audio services. Move it back and restart to restore tuning. Reconciliation also restores the link. Permanently removing the tuning requires retiring its four dotfile declarations, not just deleting their sources.
