---
name: operating-the-printer
description: Reaches the Canon MF654Cdw on Scanners, drives its Remote UI, and reads its state over IPP and mDNS. Use when printing or scanning is broken, when a printer setting needs checking or changing, or when the printer appears offline.
---

# Operating the printer

A Canon imageCLASS MF654Cdw, advertised as `Canon MF650C Series`, sits on Scanners at `10.10.40.187` (`printer.thurstons.house`, hostname `Canonc24a79.local`, MAC `14:d4:24:f2:6f:e6`). It is declared as `unifi_client.canon_printer` in `terraform/unifi/clients.tf`.

## Reaching it

Bunker cannot initiate toward Scanners, so pod042 cannot talk to the printer from its own address. Its probe namespace holds a leg on every client VLAN, and the `scanners` leg is the way in:

Run the commands below directly on pod042. From an orb or another host, execute them on pod042 through `agents/homelab/skills/operating-pod042/scripts/with-pod042-access ssh --`.

```sh
sudo -n net-probe ping -c2 10.10.40.187
sudo -n net-probe curl -s http://10.10.40.187/
sudo -n net-probe tcpdump -ni scanners udp port 5353   # watch the gateway's mDNS on the segment
```

The namespace is declared in `bootstrap/targets/pod042/network/probe.py` and holds no service of its own. It is also the only vantage that can watch the gateway's mDNS traffic on Scanners.

`Host is unreachable` means the printer is answering no ARP, which it does whenever its radio is unwell or it is asleep. Unicast still works once something can resolve it, so install the neighbour entry by hand:

```sh
sudo -n net-probe ip neigh replace 10.10.40.187 lladdr 14:d4:24:f2:6f:e6 dev scanners nud stale
```

Auto Sleep Time is 10 minutes. Any unicast request wakes it, so the first HTTP call after a quiet spell may be the one that revives it.

## Remote UI

`http://10.10.40.187/`. The password lives in 1Password and is declared as `CANON_REMOTE_UI_PASSWORD` in `fnox.pod042.toml`; resolve it through fnox and pipe it into the script rather than putting it on a command line:

```sh
./scripts/fnox-host exec --secret CANON_REMOTE_UI_PASSWORD -- sh -c \
  'printf "%s\n" "$CANON_REMOTE_UI_PASSWORD" | sudo -n net-probe python3 /tmp/task.py'
```

Log in by posting to `/checkLogin.cgi` and keeping the cookie jar. System Manager Mode is `{"i0012": "1", "i2101": PIN}`; General User Mode is `{"i0017": "2", "i0019": "", "i2101": PIN}` and sees almost nothing. A rejected login redirects to `/login.html?err=1` rather than returning an error status, so check the final URL.

Settings/Registration is `/p_paper_select.html`, which carries the whole settings menu in its sidebar. The pages worth knowing:

| Page | Holds |
| --- | --- |
| `/p_timer.html` | Auto Sleep Time, auto shutdown, sleep exit time |
| `/m_network.html` | index of every network page below |
| `/m_network_airprint.html` | Use AirPrint, printer name, location |
| `/m_network_wirelesslan.html` | SSID, channel, security, Power Save Mode |
| `/m_network_escl.html` | AirScan |
| `/m_network_ipp_print.html` | IPP and IPPS |
| `/m_network_multicast.html` | Canon's own discovery response, not mDNS |
| `/m_network_sleep_notif.html` | the UDP broadcast Canon's app uses to wake it |
| `/firewall.html`, `/m_security.html` | address filters and TLS |

Most pages are read-only over HTTP. Wireless settings in particular can only be changed at the panel: Menu > Preferences > Network > Wireless LAN Settings.

Restarting is scriptable, takes about ninety seconds, and is the way to make a panel-side change take effect without walking to the machine. Read `/restart_device.html` for the `iToken` value, then post that token to `/cgi/restart_device.cgi`.

## Reading state without the UI

IPP answers on 631 and is the fastest way to confirm the printer is healthy and knows how to print. Post a `Get-Printer-Attributes` operation to `/ipp/print`; the response names `printer-make-and-model` and lists `urf-supported`, which is what AirPrint needs. Ports 80, 443, 631, 9100 (RAW) and 515 (LPD) are open; 5353 is UDP only.

Over mDNS it answers direct queries for `_ipp._tcp`, `_ipps._tcp`, `_universal._sub._ipp._tcp`, `_uscan._tcp`, `_scanner._tcp` and `_printer._tcp`, giving a complete instance, SRV and A set. It never answers `_services._dns-sd._udp` enumeration, which is why the beacon exists: the gateway browses only the types enumeration returns, so without the beacon the printer is absent from the gateway's cache and invisible to every other VLAN.

## Traps already paid for

The printer answers unicast perfectly while ignoring every broadcast and multicast frame when its Wi-Fi group key is wrong. That state looks exactly like a dead printer to AirPrint and a healthy one to the Canon app, IPP and the Remote UI. Scanners runs plain WPA2 for this reason; WPA3 transition mode broke it for four days. If discovery fails again, ask whether the printer answers a multicast query before suspecting anything upstream of it, and compare against another Scanners device, since the ones that fail and the ones that work will disagree on exactly that.

Its connection method is a setting, not a cable. Set to wired with no cable attached, it sits silently off the network with no indication beyond its absence from the controller.
