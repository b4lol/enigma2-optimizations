#!/bin/bash

# Enigma2 IPTV, CI+ & STB Performance Optimization Script
# Author: b4lol
# Description: Automates Enigma2 IPTV, player, network, hardware tuning, and CI+ Helper monitor daemon.

# Exit immediately if a command exits with a non-zero status
set -e

# Configuration Files Paths (Relative to script directory)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SYSCTL_SRC="${SCRIPT_DIR}/configs/sysctl.conf"
RESOLV_SRC="${SCRIPT_DIR}/configs/resolv.conf"
SETTINGS_SRC="${SCRIPT_DIR}/configs/settings.append"
MONITOR_SRC="${SCRIPT_DIR}/configs/enigma2_monitor.sh"
RCLOCAL_SRC="${SCRIPT_DIR}/configs/rc.local"

echo "=========================================================="
echo "      Enigma2 Performance & CI+ Optimization Suite        "
echo "=========================================================="

# 1. Prompt User for Receiver IP & Credentials (No hardcoded defaults for security/portability)
read -p "Enter Enigma2 Receiver IP Address: " REC_IP
if [ -z "$REC_IP" ]; then
    echo "[!] Error: Receiver IP is required."
    exit 1
fi

read -p "Enter SSH Username (e.g. root): " REC_USER
if [ -z "$REC_USER" ]; then
    echo "[!] Error: SSH Username is required."
    exit 1
fi

read -s -p "Enter SSH Password: " REC_PASS
echo ""
if [ -z "$REC_PASS" ]; then
    echo "[!] Error: SSH Password is required."
    exit 1
fi

# Check for sshpass dependency
if ! command -v sshpass &> /dev/null; then
    echo "[!] Error: sshpass is not installed locally. Please install it (e.g. 'sudo apt-get install sshpass') or use SSH Key authentication."
    exit 1
fi

SSH_CMD="sshpass -p ${REC_PASS} ssh -o StrictHostKeyChecking=no ${REC_USER}@${REC_IP}"
SCP_CMD="sshpass -p ${REC_PASS} scp -o StrictHostKeyChecking=no"

echo "[+] Testing SSH connection to ${REC_IP}..."
if ! ${SSH_CMD} "echo 'Connection successful!'" &> /dev/null; then
    echo "[!] Error: Failed to connect to ${REC_IP} using provided credentials."
    exit 1
fi

# 2. Update and Install Required Player Packages
echo "[+] Updating opkg package lists and installing media packages on receiver..."
${SSH_CMD} "opkg update && opkg install enigma2-plugin-systemplugins-serviceapp exteplayer3 ffmpeg gstplayer"

# 3. Apply sysctl Network and RAM Tuning Config
if [ -f "${SYSCTL_SRC}" ]; then
    echo "[+] Copying optimized sysctl.conf to receiver..."
    ${SCP_CMD} "${SYSCTL_SRC}" "${REC_USER}@${REC_IP}:/etc/sysctl.conf"
    echo "[+] Loading sysctl network and virtual memory parameters..."
    ${SSH_CMD} "sysctl -p /etc/sysctl.conf"
else
    echo "[!] Warning: configs/sysctl.conf not found. Skipping network tuning."
fi

# 4. Apply resolv.conf DNS Config
if [ -f "${RESOLV_SRC}" ]; then
    echo "[+] Copying optimized resolv.conf DNS file to receiver..."
    ${SCP_CMD} "${RESOLV_SRC}" "${REC_USER}@${REC_IP}:/etc/resolv.conf"
else
    echo "[!] Warning: configs/resolv.conf not found. Skipping DNS optimization."
fi

# 5. Apply ServiceApp & Software Audio Decoding settings to /etc/enigma2/settings
if [ -f "${SETTINGS_SRC}" ]; then
    echo "[+] Updating player settings in /etc/enigma2/settings..."
    
    # Stop Enigma2 GUI temporarily so it does not overwrite settings during reload
    echo "[+] Stopping Enigma2 GUI (init 4)..."
    ${SSH_CMD} "init 4"
    sleep 3

    # Generate a temporary script on the receiver to merge settings and prevent duplicates
    echo "[+] Merging settings cleanly on receiver..."
    ${SSH_CMD} "cat << 'EOF' > /tmp/update_settings.py
import sys

settings_path = '/etc/enigma2/settings'
append_path = '/tmp/settings.append'

