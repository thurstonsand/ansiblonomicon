---
status: open
type: grilling
blocked-by: []
---

# Locks and entry

## Question

- the two **Schlage Sense Pro** (UWB) locks are installed and set up
- Home Assistant automation locks a door only after its SuperLink sensor reports it closed
- both garage-door ratgdos are installed, configured, and working
- a preexisting garage-door fault remains: the obstruction sensors intermittently report an obstruction when the path is clear, leaving the door stuck open. Stable sensor LEDs, clean and aligned lenses, direct sunlight, loose terminals or field wiring under movement, and track vibration have all been checked and ruled out. The investigation has moved to the electrical path: sensor supply voltage, concealed-wire continuity and resistance, opener outlet voltage under motor load, electrical noise, the sensor pair, and finally the opener logic board. A temporary loose sensor cable that bypasses the concealed run is the clean split between wiring and equipment; powering the opener temporarily from a known-good circuit similarly separates house power from the opener. Do not bypass the sensors or treat the ratgdo as the cause without evidence
- during an Internet outage, an open garage door did not automatically close as expected. After repairing the obstruction-sensor fault, identify whether ratgdo or Home Assistant owns the close timer and inspect the failed run's automation trace before changing it. Then test by disconnecting only the WAN while leaving Home Assistant, UniFi, and the garage WLAN running: confirm the ratgdo remains associated, its door and obstruction entities remain available from HA's local address, the timer fires, every condition uses locally available state, and HA sends the close command. Treat remote notifications as optional observability, not part of the close path. The result must distinguish loss of Internet from loss of LAN, Wi-Fi, HA, or power; automatic closing is not expected to survive those different failures without additional local control and backup power
- the enclosed deck has one exterior entrance, then three doors into the house. Locking all three is annoying; locking the single deck door would be simpler, but it's a mesh enclosure — how "reliable" is a lock there? (Windows are arguably the same story; these locks stop good actors more than bad.) Decide what's right, including whether the answer is "not possible."
