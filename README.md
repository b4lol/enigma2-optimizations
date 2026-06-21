# Enigma2 IPTV & CI+ Performance Optimization Suite

This repository contains modular scripts and configurations to optimize Enigma2 satellite receivers (e.g. Gigablue, Dreambox, VU+, Zgemma, Formuler) for high-performance IPTV streaming and D-Smart / Digiturk CI+ module decoding.

It resolves common Enigma2 issues like:
*   **Buffering & stuttering** on high-resolution streams (4K/FHD) due to standard TCP/IP limits.
*   **Audio loss** ("picture but no sound") due to missing hardware DTS/AAC/EAC3 downmixing.
*   **Slow channel-zapping speeds** caused by high DNS lookup times or slow player framework timeouts.
*   **VOD lockups** when forwarding or rewinding movies.
*   **CI+ Module detection & freeze bugs** (e.g., UI kilitlenmesi) due to broken `ciplushelper` installer scripts on modern ARM/MIPS 4K receivers.
*   **CI+ Helper disconnects** after restarting the Enigma2 GUI.

---

## 🚀 Quick Start

### 1. Prerequisites
You need `sshpass` installed on your local computer to automate authentication.
*   **Ubuntu/Debian:** `sudo apt-get install sshpass`
*   **macOS:** `brew install hudochenkov/sshpass/sshpass`

### 2. Execution
Clone the configurations to your machine, open a terminal in the folder, and run:
```bash
./optimize.sh
```
The script will interactively ask for:
1.  **Enigma2 IP address** (defaults to `192.168.1.6`)
2.  **SSH Username** (defaults to `root`)
3.  **SSH Password** (defaults to `root`)
4.  **CI+ Helper (ciplushelper) Setup** (select `y` if you use a CI+ cam module)
5.  **Enigma2 PID Monitor Daemon & STB optimizations (rc.local)** (select `y` to apply CPU, I/O, picture optimizations and the monitor daemon)

---

## 📂 Repository Layout

*   `optimize.sh`: Main script that coordinates package updates, configuration transfer, safely updates Enigma2 settings, repairs `ciplushelper` binaries, deploys hardware tunings, and starts the background monitoring processes.
*   `configs/sysctl.conf`: Kernel networking adjustments for high-bandwidth media streams and RAM/swap optimization.
*   `configs/resolv.conf`: Low-latency DNS routing (Cloudflare/Google) with query rotation.
*   `configs/settings.append`: Settings for Enigma2 player replacements, audio software decoding, and GStreamer buffer sizing.
*   `configs/enigma2_monitor.sh`: A daemon that runs on the receiver to sync `ciplushelper` restarts with Enigma2 GUI reloads and tunes CPU/IO scheduling priorities.
*   `configs/rc.local`: Runs at receiver startup to configure CPU governors, eMMC I/O scheduler, PEP picture sharpening, and start the monitoring daemon.

---

## 🛠️ Optimization Details

### 1. Networking (sysctl.conf)
*   **Window Scaling & SACK:** Enabled to maximize network throughput on high-latency links.
*   **TCP Buffers:** Max buffer sizes set to 16MB (`rmem_max`/`wmem_max`) to absorb network drops without buffering.
*   **Memory Management:** Virtual memory swappiness tuned to `10` and cache pressure to `50` to maintain responsive canal zapping.

### 2. Player Framework (ServiceApp & exteplayer3)
*   Routes stream play via **exteplayer3** (FFmpeg based) using Service ID `5002` instead of default GStreamer (`4097`). This leads to faster start times and lower CPU overhead.
*   Enables software decoding for **AAC, EAC3, AC3, DTS, MP3, and WMA** to prevent silent audio on streams.
*   Increases GStreamer fallback buffers to **16MB** and sets a safe **5-second** buffer duration.

### 3. DNS Lookup speed (resolv.conf)
*   Configures Cloudflare (`1.1.1.1`) and Google (`8.8.8.8`) DNS resolvers.
*   Enables `options rotate` to query resolvers concurrently, cutting down hostname lookups to milliseconds.

### 4. CI+ Helper Repair Module (ciplushelper)
*   **The Bug:** The official `enigma2-plugin-systemplugins-ciplushelper` has installation scripts (`postinst`) that fail to recognize newer 4K receivers (like `gbquad4kpro`), leaving the system without `/usr/bin/ciplushelper` and causing UI lockups/crashes when viewing encrypted channels.
*   **The Fix:** The script downloads the official `.ipk`, unpacks it, queries the receiver's CPU architecture (`uname -m`), extracts the matching Broadcom binary (ARM `hd51/6.new` or MIPS `mipsel32/6.new`), sets up the `/etc/init.d/ciplushelper` service script, runs the autostart registration, and launches the helper in the background.

### 5. Enigma2 PID Monitor Daemon & STB Tuning (enigma2_monitor.sh & rc.local)
*   **PID Tracking:** Checks if Enigma2 restarts (GUI reload). When detected, it automatically restarts `ciplushelper` with a 20-second delay. This allows Enigma2 to initialize the hardware slot scan first, preventing slot locks (`EBUSY`) and keeping CI+ module decryption active.
*   **Process Priority:** Elevates Enigma2 process priority (`renice -n -10`, `ionice -c 2 -n 0`, `oom_score_adj=-999`) to prevent stuttering.
*   **Hardware Tweaks:** Sets all CPU scaling governors to `performance`, optimizes the eMMC I/O scheduler to `deadline` and read-ahead to `512 KB`.
*   **Picture Enhancements:** Configures Broadcom pep parameters (dynamic contrast, horizontal/vertical dejagging, sharpness) for optimal picture quality on 4K/FHD channels.
