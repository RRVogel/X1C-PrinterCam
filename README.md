# PrinterCam (CSI) for Raspberry Pi Zero 2 W

MJPEG stream from a **Raspberry Pi Camera Module 3** (CSI ribbon) on a **Pi Zero 2 W**, intended for a Bambu Lab X1C / D3P toolhead-style mount. The stream is a simple HTTP MJPEG endpoint suitable for a browser or Home Assistant-style viewer.

Print files, mechanical assembly notes, and the 3MF are **not** in this repository; they stay with the MakerWorld / electronics write-up.

## Status: running vs fresh install

| Claim | Status |
| --- | --- |
| This tree matches the **CSI software that was running** on a live Pi Zero 2 W hostname `PrinterCam` when collected (2026-11-08, America/New_York) | **Observed** |
| Packages and versions listed below were read from that device (`dpkg`) | **Observed** |
| Stream settings in `printercam.py` (1280×720, 12 fps, port 7123, vertical flip) | **Observed** |
| systemd units and stream watchdog as collected | **Observed** |
| Exact `apt install` / first-boot sequence on a **brand-new** image | **Not verified** — reconstructed from the package list; follow as guidance and adjust if package names differ on your image |
| Camera Module 3 identity via `libcamera-hello --list-cameras` during collection | **Not captured** this pass; module type comes from the builder’s hardware notes plus a live Picamera2 CSI service |

No alternate stack (ustreamer, rpicam-vid as the service, Docker, etc.) is claimed here. `ustreamer` was installed on the collection host but the **CSI service does not use it**; it runs `printercam.py` via Picamera2.

## Hardware (software side)

- Raspberry Pi Zero 2 W  
- Raspberry Pi Camera Module 3  
- Official (or equivalent) Pi power supply  
- Longer Adafruit CSI camera ribbon (stock Zero ribbon is usually too short for toolhead routing)  
- Fasteners used on the published mount: one M3×20 mm thumbscrew + nut, four M3×16 mm screws  

Mechanical design, alternate glass-less cover, watch lens, and adhesive notes belong with the assembly / MakerWorld listing, not this code tree.

## What you get

```
printercam/printercam.py          # CSI MJPEG HTTP server (Picamera2)
systemd/PrinterCam.service        # starts the stream at boot
bin/printercam-watchdog.sh        # restarts service if localhost stream looks dead
systemd/printercam-watchdog.service
systemd/printercam-watchdog.timer # every minute after boot grace
README.md
```

Default stream (as in the collected script):

- URL path: `http://<pi-address>:7123/` (simple HTML page) and `http://<pi-address>:7123/stream.mjpg`
- Resolution: 1280×720  
- Frame rate: 12  
- Vertical flip enabled (`Transform(vflip=1)`); change in `printercam.py` if your mount orientation differs  

## Paths and username (edit before enable)

The live device used a personal login and `$HOME/printercam`. This publish tree uses the common Raspberry Pi OS default **`pi`** as a **placeholder only**.

Before `systemctl enable`, edit `systemd/PrinterCam.service` so these match **your** login:

- `User=`
- `WorkingDirectory=`
- `ExecStart=` path to `printercam.py`

Install layout expected by that unit:

| Role | Example with user `pi` |
| --- | --- |
| App directory | `/home/pi/printercam/printercam.py` |
| Watchdog script | `/usr/local/bin/printercam-watchdog.sh` |
| Units | `/etc/systemd/system/PrinterCam.service`, `printercam-watchdog.service`, `printercam-watchdog.timer` |

Your user must be in the **`video`** group (and normally `render` / `input` on current Raspberry Pi OS). The collected host’s camera user was in `video`.

## Dependencies (observed package versions)

Reconstructed from the collection host — **not** a guaranteed one-shot install script:

- OS: Debian 12 (bookworm) / Raspberry Pi OS 64-bit style image  
- `python3-picamera2` **0.3.31-1**  
- `python3-libcamera` / `libcamera` **0.5.2+rpt…**  
- `rpicam-apps` **1.9.0** (present on host; not invoked by `printercam.py`)  
- `ffmpeg` **5.1.9** (present on host; not used by the CSI path)  
- Watchdog needs: `curl`, `timeout` (coreutils), `systemd`, `logger`

Typical packages to have installed on a camera-capable bookworm image (verify names on your image):

```bash
sudo apt update
sudo apt install -y python3-picamera2 python3-libcamera curl
```

Enable the CSI camera / interface the way your Raspberry Pi OS release requires (`raspi-config` or the current equivalent), then reboot if prompted.

## Install outline (unverified on a wiped card)

1. Copy `printercam/printercam.py` to `~/printercam/printercam.py` and `chmod +x` if you like.  
2. Edit `systemd/PrinterCam.service` for your username and paths (see above).  
3. Install the unit:  
   `sudo cp systemd/PrinterCam.service /etc/systemd/system/`  
4. Install the watchdog:  
   `sudo cp bin/printercam-watchdog.sh /usr/local/bin/`  
   `sudo chmod 755 /usr/local/bin/printercam-watchdog.sh`  
   `sudo cp systemd/printercam-watchdog.service systemd/printercam-watchdog.timer /etc/systemd/system/`  
5. `sudo systemctl daemon-reload`  
6. `sudo systemctl enable --now PrinterCam.service`  
7. `sudo systemctl enable --now printercam-watchdog.timer`  
8. On the Pi: `curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:7123/` — expect `200` when the camera is up.

`ExecStartPre=/bin/sleep 12` in the service gives the camera stack time after boot before Picamera2 starts.

## Watchdog behavior (as collected)

`printercam-watchdog.timer` runs the oneshot service about every **1 minute** (`OnUnitActiveSec=1min`), first firing **2 minutes** after boot (`OnBootSec=2min`).

The script:

1. Exits quietly if uptime &lt; **90** seconds.  
2. Exits if `PrinterCam` is not active.  
3. Exits if the service became active less than **45** seconds ago.  
4. Otherwise pulls up to ~4 seconds of `http://localhost:7123/stream.mjpg` and counts bytes.  
5. If fewer than **20000** bytes arrived, logs via `logger -t printercam-watchdog` and runs `systemctl restart PrinterCam`.

It only talks to **localhost**; it does not open the stream from another machine.

## Security caveat

`printercam.py` binds to all interfaces (`('', PORT)` → port **7123**) and serves MJPEG **with no authentication, TLS, or access control**. Anyone who can reach that port on your LAN (or beyond, if you port-forward) can view the camera. Treat it as a local-network appliance: firewall it, keep it off the public internet, or put a reverse proxy with auth in front if you need remote access. This caveat comes from the source as collected; it is not a hardening guide.

## Configuration knobs

At the top of `printercam.py`:

- `RESOLUTION` — default `(1280, 720)`  
- `FRAMERATE` — default `12`  
- `PORT` — default `7123`  
- `Transform(vflip=1)` — orientation; use `hflip` / both as needed for your mount  

After edits: `sudo systemctl restart PrinterCam`.

## License

No license file is included. Do not assume a license until the author adds one.

## Related

MakerWorld listing, 3MF, and physical assembly documentation are maintained separately from this software tree.
