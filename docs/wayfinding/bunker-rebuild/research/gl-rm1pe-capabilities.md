# GL.iNet GL-RM1PE capabilities and safe bootstrap

Research date: 2026-09-04

## Verdict

The GL-RM1PE can use one ordinary Ethernet cable for both data and power from the UniFi Pro Max 24 PoE. GL.iNet specifies a 10/100/1000 Mbps, IEEE 802.3af/at PoE port and less than 5 W consumption. Every copper port on that switch can supply at least PoE+, so a 1 GbE PoE+ port is sufficient. A 2.5 GbE or PoE++ port adds no KVM capability. The actual link may negotiate down if the cable or port is defective or constrained, so bring-up should still verify a 1 GbE link in UniFi rather than turn the advertised maximum into an observed fact. [GL-RM1PE datasheet](https://static.gl-inet.com/www/images/products/datasheet/rm1pe_datasheet_20251110.pdf) [UniFi Pro Max 24 PoE specifications](https://techspecs.ui.com/unifi/switching/usw-pro-max-24-poe)

The current firmware has first-party Tailscale support and exposes the complete console through a browser at the appliance's Tailscale address. That is the best-supported non-GL.iNet-cloud path to prototype. A Cloudflare Access public hostname can plausibly carry the web application and WebSockets, but GL.iNet's preferred console media mode is WebRTC, whose media path does not travel through a normal HTTP reverse proxy. Neither vendor documents the GL-RM1PE local console behind Cloudflare Tunnel, and GL.iNet does not publish the transport used by its `Direct` video mode or browser virtual-media uploads. Cloudflare therefore remains a prototype target, not a proven permanent path. [GL.iNet Tailscale instructions](https://docs.gl-inet.com/kvm/en/faq/remote_access_to_controlled_device_via_tailscale/) [GL-RM1PE console guide](https://docs.gl-inet.com/kvm/en/user_guide/gl-rm1pe/control_panel_guide/) [Cloudflare Tunnel WebSocket FAQ](https://developers.cloudflare.com/cloudflare-one/faq/cloudflare-tunnels-faq/) [Cloudflare explanation of WebRTC bypassing HTTP/HTTPS proxies](https://developers.cloudflare.com/cloudflare-one/remote-browser-isolation/network-dependencies/)

## Power and network

- The Ethernet interface is one 1 Gbps copper port supporting 10/100/1000 Mbps and 802.3af/at PoE. GL.iNet lists appliance consumption as less than 5 W. It does not publish the powered-device class or requested PoE allocation, so the exact negotiated allocation must be read from UniFi after attachment. The useful capacity figure is under 5 W, not an invented PoE class. [GL-RM1PE datasheet](https://static.gl-inet.com/www/images/products/datasheet/rm1pe_datasheet_20251110.pdf)
- GL.iNet explicitly describes the PoE model as receiving power and network over one Ethernet cable and instructs users to connect it directly to a PoE switch. No injector or separate USB supply is required. [GL-RM1PE user guide](https://docs.gl-inet.com/kvm/en/user_guide/gl-rm1pe/) [quick setup](https://docs.gl-inet.com/kvm/en/user_guide/gl-rm1pe/quick_setup_guide)
- The alternate input is USB-C, 5 V/2 A. The product page calls it optional and PD-compatible, and the datasheet says PoE and the adapter may be used simultaneously for uninterrupted operation. This is an alternate or redundant input, not part of the normal one-cable installation. [GL-RM1PE product page](https://www.gl-inet.com/en-us/products/gl-rm1pe) [GL-RM1PE datasheet](https://static.gl-inet.com/www/images/products/datasheet/rm1pe_datasheet_20251110.pdf)
- The UniFi switch has sixteen 1 GbE ports, eight PoE+ and eight PoE++, plus eight 2.5 GbE PoE++ ports. Ubiquiti specifies 32 W per PoE+ PSE port, 60 W per PoE++ port, and a 400 W total PoE budget. Thus even a 1 GbE PoE+ port exceeds the GL-RM1PE's standard and consumption requirements by a wide margin. The shared budget must have room for the allocation that the switch negotiates. Because GL.iNet does not publish the PD class, that reservation could exceed the appliance's less-than-5-W actual draw and must be read from UniFi rather than calculated from the available specifications. [UniFi Pro Max 24 PoE specifications](https://techspecs.ui.com/unifi/switching/usw-pro-max-24-poe)
- `poe_mode = "auto"` is the appropriate UniFi behavior because the appliance is a standards-based 802.3af/at powered device. Do not use passive PoE. Assign `pod042-kvm` a non-fast Bunker 1 GbE PoE+ port and reserve 2.5 GbE for clients that can use it.

## Physical connections to `pod042`

1. Connect the GL-RM1PE Ethernet/PoE port to its UniFi PoE port. This powers the KVM independently of the NAS.
2. Connect `HD IN` to one of `pod042`'s HDMI outputs. The appliance captures up to 4K at 30 fps and encodes H.264. [GL-RM1PE product page](https://www.gl-inet.com/en-us/products/gl-rm1pe)
3. Connect the GL-RM1PE USB 2.0 Type-C device port to a USB host port on `pod042`, using the included Type-A-to-Type-C or Type-C-to-Type-C cable as appropriate. This connection presents keyboard, mouse, and virtual storage to the NAS. GL.iNet documents the USB connection as mandatory in quick setup and documents the virtual-media device as a read/write USB drive or read-only emulated CD/DVD/disk visible during BIOS/UEFI startup. [quick setup](https://docs.gl-inet.com/kvm/en/user_guide/gl-rm1pe/quick_setup_guide) [console guide, Virtual Media](https://docs.gl-inet.com/kvm/en/user_guide/gl-rm1pe/control_panel_guide/)
4. For physical ATX control, install the optional GL-ATXPC inside the chassis. Its Type-C interface connects to the KVM's USB 2.0 Type-A extension port. Its two interchangeable headers sit inline between the case's front-panel control lead and the motherboard F_PANEL header. Preserve the motherboard silkscreen orientation and check polarity. The board simulates power-button and reset operations; the console exposes short power press, long power press, and restart. [GL-ATXPC guide](https://docs.gl-inet.com/kvm/en/user_guide/gl-atx-board/) [GL-RM1PE console guide, ATX Power](https://docs.gl-inet.com/kvm/en/user_guide/gl-rm1pe/control_panel_guide/)

ATX wiring is optional. Without it, KVM, HID, virtual media, and console video still work; Wake-on-LAN is also built in. WOL cannot recover a host whose firmware/NIC will not wake, while the inline ATX board can simulate the physical switches. [GL-RM1PE console guide](https://docs.gl-inet.com/kvm/en/user_guide/gl-rm1pe/control_panel_guide/)

## Safe first boot, reset, and recovery

### Record before changing anything

Photograph the bottom label and record serial number, MAC address as observed by UniFi, assigned IP, device ID/identity, hostname, installed firmware version and channel, cloud-binding state, Tailscale/ZeroTier/NetBird binding state, and whether an ATX board is present. In the upgrade dialog, use **Save current configuration** before reset. Copy off any useful virtual-media files and export troubleshooting logs if they matter. GL.iNet says the configuration-save option preserves cloud-account binding, but does not document the backup format or a complete list of retained fields. Treat it as a recovery artifact, not a proven full appliance clone. [firmware upgrade guide](https://docs.gl-inet.com/kvm/en/faq/firmware_upgrade/) [console guide](https://docs.gl-inet.com/kvm/en/user_guide/gl-rm1pe/control_panel_guide/)

The serial number is printed on the device label and supports account binding, so it is hardware identity rather than ordinary mutable configuration. No official GL.iNet source found says that a factory reset erases the serial number, a license, calibration data, or U-Boot. No product license is documented. Conversely, no official source promises that every pairing or local file survives. Preserve the facts above, then reset. [quick setup, S/N binding](https://docs.gl-inet.com/kvm/en/user_guide/gl-rm1pe/quick_setup_guide)

### Reset and first login

- Prefer the authenticated console's **Settings > System > Reset KVM** control. GL.iNet identifies this as a one-click factory reset. The hardware alternative is to let the device finish booting, then hold Reset for at least eight seconds. [console guide](https://docs.gl-inet.com/kvm/en/user_guide/gl-rm1pe/control_panel_guide/) [GL-RM1PE datasheet](https://static.gl-inet.com/www/images/products/datasheet/rm1pe_datasheet_20251110.pdf)
- Do not hold Reset while applying power for an ordinary reset. On the GL-RM1PE that sequence deliberately enters U-Boot failsafe after five blue flashes. Confusing recovery with reset is the principal bootstrap hazard. Do not remove power during reset or firmware writes. [U-Boot recovery guide](https://docs.gl-inet.com/kvm/en/faq/debrick/)
- After reset, DHCP supplies an address. Browse from the same LAN to `glkvm.local` or the leased IP. First access requires creation of an admin password; the documentation does not publish a default password. Chrome and Edge are the recommended browsers. [quick setup](https://docs.gl-inet.com/kvm/en/user_guide/gl-rm1pe/quick_setup_guide)
- Set hostname `pod042-kvm`. Keep DHCP and let UniFi own the stable network identity rather than configuring a second static-address source on the appliance. The console also supports a device-side static IPv4 configuration if ever required. [console guide, Network](https://docs.gl-inet.com/kvm/en/user_guide/gl-rm1pe/control_panel_guide/)

### Firmware and recovery

Use the stable RM1PE channel. The console checks for online updates; **Update Settings** also supports a downloaded local image, an explicitly less-stable beta program, and configuration save. Do not join beta on the permanent out-of-band console. [official RM1PE stable download channel](https://dl.gl-inet.com/kvm/rm1pe/stable) [firmware upgrade guide](https://docs.gl-inet.com/kvm/en/faq/firmware_upgrade/)

Recovery exists at two levels:

- U-Boot failsafe: remove power, directly connect a computer by Ethernet, hold Reset while powering on, release after the five-flash sequence, set the computer to `192.168.1.2`, and upload the model-correct firmware. GL.iNet says configuration is typically retained, but “typically” is not a guarantee. [U-Boot recovery guide](https://docs.gl-inet.com/kvm/en/faq/debrick/)
- RKDevTool loader: if ordinary updates and U-Boot fail, GL.iNet documents a Windows-only Rockchip recovery using a USB data cable, a separate power adapter, and the Type-C OTG port. Holding Reset for ten seconds while applying power enters loader mode. Disconnecting USB or power during flashing may damage the device. [RKDevTool recovery guide](https://docs.gl-inet.com/kvm/en/tutorials/how_to_debrick_kvm_via_rkdevtool/)

These paths make a clean factory reset reasonable after recording state. They also make arbitrary shell customization unattractive: the official recovery guide names DIY changes and wrong firmware as causes of bricking.

## Local administration and automation boundary

The supported local interface is the HTTPS browser console at `glkvm.local` or the DHCP address. It manages video and EDID, HID, device identity, time zone, Ethernet DHCP/static addressing, WOL, ATX actions, virtual media, firmware, cloud status, password, 2FA, TLS certificates, reboot, and log export. It also has an authenticated browser **Toolbox > Terminal** for advanced settings. [local browser guide](https://docs.gl-inet.com/kvm/en/faq/local_access_to_controlled_device_via_browser/) [console guide](https://docs.gl-inet.com/kvm/en/user_guide/gl-rm1pe/control_panel_guide/)

GL.iNet publishes [`gl-inet/glkvm`](https://github.com/gl-inet/glkvm), a PiKVM-derived server containing authenticated HTTP and WebSocket APIs, but its README does not promise that those endpoints are a stable or complete management API for RM1PE firmware. The official appliance documentation does not document SSH, API compatibility/versioning, unattended configuration import, or a command-line backup restore. A browser terminal is not the same promise as an externally supported SSH service. Accordingly:

- use the console's documented configuration save and local firmware upload;
- leave appliance configuration manual;
- do not put credentials into Ansible or automate private HTTP endpoints until a prototype identifies a vendor-supported contract;
- let this repository manage only UniFi identity, port profile, PoE, and name.

That boundary is deliberate. Reverse engineering a permanent console into compliance would make recovery depend on the thing intended to provide recovery. A small triumph of recursion, but not operations.

## Remote access without GL.iNet Cloud

### Tailscale: documented and direct

RM1PE firmware integrates Tailscale under **Apps Center > Tailscale**. Bind the KVM and controlling client to the same tailnet, then open the KVM's Tailscale IPv4, IPv6, or MagicDNS name in a browser and authenticate with the appliance admin password. GL.iNet explicitly says neither its app nor its cloud service is required. The Apps Center also exposes exit-node and subnet-route options, though this installation needs neither for access to the KVM itself. [GL.iNet Tailscale instructions](https://docs.gl-inet.com/kvm/en/faq/remote_access_to_controlled_device_via_tailscale/) [console guide, Apps Center](https://docs.gl-inet.com/kvm/en/user_guide/gl-rm1pe/control_panel_guide/)

Tailscale is WireGuard-based, so it gives the browser IP reachability to the same local service instead of reverse-proxying selected HTTP requests. This preserves whatever same-origin HTTP, WebSocket, WebRTC, and upload behavior the console uses. Apply a tailnet ACL/grant restricted to Thurston's administering devices and `pod042-kvm`; do not advertise the Bunker subnet from this recovery appliance unless a later design explicitly calls for it.

ZeroTier and NetBird are also integrated non-GL-cloud overlays and expose the browser console at their assigned virtual IPs. They are viable protocol-level alternatives, but there is no reason to add another control plane before the Tailscale prototype. [quick setup](https://docs.gl-inet.com/kvm/en/user_guide/gl-rm1pe/quick_setup_guide) [console guide, Apps Center](https://docs.gl-inet.com/kvm/en/user_guide/gl-rm1pe/control_panel_guide/)

GL.iNet also publishes a self-hosted cloud server. Its official deployment requires HTTP/HTTPS plus TCP/UDP 3478 for TURN/WebRTC, confirming that GL.iNet remote video can require a non-HTTP media relay. Self-hosting still adds an Internet service and is unnecessary when Tailscale gives direct private reachability. [gl-inet/glkvm-cloud README](https://github.com/gl-inet/glkvm-cloud/blob/main/README.md)

### Cloudflare Tunnel/Access: compatible pieces, unproven whole

GL.iNet documents three video transfers: `WebRTC`, `WebRTC (FEC)`, and `Direct`. WebRTC carries video and audio; FEC adds redundant media packets; Direct has the lowest latency and lossless video but no audio. GL.iNet does not document Direct's wire protocol. The browser also uploads local files/ISO images into RM1PE storage and the KVM then exposes that storage over USB, but the guide does not identify the browser upload protocol. [console guide, Video and Virtual Media](https://docs.gl-inet.com/kvm/en/user_guide/gl-rm1pe/control_panel_guide/)

Cloudflare Tunnel can publish the local HTTP/HTTPS application, and Cloudflare says Tunnel fully supports WebSockets. Access can therefore protect the login page and any same-origin HTTP/WebSocket control channel. [Cloudflare published-application protocols](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/routing-to-tunnel/protocols/) [Cloudflare Tunnel FAQ](https://developers.cloudflare.com/cloudflare-one/faq/cloudflare-tunnels-faq/)

That is not enough to claim complete KVM compatibility:

- WebRTC normally negotiates media separately and prefers UDP. Cloudflare itself documents that WebRTC traffic does not flow through normal HTTP/HTTPS proxies. A public-hostname Tunnel is not a generic WebRTC TURN relay. [Cloudflare WebRTC network dependencies](https://developers.cloudflare.com/cloudflare-one/remote-browser-isolation/network-dependencies/)
- GL.iNet's self-hosted cloud opens both TCP and UDP 3478 for TURN. A Cloudflare hostname pointed only at the KVM's web origin does not reproduce that design. [gl-inet/glkvm-cloud README](https://github.com/gl-inet/glkvm-cloud/blob/main/README.md)
- Direct mode might stay inside an HTTP-compatible connection, but no primary source says so. Virtual-media upload might be ordinary HTTP, but no primary source says so either. Large ISO behavior through Cloudflare must be measured, including upload limits and interruption recovery.

The later prototype should therefore test login, keyboard/mouse, WebRTC video and audio, Direct video, an ISO larger than the intended Debian installer, mount through BIOS, and reconnect after idle periods. Until all pass, Cloudflare is an experimental convenience path. Tailscale is the documented non-vendor-cloud recovery path.

## Security baseline

1. Update from stable firmware before exposing remote access. Avoid beta and preserve the downloaded model-correct recovery image.
2. Set a unique high-entropy admin password on first login, enable the console's 2FA, and store recovery material in 1Password. GL.iNet documents both controls. [quick setup](https://docs.gl-inet.com/kvm/en/user_guide/gl-rm1pe/quick_setup_guide) [console guide, Security](https://docs.gl-inet.com/kvm/en/user_guide/gl-rm1pe/control_panel_guide/)
3. Replace the pre-installed default TLS certificate with a trusted custom certificate if clients will address a stable DNS name. Expect a browser privacy warning otherwise; the console supports certificate and private-key upload. [console guide, Security](https://docs.gl-inet.com/kvm/en/user_guide/gl-rm1pe/control_panel_guide/)
4. Do not bind GL.iNet Cloud. If the received unit is already bound, record that fact, save configuration, reset it, and confirm the cloud status is unbound. Enable only Tailscale for the first remote prototype.
5. Put `pod042-kvm` on the Bunker access network with no inbound Internet port forward. Limit cross-network access to the administration path and required outbound DNS/NTP/update/Tailscale traffic. The KVM controls pre-boot input, virtual media, and physical power, so compromise is equivalent to hands at the server.
6. Disable unused overlays and features, including ZeroTier, NetBird, exit-node/subnet routing, microphone, mouse jiggler, and writable virtual media. Remove uploaded ISO and shared files after use.
7. Verify after hardening that the KVM remains powered, reachable, and able to operate ATX controls while `pod042` is shut down. This proves the out-of-band path does not quietly depend on the machine it is meant to recover.

## Installation facts to verify on hardware

The primary sources leave a few runtime facts for ticket 29 rather than licensing guesses as documentation:

- UniFi reports a 1 GbE negotiated link, 802.3af or 802.3at mode, actual allocated wattage, and less than 5 W draw.
- The saved configuration can be restored after this firmware's reset, and the serial/device identity remains unchanged.
- Stable firmware version and checksum correspond to the current official RM1PE download.
- The chosen `pod042` HDMI output displays BIOS/UEFI, USB HID works there, and a mounted ISO appears as a boot device.
- The particular motherboard F_PANEL polarity and ATX board's short press, long press, and restart behave as intended.
- Tailscale works after a cold boot with GL.iNet Cloud unbound and while the NAS is off.
- Cloudflare's candidate route passes the full test matrix above. No source reviewed establishes that result in advance.