# Read existing receiver settings
try:
    with open(settings_path, 'r') as f:
        existing_lines = f.readlines()
except FileNotFoundError:
    existing_lines = []

existing_keys = {}
for line in existing_lines:
    if '=' in line:
        k, v = line.split('=', 1)
        existing_keys[k.strip()] = line

# Read append settings
try:
    with open(append_path, 'r') as f:
        append_lines = f.readlines()
except FileNotFoundError:
    print('Append settings file not found!')
    sys.exit(1)

# Prevent duplicates and merge changes
updated_settings = list(existing_lines)
for line in append_lines:
    if '=' in line:
        k, v = line.split('=', 1)
        k = k.strip()
        if k in existing_keys:
            idx = updated_settings.index(existing_keys[k])
            updated_settings[idx] = line
        else:
            updated_settings.append(line)

# Write merged settings back
with open(settings_path, 'w') as f:
    f.writelines(updated_settings)

print('Settings merged cleanly.')
EOF
"
    # Copy append configurations to receiver
    ${SCP_CMD} "${SETTINGS_SRC}" "${REC_USER}@${REC_IP}:/tmp/settings.append"
    
    # Run settings merger script on receiver and clean up temporary files
    ${SSH_CMD} "python /tmp/update_settings.py && rm -f /tmp/settings.append /tmp/update_settings.py"

    echo "[+] Starting Enigma2 GUI (init 3)..."
    ${SSH_CMD} "init 3"
else
    echo "[!] Warning: configs/settings.append not found. Skipping player optimizations."
fi

# 6. Optimize BouquetMakerXtream Playlists JSON (enable exteplayer3 for VOD)
echo "[+] Checking BouquetMakerXtream playlist configuration..."
${SSH_CMD} "
if [ -f /etc/enigma2/bouquetmakerxtream/bmx_playlists.json ]; then
    echo '[+] Updating bmx_playlists.json (VOD type -> 5002)...'
    sed -i 's/\"vod_type\": \"4097\"/\"vod_type\": \"5002\"/g' /etc/enigma2/bouquetmakerxtream/bmx_playlists.json
    echo '[+] BMX playlists optimized.'
else
    echo '[!] BMX config not found. Skipping VOD type optimization.'
fi
"

# 7. CI+ Helper (ciplushelper) Setup and Bug Fix Module
echo "----------------------------------------------------------"
read -p "Do you want to install and repair CI+ Helper (ciplushelper)? [y/N]: " INSTALL_CI
INSTALL_CI="${INSTALL_CI:-n}"

