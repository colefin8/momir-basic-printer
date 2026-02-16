# Scryfall Thermal Printer

Prints a random Magic: The Gathering creature by mana value on a thermal printer. This is designed for Momir Basic style play in paper, where you roll or choose a mana value and reveal a random creature to represent the token you get.

This tool:

- Queries Scryfall for a random creature card by mana value.
- Renders a receipt-style image with the art and rules text.
- Prints to ESC/POS thermal printers over USB or network, or saves a PNG for testing.

See the Momir Basic rules here: https://magic.wizards.com/en/formats/momir-basic

## Requirements

- Python 3.9+
- A USB or network ESC/POS thermal printer (58mm or 80mm)

## Windows setup

### 1) Install Python

Install Python 3.9+ using one of these options:

- Microsoft Store (simple, auto-updates)
- python.org installer (check "Add Python to PATH")

Verify:

```powershell
python --version
pip --version
```

### 2) Create and activate a virtual environment

A virtual environment keeps this app's dependencies isolated from other Python projects on your machine.

```powershell
cd scryfall-thermal
python -m venv .venv
```

Activate it:

```powershell
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, run one of these and try again:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

or for this session only:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
```

### 3) Install the app

```powershell
pip install -U pip
pip install -e .
```

### 4) Test the app (no printer required)

```powershell
scryfall-thermal --mv 3 --dry-run --output output.png
```

### 5) Print to a printer

USB format: `usb:0x1234:0xabcd`
Network format: `net:192.168.1.50:9100`

Example:

```powershell
scryfall-thermal --mv 2 --printer usb:0x04b8:0x0202
```

## Raspberry Pi Lite setup (headless)

The steps below assume Raspberry Pi OS Lite (no desktop) and SSH access.

### 1) Update system packages

```bash
sudo apt update
sudo apt upgrade -y
```

### 2) Install Python and system deps

```bash
sudo apt install -y python3 python3-venv python3-pip
```

If you are using the Scryfall symbol cache, CairoSVG requires extra system packages:

```bash
sudo apt install -y libcairo2 libffi-dev libgdk-pixbuf2.0-0 libpango-1.0-0 libpangocairo-1.0-0
```

### 3) Clone and create a virtual environment

```bash
git clone <YOUR_REPO_URL>
cd scryfall-thermal
python3 -m venv .venv
source .venv/bin/activate
```

### 4) Install the app

```bash
pip install -U pip
pip install -e .
```

### 5) Test without a printer

```bash
scryfall-thermal --mv 3 --dry-run --output output.png
```

### 6) Print to a printer

USB format: `usb:0x1234:0xabcd`
Network format: `net:192.168.1.50:9100`

Example:

```bash
scryfall-thermal --mv 2 --printer net:192.168.1.50:9100
```

## Hardware mode (Raspberry Pi 3 B)

Use a rotary encoder and a 2-digit 7-segment display (common cathode) to select mana value and trigger printing.

Default GPIO mapping (BCM numbering):

- Encoder A/CLK: GPIO17
- Encoder B/DT: GPIO18
- Encoder SW: GPIO27
- Segments a,b,c,d,e,f,g,dp: GPIO5, GPIO6, GPIO13, GPIO19, GPIO26, GPIO12, GPIO16, GPIO20
- Digit commons D1,D2: GPIO21, GPIO25

Wiring notes:

- The encoder A/B/SW lines should use pull-ups (gpiozero defaults to pull-ups).
- Use 220-330 ohm resistors for each segment line.
- Because this is a bare 2-digit display, you must multiplex the digits.
- Use NPN transistors (e.g., 2N2222) to switch each digit common cathode.

Run in hardware mode:

```bash
scryfall-thermal --hardware --dry-run --output output.png
```

If you have a printer later:

```bash
scryfall-thermal --hardware --printer usb:0x1234:0xabcd
```

Override pins if needed:

```bash
scryfall-thermal --hardware --seg-pins 5,6,13,19,26,12,16,20 --digit-pins 21,25
```

## Run on startup (systemd)

Create a systemd unit file at `/etc/systemd/system/scryfall-thermal.service`:

```ini
[Unit]
Description=Scryfall Thermal Hardware UI
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=colefin8
WorkingDirectory=/home/colefin8/scryfall-thermal
ExecStart=/home/colefin8/scryfall-thermal/.venv/bin/scryfall-thermal --hardware --dry-run --output /home/colefin8/output.png
Restart=on-failure
RestartSec=2

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now scryfall-thermal
```

Check status/logs:

```bash
systemctl status scryfall-thermal
journalctl -u scryfall-thermal -b
```

## Notes

- Default render width is 384px (58mm printers). Use `--width 576` for 80mm printers.
- If the printer is not connected, use `--dry-run` to validate output.
- A symbology snapshot is bundled at `src/scryfall_thermal/assets/symbology.json` so new clones do not need to fetch the symbol list. PNGs are still downloaded on first use and cached locally. Set `SCRYFALL_SYMBOLS_DIR` to override the cache directory.
- Refresh the snapshot with: `curl -L https://api.scryfall.com/symbology -o src/scryfall_thermal/assets/symbology.json`
