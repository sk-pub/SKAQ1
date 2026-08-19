## Compiling .mpy files

Requires Digi XBee3 Zigbee 3.0 firmware **1014 or later** (MicroPython 1.20). Use `mpy-cross==1.20.*` ([PyPI](https://pypi.org/project/mpy-cross/)):

```sh
mpy-cross sen5x.py -march=xtensawin -msmall-int-bits=31
```

Files needed on the device:

```
/flash/main.mpy
/flash/lib/eventlog.mpy
/flash/lib/scd30.mpy
/flash/lib/sen5x.mpy
/flash/lib/skaq1.mpy
```

## Event log

Problems (boots, fatal exceptions with traceback, TX failure streaks, network
association changes) are recorded by `eventlog.py` in `/flash/log.txt`, which
survives reboots. Read it over the MicroPython REPL:

```python
import eventlog
eventlog.dump()
```

Timestamps are `up=<seconds since boot>` (no RTC). Space is bounded three ways:
the file is capped at 4 KB (oldest lines dropped), writes are capped at 20 per
boot, and writing stops if flash free space falls below 16 KB. That keeps the
log around 1% of the ~382 KB file system (firmware 1014, per `ATFS INFO`).

Note the XBee3 file system only reclaims deleted-file space at its end, so
remove+rewrite cycles interleaved with other file writes slowly strand dead
space. If `ATFS INFO` ever shows the space missing, `os.format()` and
re-uploading the files above recovers it.

## XBee3 module configuration (XCTU)

Function set: **Digi XBee3 Zigbee 3.0** (with MicroPython)

Non-default AT settings:

| AT | Value | Meaning |
| --- | --- | --- |
| `ZS` | 2 | Stack profile = Zigbee PRO (required for z2m) |
| `EE` | 1 | Encryption enabled |
| `NJ` | 0xFE | Allow joining for 254 s when triggered |
| `NI` | `SKAQ1` / `SKAQ2` / ... | Friendly node identifier; one per physical device |
| `PS` | 1 | MicroPython auto-start on boot |
| `AP` | 4 | API mode: MicroPython REPL |
| `AO` | 7 | Verbose explicit RX (so `rx_callback` sees ZDO + full metadata) |
| `D1` | 6 | DIO1 = I2C SCL |
| `P1` | 6 | DIO11 = I2C SDA |
| `D4` | 4 | DIO4 = digital out, low (onboard blue LED off) |
| `D5` | 3 | DIO5 = digital input (REPL drop-into button, code adds pull-up) |

Defaults that should remain:

- `CE` = 0 → router (mains-powered, always-on)
- `SM` = 0 → no sleep
- `ID` = 0 → join any reachable PAN (pinned automatically after first join, see below)
- `EO` = 0 → join with the well-known link key, without the Zigbee 3.0
  centralized-trust-center link-key update. Digi's Zigbee 3.0 guides say to
  set `EO` bit 1 ("Use Centralized Trust Center"), but with it set the XBee3
  (firmware 1014) requests a trust-center link-key update after joining and
  then fails its Verify Key step against EmberZNet 8.x trust centers
  (`TC_REQUESTER_VERIFY_KEY_FAILURE` on the coordinator) — the device is then
  required to leave, producing an endless join/leave loop. Old pre-R21
  coordinators (e.g. CC2531) never offered the update, which masked this.
  With `EO` = 0 the join completes and traffic is normal (NWK encrypted).
  Every `EO` value with bit 1 set fails the same way (0x02, 0x06, 0x0E,
  0x12 tested); bits 2 and 3 are trust-center-side only and don't affect
  a joiner.

Set automatically by the firmware after every successful join
(`configure_network_selfheal` in `skaq1.py`, no XCTU steps needed):

| AT | Value | Meaning |
| --- | --- | --- |
| `ID` | network ext PAN | Pinned to the joined network's extended PAN ID (`OP`); never joins a foreign network again |
| `JV` | 1 | Verify coordinator on boot, rejoin if missing |
| `NW` | 30 | Network watchdog: self-rejoin after 3×30 min without coordinator contact |
| `DC` | bit 5 set (OR-ed into existing value) | Watchdog rejoins without leaving the network (avoids stranding) |

### Moving a device to another network

The pinned `ID` means the device only ever looks for its original network.
That's the right behavior when the coordinator hardware is replaced but the
network itself survives — i.e. Z2M's coordinator backup is restored onto the
new dongle (same PAN, keys, channel): devices rejoin on their own, nothing
to do.

If the network genuinely changes — fresh Z2M install, new network created
without restoring the backup, changed PAN/security settings — the device
keeps searching for the old network forever and must be re-pointed once,
via XCTU or the MicroPython REPL:

1. Clear the pin: set `ID` to 0 (REPL: `xbee.atcmd('ID', b'\x00' * 8)`).
2. Persist it: write settings (REPL: `xbee.atcmd('WR')`).
3. Leave the old network and rescan: `NR` (REPL: `xbee.atcmd('NR', 0)`).
4. Enable permit join in Z2M. After the device joins, the firmware
   re-pins `ID` to the new network automatically — no further steps.

## Hardware wiring (current build)

```
XBee3 Thing Plus           SEN55                SCD30
────────────────────       ──────────           ──────────
VUSB pin       ─────●────► VDD     ────────────► VDD
GND pin        ─────●────► VSS     ────────────► GND
SDA pin        ─────●────► SDA     ────────────► SDA
SCL pin        ─────●────► SCL     ────────────► SCL
                           SEL ──► VSS (I2C mode)
                                                 SEL ──► GND (I2C mode)

                     ━━┻━━ 22-100 µF electrolytic across VUSB-GND, near SEN55
```

I2C addresses: SCD30 = `0x61`, SEN55 = `0x69`. The bare Sensirion SCD30 and SEN55 modules don't include I2C pull-ups, but the XBee3 Thing Plus has them on the bus (same electrical net for both the Qwiic port and the SDA/SCL header pins), so no external resistors are needed regardless of which tap point you wire to.
