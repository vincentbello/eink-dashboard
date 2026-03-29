# e-ink Fridge Dashboard

A Raspberry Pi–powered always-on fridge display showing:

- **Clock & date** (header)
- **Current weather** (Open-Meteo, no API key)
- **Google Calendar events** (today's schedule)
- **NYC Subway arrivals** (MTA GTFS-RT)
- **Citi Bike availability** (GBFS, no API key)

Target hardware: Raspberry Pi 4 + Waveshare 7.5-inch V2 e-ink display (800×480 px).

---

## Table of Contents

1. [Hardware requirements](#1-hardware-requirements)
2. [MTA API key and stop ID](#2-mta-api-key-and-stop-id)
3. [Citi Bike station IDs](#3-citi-bike-station-ids)
4. [Google Calendar OAuth setup](#4-google-calendar-oauth-setup)
5. [Installation](#5-installation)
6. [Testing with mock_display.py](#6-testing-with-mock_displaypy)
7. [Configuration reference](#7-configuration-reference)
8. [Finding your subway stop ID](#8-finding-your-subway-stop-id)

---

## 1. Hardware requirements

| Component | Notes |
|-----------|-------|
| Raspberry Pi 4 (2 GB+ RAM) | Also works on Pi 3B+ or Pi Zero 2W |
| Waveshare 7.5-inch e-Paper HAT V2 | 800×480, black & white |
| MicroSD card (16 GB+) | Raspberry Pi OS (Bookworm, 64-bit) recommended |
| Power supply | Official 5 V / 3 A USB-C PSU for Pi 4 |

### Wiring (HAT)

The Waveshare 7.5-inch HAT connects directly to the 40-pin GPIO header —
no additional wiring is required. It uses the SPI bus.

Enable SPI before running the dashboard:

```bash
sudo raspi-config nonint do_spi 0
sudo reboot
```

---

## 2. MTA API key and stop ID

### Get a free MTA API key

1. Go to <https://api.mta.info/#/signup> and create a free account.
2. Once logged in, navigate to **My Account → API Keys** and generate a key.
3. Copy the key into `config.py` as `MTA_API_KEY`, or export it as an
   environment variable:

   ```bash
   export MTA_API_KEY="your_key_here"
   ```

### Choose the correct feed URL

Each subway line group has its own GTFS-RT feed. Update `SUBWAY_LINE_FEED_URL`
in `config.py` for the line(s) serving your stop:

| Lines | Feed URL |
|-------|----------|
| 1 / 2 / 3 / 4 / 5 / 6 / 7 | `https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs` |
| A / C / E | `https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-ace` |
| B / D / F / M | `https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-bdfm` |
| G | `https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-g` |
| J / Z | `https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-jz` |
| L | `https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-l` |
| N / Q / R / W | `https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-nqrw` |
| Staten Island Railway | `https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-si` |

---

## 8. Finding your subway stop ID

Stop IDs follow the pattern `<number><direction>` where direction is
`N` (northbound / Uptown) or `S` (southbound / Downtown).

### Method 1 — MTA static GTFS

1. Download the MTA static GTFS package:
   <https://rrgtfsfeeds.s3.amazonaws.com/gtfslatest.zip>

2. Unzip and open `stops.txt`. Search for your station name:

   ```bash
   grep -i "canal" stops.txt
   ```

   Example output:
   ```
   120N,Canal St,40.7219,-74.0051,...
   120S,Canal St,40.7219,-74.0051,...
   ```

3. Use `120N` for Uptown trains or `120S` for Downtown trains.

### Method 2 — Online lookup

Visit <https://api.mta.info/doc/GTFS-Realtime-Feed-Codes.pdf> for a
printable reference of all stop IDs.

Set your stop ID in `config.py`:

```python
SUBWAY_STOP_ID = "120S"   # Canal St, Downtown (1/2/3)
```

---

## 3. Citi Bike station IDs

Station IDs come from the public GBFS feed — no login required.

```bash
curl -s https://gbfs.citibikenyc.com/gbfs/en/station_information.json \
  | python3 -m json.tool \
  | grep -A3 '"name"'
```

Look for your two nearest stations and note their `station_id` values.
Update `config.py`:

```python
CITIBIKE_STATION_IDS = ["3279", "3182"]
```

---

## 4. Google Calendar OAuth setup

The dashboard reads your Google Calendar using OAuth 2.0. You need to
complete this setup **once** on any machine with a browser (e.g. your laptop),
then transfer `token.json` to the Pi.

### Step-by-step

1. **Create a Google Cloud project**
   - Open <https://console.cloud.google.com/> and create a new project
     (e.g. "Fridge Dashboard").

2. **Enable the Google Calendar API**
   - In the project, go to **APIs & Services → Library**.
   - Search for "Google Calendar API" and click **Enable**.

3. **Create OAuth credentials**
   - Go to **APIs & Services → Credentials → Create Credentials →
     OAuth client ID**.
   - Application type: **Desktop app**.
   - Download the JSON file and save it as `credentials.json` in the
     project root.

4. **Run the auth flow once**

   ```bash
   cd dashboard
   python3 -c "from fetchers.calendar import fetch_calendar; fetch_calendar()"
   ```

   A browser window opens. Sign in with your Google account and grant
   Calendar read access. A `token.json` file is written to the project root.

5. **Transfer files to the Pi** (if you ran the auth flow on a laptop)

   ```bash
   scp credentials.json token.json pi@raspberrypi.local:~/dashboard/
   ```

6. The `token.json` is refreshed automatically when it expires.
   You should never need to repeat the OAuth flow unless you revoke access.

> **Security note:** `credentials.json` and `token.json` contain sensitive
> secrets. Do not commit them to version control. Both files are listed in
> `.gitignore` by default.

---

## 5. Installation

### Run the setup script (Raspberry Pi only)

```bash
git clone https://github.com/yourname/dashboard.git
cd dashboard
sudo ./scripts/setup.sh
```

The script:
- Installs system and Python dependencies into a `.venv` virtual environment
- Clones the Waveshare e-Paper library
- Downloads DejaVu fonts into `assets/fonts/`
- Creates `/etc/systemd/system/dashboard.service`
- Enables and starts the service automatically on every boot

### Manual installation (any platform)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## 6. Testing with mock_display.py

Run the full pipeline on any machine (no Pi or e-ink panel required):

```bash
cd dashboard
source .venv/bin/activate           # or activate your environment
python tests/mock_display.py
```

This will:
1. Fetch live data from all four APIs
2. Render the full layout to `mock_output.png`
3. Print a summary of fetched data to stdout

Open `mock_output.png` in any image viewer to inspect the layout.

You can also set `MOCK_MODE=1` when running `main.py` directly:

```bash
MOCK_MODE=1 python main.py
```

---

## 7. Configuration reference

All configuration lives in `config.py`. Key settings:

| Variable | Default | Description |
|----------|---------|-------------|
| `LATITUDE` / `LONGITUDE` | 40.7128 / -74.0060 | Your GPS coordinates (NYC default) |
| `TIMEZONE` | `America/New_York` | Local timezone string |
| `MTA_API_KEY` | — | MTA GTFS-RT API key |
| `SUBWAY_STOP_ID` | `120S` | GTFS stop ID (see §8) |
| `SUBWAY_LINE_FEED_URL` | 1/2/3 feed | GTFS-RT feed URL for your line |
| `NUM_ARRIVALS_TO_SHOW` | `3` | How many upcoming trains to display |
| `CITIBIKE_STATION_IDS` | `["3279", "3182"]` | GBFS station IDs (see §3) |
| `GOOGLE_CALENDAR_ID` | `primary` | Calendar ID (or a specific calendar ID) |
| `GOOGLE_CREDENTIALS_PATH` | `credentials.json` | OAuth credentials file path |
| `NUM_CALENDAR_EVENTS` | `5` | Max events to display |
| `MOCK_MODE` | `False` | Set `True` (or `MOCK_MODE=1`) to render to PNG |
| `TRANSIT_REFRESH_INTERVAL` | `60` | Subway + Citi Bike refresh rate (seconds) |
| `FULL_REFRESH_INTERVAL` | `900` | Full screen redraw rate (seconds, default 15 min) |
| `LOG_LEVEL` | `INFO` | Python log level (`DEBUG`, `INFO`, `WARNING`, …) |

### Viewing logs

```bash
sudo journalctl -u dashboard -f          # follow live
sudo journalctl -u dashboard -n 100      # last 100 lines
```