if [[ "$INSTALL_CI" =~ ^[Yy]$ ]]; then
    echo "[+] Installing and repairing CI+ Helper..."
    ${SSH_CMD} "
        # 1. Clean previous temp files
        rm -rf /tmp/ciplus_pkg /tmp/enigma2-plugin-systemplugins-ciplushelper*

        # 2. Download package from feeds using opkg
        echo '[+] Downloading ipk file from package server...'
        cd /tmp
        if ! opkg download enigma2-plugin-systemplugins-ciplushelper; then
            echo '[!] Package download failed. Attempting to install it first to resolve feeds...'
            opkg install enigma2-plugin-systemplugins-ciplushelper || true
            opkg download enigma2-plugin-systemplugins-ciplushelper
        fi

        IPK_FILE=\$(ls enigma2-plugin-systemplugins-ciplushelper_*.ipk 2>/dev/null | head -n 1)
        if [ -z \"\$IPK_FILE\" ]; then
            echo '[!] Error: ciplushelper ipk file not found on receiver.'
            exit 1
        fi

        # 3. Unpack ipk archive manually
        echo '[+] Unpacking ipk archive...'
        mkdir -p /tmp/ciplus_pkg
        cd /tmp/ciplus_pkg
        if ! ar x /tmp/\$IPK_FILE 2>/dev/null; then
            tar -xf /tmp/\$IPK_FILE
        fi
        tar -zxf data.tar.gz

        # 4. Detect receiver CPU architecture
        ARCH=\$(uname -m)
        echo \"[+] Detected receiver architecture: \$ARCH\"

        # 5. Copy correct binary based on CPU architecture to fix installer bugs
        if [[ \"\$ARCH\" =~ 'arm' ]]; then
            echo '[+] Copying ARM binary for Broadcom (hd51/gbquad4kpro/etc)...'
            cp var/local/hd51/6.new/usr/bin/ciplushelper /usr/bin/ciplushelper
        elif [[ \"\$ARCH\" =~ 'mips' ]]; then
            echo '[+] Copying MIPS binary (mipsel32)...'
            cp var/local/mipsel32/6.new/usr/bin/ciplushelper /usr/bin/ciplushelper
        else
            echo '[!] Unsupported architecture. Copying default ARM binary...'
            cp var/local/hd51/6.new/usr/bin/ciplushelper /usr/bin/ciplushelper
        fi

        # 6. Copy startup service script
        echo '[+] Copying startup script (/etc/init.d/ciplushelper)...'
        cp var/local/etc/init.d/ciplushelper /etc/init.d/ciplushelper

        # 6b. Copy certificates and param files (Crucial for CI+ decryption handshakes)
        echo '[+] Copying CI+ certificates and authentication parameters...'
        mkdir -p /etc/ciplus
        cp etc/ciplus/* /etc/ciplus/ 2>/dev/null || true
        mkdir -p /etc/ssl/certs
        cp etc/ssl/certs/* /etc/ssl/certs/ 2>/dev/null || true

        # 7. Set executable permissions
        chmod 755 /usr/bin/ciplushelper
        chmod 755 /etc/init.d/ciplushelper

        # 8. Clean up temp files
        rm -rf /tmp/ciplus_pkg /tmp/\$IPK_FILE

        # 9. Enable autostart and start service
        echo '[+] Registering service for autostart and launching daemon...'
        /etc/init.d/ciplushelper stop 2>/dev/null || true
        /etc/init.d/ciplushelper enable_autostart
        /etc/init.d/ciplushelper start

        # 10. Ensure helper is enabled in settings
        if grep -q 'config.cimisc.cihelperenabled=False' /etc/enigma2/settings; then
            echo '[+] Enabling cihelperenabled=True in Enigma2 settings...'
            sed -i 's/config.cimisc.cihelperenabled=False/config.cimisc.cihelperenabled=True/g' /etc/enigma2/settings
        fi

        echo '[+] CI+ Helper repair and installation completed.'
    "
fi

# 8. Deploy STB Hardware Optimizations & Enigma2 Monitor Daemon
echo "----------------------------------------------------------"
read -p "Do you want to deploy Enigma2 PID Monitor Daemon & STB hardware tweaks (rc.local)? [y/N]: " DEPLOY_MONITOR
DEPLOY_MONITOR="${DEPLOY_MONITOR:-n}"

if [[ "$DEPLOY_MONITOR" =~ ^[Yy]$ ]]; then
    # Deploy Monitor Daemon script
    if [ -f "${MONITOR_SRC}" ]; then
        echo "[+] Copying Enigma2 PID Monitor Daemon script to receiver (/usr/bin/enigma2_monitor.sh)..."
        ${SCP_CMD} "${MONITOR_SRC}" "${REC_USER}@${REC_IP}:/usr/bin/enigma2_monitor.sh"
        ${SSH_CMD} "chmod 755 /usr/bin/enigma2_monitor.sh"
    else
        echo "[!] Warning: configs/enigma2_monitor.sh not found. Skipping monitor daemon deployment."
    fi

    # Deploy rc.local configuration script
    if [ -f "${RCLOCAL_SRC}" ]; then
        echo "[+] Copying hardware optimizations and autostart rc.local to receiver..."
        # Backup existing rc.local on receiver
        ${SSH_CMD} "cp /etc/rc.local /etc/rc.local.bak 2>/dev/null || true"
        ${SCP_CMD} "${RCLOCAL_SRC}" "${REC_USER}@${REC_IP}:/etc/rc.local"
        ${SSH_CMD} "chmod 755 /etc/rc.local"
        
        # Execute it immediately to apply tweaks and run monitor daemon in the background
        echo "[+] Executing rc.local on receiver to load optimizations and daemon..."
        ${SSH_CMD} "killall enigma2_monitor.sh 2>/dev/null || true; nohup /etc/rc.local >/dev/null 2>/dev/null &"
        echo "[+] Hardware optimizations and PID Monitor Daemon activated in background."
    else
        echo "[!] Warning: configs/rc.local not found. Skipping rc.local deployment."
    fi
fi

echo "=========================================================="
echo "[+] All optimizations and repairs completed successfully!  "
echo "=========================================================="
