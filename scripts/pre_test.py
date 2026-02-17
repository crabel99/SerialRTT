#!/usr/bin/env python3
"""
Pre-test script: Start J-Link RTT socket before tests run.

Configuration (highest priority first):
- Environment variable: JLINK_DEVICE
- platformio.ini project options: test_port, upload_protocol

If no device is provided, a best-effort fallback attempts to map build.mcu to a
SEGGER device name (for example samd21g18a -> ATSAMD21G18A). For devices that do
not map cleanly, set JLINK_DEVICE explicitly.
"""

import os
import shutil
import socket
import subprocess
import sys
import time
from typing import Optional, Tuple

try:
    # SCons will provide `env` here when run by PlatformIO
    Import("env")  # type: ignore
except Exception:
    raise RuntimeError(
        "This script must be run by PlatformIO as extra_scripts = pre:..."
    )


def _get_project_option(key: str, default: Optional[str] = None) -> Optional[str]:
    try:
        return env.GetProjectOption(key, default)  # type: ignore[name-defined]
    except Exception:
        return default


def _auto_device_from_mcu() -> Optional[str]:
    try:
        board = env.BoardConfig()  # type: ignore[name-defined]
        mcu = board.get("build.mcu")
        jlink_from_board = None
        debug_cfg = board.get("debug")
        if isinstance(debug_cfg, dict):
            jlink_from_board = debug_cfg.get("jlink_device")
    except Exception:
        mcu = None
        jlink_from_board = None

    if jlink_from_board:
        return str(jlink_from_board)

    if not mcu:
        return None

    mcu_lower = str(mcu).lower()
    if mcu_lower.startswith("sam"):
        return f"AT{str(mcu).upper()}"

    if mcu_lower.startswith("stm32"):
        return f"STM32{str(mcu).upper()[5:]}"

    if mcu_lower.startswith("nrf52"):
        return f"nRF{str(mcu).upper()[3:]}_xxAA"

    return None


def _parse_test_port(value: Optional[str]) -> Tuple[str, int]:
    if not value:
        return ("localhost", 19021)

    raw = value.strip()
    if raw.startswith("socket://"):
        raw = raw[len("socket://") :]

    if ":" in raw:
        host, port_text = raw.split(":", 1)
        try:
            return (host or "localhost", int(port_text))
        except ValueError:
            pass

    # Fallback for non-socket test_port values (serial ports, patterns, etc.)
    return ("localhost", 19021)


jlink_device = os.getenv("JLINK_DEVICE")
if not jlink_device:
    jlink_device = _auto_device_from_mcu()
    if jlink_device:
        print(
            f"Using auto-detected J-Link device from build.mcu: {jlink_device}",
            flush=True,
        )

if not jlink_device:
    print("ERROR: J-Link device not specified.", flush=True)
    print("Set JLINK_DEVICE to a SEGGER-supported device name.", flush=True)
    sys.exit(1)

upload_protocol = (_get_project_option("upload_protocol") or "").lower()
if upload_protocol.endswith("-jtag"):
    jlink_if = "JTAG"
else:
    jlink_if = "SWD"

jlink_speed = "adaptive"

test_port = _get_project_option("test_port")
rtt_host, rtt_port = _parse_test_port(test_port)

# Check if JLinkGDBServerCLExe is available
jlink_exe = shutil.which("JLinkGDBServerCLExe")
if not jlink_exe:
    print("ERROR: JLinkGDBServerCLExe not found in PATH", flush=True)
    print("Install J-Link tools or add them to PATH", flush=True)
    print("Download: https://www.segger.com/downloads/jlink/", flush=True)
    sys.exit(1)

print("Found J-Link at:", jlink_exe, flush=True)

print("Cleaning up existing J-Link processes...", flush=True)
# Try graceful shutdown first (allows cleanup)
os.system("pkill -15 JLinkGDBServerCLExe 2>/dev/null || true")
time.sleep(1.5)
# Then force kill any stragglers
os.system("pkill -9 JLinkGDBServerCLExe 2>/dev/null || true")
time.sleep(0.5)

# Verify port is truly free by waiting for TIME_WAIT to clear
print(f"Waiting for port {rtt_port} to be fully released...", flush=True)
max_port_waits = 20  # 20 x 0.2s = 4 seconds total
for attempt in range(max_port_waits):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.settimeout(0.5)
        result = sock.connect_ex((rtt_host, int(rtt_port)))
        sock.close()
        if result != 0:
            print(f"Port {rtt_port} is fully released", flush=True)
            break
    except Exception:
        break
    if attempt % 5 == 0 and attempt > 0:
        print(f"   (still waiting... {attempt * 0.2:.1f}s)", flush=True)
    time.sleep(0.2)
else:
    print("WARNING: Port still in use, forcing cleanup...", flush=True)
    os.system(f"lsof -ti:{rtt_port} 2>/dev/null | xargs kill -9 2>/dev/null || true")
    time.sleep(1)

print(f"Starting J-Link RTT socket on {rtt_host}:{rtt_port}...", flush=True)
jlink_cmd = [
    "JLinkGDBServerCLExe",
    "-select",
    "USB",
    "-device",
    jlink_device,
    "-if",
    jlink_if,
    "-speed",
    str(jlink_speed),
    "-RTTTelnetPort",
    str(rtt_port),
]

try:
    process = subprocess.Popen(
        jlink_cmd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    print(f"J-Link PID: {process.pid}", flush=True)
except Exception as e:
    print(f"ERROR: Failed to start J-Link: {e}", flush=True)
    sys.exit(1)

print("Waiting for RTT socket to be ready...", flush=True)
max_retries = 50  # 50 x 0.2s = 10 seconds
retry_count = 0

while retry_count < max_retries:
    retry_count += 1
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex((rtt_host, int(rtt_port)))
        sock.close()
        if result == 0:
            print(
                "RTT socket ready (connected after {:.1f}s)".format(retry_count * 0.2),
                flush=True,
            )
            time.sleep(0.5)
            break
    except Exception:
        pass
    time.sleep(0.2)
else:
    print("ERROR: RTT socket not responding after 10 seconds", flush=True)
    print("Possible causes:", flush=True)
    print("1. J-Link hardware not connected or not powered", flush=True)
    print("2. J-Link probe not detected via USB", flush=True)
    print(f"3. Wrong device specified ({jlink_device})", flush=True)
    print(" ", flush=True)
    print("Debug: Try running J-Link manually to see detailed output:", flush=True)
    print(
        f"$ JLinkGDBServerCLExe -select USB -device {jlink_device} -if {jlink_if} -speed {jlink_speed}",
        flush=True,
    )
    print(" ", flush=True)
    print(f"Killing J-Link process {process.pid}...", flush=True)
    os.system(f"kill -9 {process.pid} 2>/dev/null || true")
    sys.exit(1)
