#!/bin/sh
# Enigma2 and ciplushelper Monitor Daemon
# Created by b4lol

LAST_PID=""
while true; do
    PID=$(pidof enigma2)
    if [ -n "$PID" ]; then
        PID=$(echo "$PID" | awk '{print $NF}')
        if [ "$PID" != "$LAST_PID" ]; then
            LAST_PID="$PID"
            
            # Kill helper to free slots for Enigma2 scan
            killall ciplushelper >/dev/null 2>&1 || true
            
            # Wait for Enigma2 to initialize slots
            sleep 20
            
            # Start helper
            if [ -x /usr/bin/ciplushelper ]; then
                /usr/bin/ciplushelper >/dev/null 2>&1 &
            fi
            
            # Optimize priority of the new Enigma2 process
            renice -n -10 -p "$PID" >/dev/null 2>&1
            ionice -c 2 -n 0 -p "$PID" >/dev/null 2>&1
            if [ -f "/proc/$PID/oom_score_adj" ]; then
                echo "-999" > "/proc/$PID/oom_score_adj" 2>/dev/null
            fi
        fi
    else
        LAST_PID=""
        killall ciplushelper >/dev/null 2>&1 || true
    fi
    sleep 5
done
