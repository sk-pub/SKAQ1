## Compiling .mpy files

Requires Digi XBee3 Zigbee 3.0 firmware **1014 or later** (MicroPython 1.20). Use `mpy-cross==1.20.*` ([PyPI](https://pypi.org/project/mpy-cross/)):

```sh
mpy-cross sen5x.py -march=xtensawin -msmall-int-bits=31
```

Files needed on the device:

```
/flash/main.mpy
/flash/lib/scd30.mpy
/flash/lib/sen5x.mpy
/flash/lib/skaq1.mpy
```

## XBee3 module configuration (XCTU)

Function set: **Digi XBee3 Zigbee 3.0** (with MicroPython)

Non-default AT settings:

| AT | Value | Meaning |
| --- | --- | --- |
| `ZS` | 2 | Stack profile = Zigbee PRO (required for z2m) |
| `EE` | 1 | Encryption enabled |
| `EO` | 2 | Use trust center / default Zigbee 3.0 link key |
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
- `ID` = 0 → join any reachable PAN

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
