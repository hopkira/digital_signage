# Raspberry Pi Digital Signage

A lightweight Python digital signage application for a Raspberry Pi 4B.

It provides:

- a full-screen PyQt5 / PyQtWebEngine player
- a password-protected Flask admin page
- local image uploads
- manually entered URLs
- a simple JSON playlist
- up/down/delete playlist controls
- one global display duration
- fallback image support
- systemd startup services

The intended display is HDMI, rotated 270 degrees at OS/display level.

## Project structure

```text
signage/
├── admin.py
├── player.py
├── config.json
├── playlist.json
├── requirements.txt
├── media/
│   └── fallback.png
├── templates/
│   ├── base.html
│   ├── index.html
│   └── login.html
├── static/
│   └── carbon-ish.css
└── systemd/
    ├── signage-admin.service
    └── signage-player.service
```

## 1. Prepare the Raspberry Pi

Use Raspberry Pi OS with desktop enabled.

Update the Pi:

```bash
sudo apt update
sudo apt full-upgrade -y
sudo reboot
```

Install required system packages:

```bash
sudo apt install -y \
  git \
  python3-venv \
  python3-pip \
  libxcb-xinerama0 \
  libnss3 \
  libxcomposite1 \
  libxdamage1 \
  libxrandr2 \
  libxtst6 \
  libasound2 \
  python3-flask \
  python3-pyqt5 \
  python3-pyqt5.qtwebengine \
  python3-pil
```


## 2. Rotate the HDMI display

Edit the Pi firmware command line:

```bash
sudo nano /boot/firmware/cmdline.txt
```

Add the following to the same single line:

```text
video=HDMI-A-1:1920x1080@60,rotate=270
```

Reboot:

```bash
sudo reboot
```

After rotation, the signage player should behave as a portrait display.

## 3. Clone the code from GitHub

Replace the URL with your repository:

```bash
cd /home/pi
git clone https://github.com/hopkira/digital_signage
cd digital_signage
```

## 4. Create the Python virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## 5. Configure the app

Edit `config.json` if required:

```json
{
  "global_duration_seconds": 15,
  "fallback_image": "media/fallback.png",
  "playlist_file": "playlist.json",
  "media_dir": "media",
  "admin_host": "0.0.0.0",
  "admin_port": 8080,
  "allowed_image_extensions": [".png", ".jpg", ".jpeg", ".gif", ".webp"],
  "url_load_timeout_seconds": 10,
  "screen": {
    "rotation": 270,
    "image_scaling": "fill"
  }
}
```

The player reloads `playlist.json` at the start of each full playlist cycle.

## 6. Run manually for testing

Start the admin app:

```bash
cd /home/pi/signage
source venv/bin/activate
export SIGNAGE_ADMIN_PASSWORD='choose-a-password'
export SIGNAGE_FLASK_SECRET='choose-a-random-secret'
python admin.py
```

From another machine on the same network, open:

```text
http://<pi-ip-address>:8080
```

Start the player from the Pi desktop session:

```bash
cd /home/pi/signage
source venv/bin/activate
python player.py
```

Press `Alt+F4` to close the player during testing.

## 7. Configure systemd startup

Edit the service files before installing them:

```bash
nano systemd/signage-admin.service
nano systemd/signage-player.service
```

Change these values as needed:

```ini
User=pi
WorkingDirectory=/home/pi/signage
Environment=SIGNAGE_ADMIN_PASSWORD=change-me
Environment=SIGNAGE_FLASK_SECRET=change-me-too
```

Install the services:

```bash
sudo cp systemd/signage-admin.service /etc/systemd/system/
sudo cp systemd/signage-player.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable signage-admin.service
sudo systemctl enable signage-player.service
sudo systemctl start signage-admin.service
sudo systemctl start signage-player.service
```

Check status:

```bash
systemctl status signage-admin.service
systemctl status signage-player.service
```

View logs:

```bash
journalctl -u signage-admin.service -f
journalctl -u signage-player.service -f
```

## 8. Disable screen blanking

In Raspberry Pi OS desktop:

```bash
sudo raspi-config
```

Then choose:

```text
Display Options > Screen Blanking > No
```

You may also want the Pi to boot to desktop with automatic login:

```text
System Options > Boot / Auto Login > Desktop Autologin
```

## 9. Admin UI usage

The admin page allows you to:

- upload local images
- add URLs
- move items up or down
- delete items

Images are stored under `media/`.

Playlist entries are stored in `playlist.json`.

Example:

```json
[
  {
    "type": "image",
    "source": "media/welcome.png"
  },
  {
    "type": "url",
    "source": "https://example.com/status"
  }
]
```

## 10. Operational notes

- Failed URLs are skipped.
- If the playlist is empty, or all image files are missing, the fallback image is displayed.
- The admin UI has a basic local-network restriction, but this is not a replacement for firewall/network security.
- Avoid very heavy web pages on a Raspberry Pi 4B.
- Use portrait-friendly URLs because rotation is handled by the HDMI/display layer.

## 11. Updating from GitHub

```bash
cd /home/pi/signage
git pull
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart signage-admin.service signage-player.service
```
