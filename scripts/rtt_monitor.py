#!/usr/bin/env python3
"""
RTT console helper.

Starts JLinkGDBServer (if available) with RTT Telnet enabled, connects to RTT,
and mirrors SerialRTT output to the terminal. Optional USB CDC frame sniffing
is available but off by default (USB is used by the device for data traffic).
"""

import argparse
import configparser
import os
import selectors
import socket
import struct
import time
import subprocess
import shutil
import signal
from datetime import datetime
from typing import Any, Optional, Protocol, runtime_checkable, cast

# Constants
FRAME_MAGIC = 0xAA55  # Device magic bytes (big-endian in header)
DEFAULT_BAUD = 921600
DEFAULT_RTT_HOST = "127.0.0.1"
DEFAULT_RTT_PORT = 19021  # J-Link RTT Telnet port (opened by JLinkGDBServer)
DEFAULT_GDB_PORT = 2331
RETRY_SEC = 1.0
PLATFORMIO_INI = "platformio.ini"


def _auto_device_from_mcu(mcu: str) -> Optional[str]:
    mcu_lower = str(mcu).lower()
    if not mcu_lower:
        return None

    if mcu_lower.startswith("sam"):
        return f"AT{str(mcu).upper()}"

    if mcu_lower.startswith("stm32"):
        return f"STM32{str(mcu).upper()[5:]}"

    if mcu_lower.startswith("nrf52"):
        return f"nRF{str(mcu).upper()[3:]}_xxAA"

    return None


def _parse_socket_endpoint(value: Optional[str]) -> tuple[str, int]:
    if not value:
        return (DEFAULT_RTT_HOST, DEFAULT_RTT_PORT)

    raw = value.strip()
    if raw.startswith("socket://"):
        raw = raw[len("socket://") :]

    if ":" in raw:
        host, port_text = raw.split(":", 1)
        try:
            return (host or DEFAULT_RTT_HOST, int(port_text))
        except ValueError:
            pass

    return (DEFAULT_RTT_HOST, DEFAULT_RTT_PORT)


def crc16_ccitt(data: bytes) -> int:
    """Calculate CRC-16/XMODEM (initial 0x0000) over payload."""
    crc = 0x0000
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc <<= 1
            if crc & 0x10000:
                crc = (crc ^ 0x1021) & 0xFFFF
    return crc


def decode_frame(buffer: bytes):
    """Decode one frame from buffer. Returns (payload, remaining_buffer) or (None, buffer) if incomplete/invalid."""
    if len(buffer) < 6:
        return None, buffer

    magic = struct.unpack(">H", buffer[0:2])[0]
    if magic != FRAME_MAGIC:
        # Resync by searching for next magic.
        for i in range(1, len(buffer) - 1):
            if struct.unpack(">H", buffer[i : i + 2])[0] == FRAME_MAGIC:
                return None, buffer[i:]
        return None, b""

    length = struct.unpack("<H", buffer[2:4])[0]
    crc_received = struct.unpack("<H", buffer[4:6])[0]
    total = 6 + length
    if len(buffer) < total:
        return None, buffer  # need more data

    payload = buffer[6:total]
    crc_computed = crc16_ccitt(payload)
    if crc_computed != crc_received:
        print(
            f"[USB] CRC mismatch: got {crc_received:04x}, expected {crc_computed:04x}; resync"
        )
        return None, buffer[2:]  # drop magic high byte and retry

    remaining = buffer[total:]
    return payload, remaining


def connect_rtt(host: str, port: int):
    """Connect to RTT Telnet endpoint (opened by J-Link RTT client or GDB server)."""
    try:
        sock = socket.create_connection((host, port), timeout=1.0)
        sock.setblocking(False)
        print(f"[RTT] Connected to {host}:{port} (Telnet RTT)")
        return sock
    except OSError as e:
        print(f"[RTT] Unable to connect to {host}:{port}: {e}")
        return None


def main() -> None:
    parser = argparse.ArgumentParser(
        description="RTT console (optional USB sniff). Starts J-Link if needed."
    )
    parser.add_argument(
        "--rtt-host", default=DEFAULT_RTT_HOST, help="RTT host (default: %(default)s)"
    )
    parser.add_argument(
        "--rtt-port",
        type=int,
        default=DEFAULT_RTT_PORT,
        help="RTT Telnet port (default: %(default)s)",
    )
    parser.add_argument(
        "--no-jlink", action="store_true", help="Do not spawn JLinkGDBServer for RTT"
    )
    parser.add_argument(
        "--jlink-device",
        default=None,
        help="MCU name for J-Link (default: auto from platformio.ini if available)",
    )
    parser.add_argument(
        "--jlink-if",
        dest="jlink_if",
        default="swd",
        help="J-Link interface (default: swd)",
    )
    parser.add_argument(
        "--jlink-speed",
        type=int,
        default=4000,
        help="J-Link speed kHz (default: %(default)s)",
    )
    parser.add_argument(
        "--jlink-exec",
        dest="jlink_exec",
        default=None,
        help="Path to JLinkGDBServerCLExe/JLinkGDBServer",
    )
    parser.add_argument(
        "--gdb-port",
        type=int,
        default=DEFAULT_GDB_PORT,
        help="GDB port when spawning J-Link (default: %(default)s)",
    )
    parser.add_argument(
        "--usb-port",
        default=None,
        help="USB CDC device to sniff frames (default: monitor_port/upload_port from platformio.ini)",
    )
    parser.add_argument(
        "--usb-baud",
        type=int,
        default=DEFAULT_BAUD,
        help="USB CDC baud hint (default: %(default)s)",
    )
    parser.add_argument(
        "--no-usb", action="store_true", help="Disable USB sniffing (RTT only)"
    )
    parser.add_argument(
        "--log-file",
        default=None,
        help="Optional log file path (with timestamps). Default: logs/rtt_TIMESTAMP.log",
    )
    parser.add_argument(
        "--pio-ini",
        default=PLATFORMIO_INI,
        help="Path to platformio.ini for auto USB settings (default: %(default)s)",
    )
    parser.add_argument(
        "--pio-env",
        default=None,
        help="Env name in platformio.ini (e.g. env:device). First env used if not set.",
    )
    args = parser.parse_args()

    def cleanup_existing_jlink_processes() -> None:
        """Terminate stale J-Link GDB server processes (pre_test.py style)."""
        print("[JLINK] Cleaning up existing J-Link processes...")
        os.system("pkill -15 JLinkGDBServerCLExe 2>/dev/null || true")
        os.system("pkill -15 JLinkGDBServer 2>/dev/null || true")
        time.sleep(1.5)
        os.system("pkill -9 JLinkGDBServerCLExe 2>/dev/null || true")
        os.system("pkill -9 JLinkGDBServer 2>/dev/null || true")
        time.sleep(0.5)

    def wait_for_port_release(host: str, port: int) -> None:
        print(f"[RTT] Waiting for port {host}:{port} to be released...")
        max_waits = 20
        for attempt in range(max_waits):
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.settimeout(0.5)
                result = sock.connect_ex((host, int(port)))
                sock.close()
                if result != 0:
                    print(f"[RTT] Port {port} is available")
                    return
            except Exception:
                return

            if attempt % 5 == 0 and attempt > 0:
                print(f"[RTT]   still waiting... {attempt * 0.2:.1f}s")
            time.sleep(0.2)

        print("[RTT] Port still busy; forcing cleanup")
        os.system(f"lsof -ti:{port} 2>/dev/null | xargs kill -9 2>/dev/null || true")
        time.sleep(1.0)

    def wait_for_rtt_socket_ready(
        host: str, port: int, timeout_s: float = 10.0
    ) -> bool:
        print(f"[RTT] Waiting for RTT socket on {host}:{port}...")
        max_retries = int(timeout_s / 0.2)
        for retry in range(1, max_retries + 1):
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1.0)
                result = sock.connect_ex((host, int(port)))
                sock.close()
                if result == 0:
                    print(f"[RTT] Socket ready after {retry * 0.2:.1f}s")
                    time.sleep(0.5)
                    return True
            except Exception:
                pass
            time.sleep(0.2)

        print(f"[RTT] Socket not ready after {timeout_s:.0f}s")
        return False

    # Setup log file with timestamps
    log_file = None
    if args.log_file:
        log_path = args.log_file
    else:
        # Default: logs/rtt_TIMESTAMP.log
        os.makedirs("logs", exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = f"logs/rtt_{timestamp}.log"

    try:
        log_file = open(log_path, "w")
        print(f"[LOG] Writing output to {log_path}")
    except IOError as e:
        print(f"[LOG] Failed to open {log_path}: {e}")
        log_file = None

    def write_output(text):
        """Write text to stdout and optional log file with timestamps."""
        if not text:
            return
        lines = text.split("\n")
        for line in lines:
            if line or text.endswith("\n"):  # Print empty lines only if part of \n
                timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                output = f"[{timestamp}] {line}"
                print(output, flush=True)
                if log_file:
                    log_file.write(output + "\n")
                    log_file.flush()

    sel = selectors.DefaultSelector()
    usb_buffer = b""
    jlink_proc: Optional[subprocess.Popen[Any]] = None

    def stop_jlink():
        nonlocal jlink_proc
        if jlink_proc and jlink_proc.poll() is None:
            try:
                jlink_proc.send_signal(signal.SIGINT)
                jlink_proc.wait(timeout=2)
            except Exception:
                jlink_proc.kill()
            jlink_proc = None

    def start_jlink() -> None:
        nonlocal jlink_proc
        if jlink_proc:
            return
        if not args.jlink_device:
            print("[JLINK] Skipping start: no J-Link device configured")
            return

        candidate = args.jlink_exec
        if not candidate:
            # Try common names in PATH
            for name in ("JLinkGDBServerCLExe", "JLinkGDBServer"):
                candidate = shutil.which(name)
                if candidate:
                    break
        if not candidate:
            print("[JLINK] Could not find JLinkGDBServer; specify --jlink-exec")
            return

        cleanup_existing_jlink_processes()
        wait_for_port_release(args.rtt_host, args.rtt_port)

        cmd = [
            candidate,
            "-select",
            "USB",
            "-if",
            args.jlink_if.upper(),
            "-device",
            args.jlink_device,
            "-speed",
            str(args.jlink_speed),
            "-port",
            str(args.gdb_port),
            "-RTTTelnetPort",
            str(args.rtt_port),
            "-nohalt",
            "-nogui",
        ]
        print(f"[JLINK] Starting: {' '.join(cmd)}")
        try:
            jlink_proc = subprocess.Popen(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except Exception as e:
            print(f"[JLINK] Failed to start: {e}")
            jlink_proc = None
            return

        print(f"[JLINK] Started with PID {jlink_proc.pid}")
        if not wait_for_rtt_socket_ready(args.rtt_host, args.rtt_port):
            stop_jlink()

    # Optional USB sniff
    ser: Optional[Any] = None
    last_usb_try = 0.0

    usb_connected = False

    # Minimal protocol to satisfy static type checking for serial-like objects
    @runtime_checkable
    class SerialLike(Protocol):
        in_waiting: int

        def read(self, n: int) -> bytes: ...
        def close(self) -> None: ...

    def load_pio_defaults():
        """Load monitor/upload port + baud and J-Link device from platformio.ini."""
        cfg = configparser.ConfigParser()
        try:
            with open(args.pio_ini, "r") as fp:
                cfg.read_file(fp)
        except OSError:
            return

        # pick env section
        section = None
        if args.pio_env and args.pio_env in cfg:
            section = args.pio_env
        else:
            for sec in cfg.sections():
                if sec.startswith("env:"):
                    section = sec
                    break
        if not section:
            return

        # Auto USB settings if not provided
        if not args.no_usb and not args.usb_port:
            port = cfg.get(section, "monitor_port", fallback=None) or cfg.get(
                section, "upload_port", fallback=None
            )
            speed = cfg.get(section, "monitor_speed", fallback=None)
            if port:
                args.usb_port = port
                print(f"[PIO] Using USB port from {args.pio_ini} [{section}]: {port}")
            if speed:
                try:
                    args.usb_baud = int(speed)
                    print(
                        f"[PIO] Using USB baud from {args.pio_ini} [{section}]: {args.usb_baud}"
                    )
                except ValueError:
                    pass

        # Auto RTT host/port from test_port if defaults are still in use
        if (
            args.rtt_host == DEFAULT_RTT_HOST
            and args.rtt_port == DEFAULT_RTT_PORT
            and cfg.has_option(section, "test_port")
        ):
            parsed_host, parsed_port = _parse_socket_endpoint(
                cfg.get(section, "test_port", fallback=None)
            )
            args.rtt_host = parsed_host
            args.rtt_port = parsed_port
            print(
                f"[PIO] Using RTT endpoint from {args.pio_ini} [{section}]: {parsed_host}:{parsed_port}"
            )

        # Auto J-Link transport from upload_protocol if defaults are still in use
        if args.jlink_if.lower() == "swd":
            upload_protocol = cfg.get(section, "upload_protocol", fallback="").lower()
            if upload_protocol.endswith("-jtag"):
                args.jlink_if = "jtag"
                print(
                    f"[PIO] Using J-Link interface from {args.pio_ini} [{section}]: JTAG"
                )

        # Auto J-Link device if not provided
        if not args.jlink_device:
            mcu = cfg.get(section, "board_build.mcu", fallback="").lower()
            auto = _auto_device_from_mcu(mcu)
            if auto:
                args.jlink_device = auto
                print(
                    f"[PIO] Using J-Link device from {args.pio_ini} [{section}]: {auto}"
                )

    load_pio_defaults()

    # Highest-priority override via environment (same approach as pre_test.py)
    env_jlink_device = os.getenv("JLINK_DEVICE")
    if env_jlink_device:
        args.jlink_device = env_jlink_device
        print(f"[ENV] Using J-Link device from JLINK_DEVICE: {env_jlink_device}")

    # Final fallback if not provided or not in platformio.ini
    if not args.jlink_device:
        print(
            "[JLINK] No device configured. Set board_build.mcu in platformio.ini, "
            "--jlink-device, or JLINK_DEVICE."
        )
        args.no_jlink = True

    def ensure_usb():
        nonlocal ser, last_usb_try, usb_connected
        if args.no_usb:
            return
        if not args.usb_port or ser:
            return
        now = time.time()
        if (now - last_usb_try) < RETRY_SEC:
            return
        last_usb_try = now
        try:
            import serial as pyserial  # lazy import to avoid dependency when not needed

            ser = pyserial.Serial(args.usb_port, args.usb_baud, timeout=0)
            ser.reset_input_buffer()
            ser.reset_output_buffer()
            sel.register(ser, selectors.EVENT_READ, data="usb")
            usb_connected = True
            print(f"[USB] Connected to {args.usb_port} @ {args.usb_baud}")
        except Exception:
            if usb_connected:
                print(f"[USB] Disconnected from {args.usb_port}")
            usb_connected = False
            ser = None

    ensure_usb()

    if not args.no_jlink:
        start_jlink()

    rtt_sock: Optional[socket.socket] = None
    last_rtt_try = 0.0

    def ensure_rtt():
        nonlocal rtt_sock, last_rtt_try
        now = time.time()
        if rtt_sock or (now - last_rtt_try) < RETRY_SEC:
            return
        last_rtt_try = now
        rtt_sock = connect_rtt(args.rtt_host, args.rtt_port)
        if rtt_sock:
            sel.register(rtt_sock, selectors.EVENT_READ, data="rtt")

    ensure_rtt()

    print("[*] Listening for RTT (and USB if enabled)... Ctrl+C to exit")
    try:
        while True:
            for key, _ in sel.select(timeout=0.1):
                if key.data == "usb":
                    try:
                        usb_obj = cast(SerialLike, key.fileobj)
                        waiting = getattr(usb_obj, "in_waiting", 0) or 1
                        chunk = usb_obj.read(waiting)
                        if not chunk:
                            continue
                        usb_buffer += chunk
                        while True:
                            payload, usb_buffer = decode_frame(usb_buffer)
                            if payload is None:
                                break
                            print(f"[USB][FRAME] {len(payload)} bytes: {payload.hex()}")
                    except Exception:
                        if usb_connected:
                            print("[USB] Disconnected")
                        usb_connected = False
                        try:
                            sel.unregister(key.fileobj)
                        except Exception:
                            pass
                        try:
                            cast(Any, key.fileobj).close()
                        except Exception:
                            pass
                        ser = None
                elif key.data == "rtt":
                    try:
                        sock_obj = cast(socket.socket, key.fileobj)
                        data = sock_obj.recv(4096)
                        if not data:
                            print("[RTT] connection closed")
                            sel.unregister(key.fileobj)
                            sock_obj.close()
                            rtt_sock = None
                            continue
                        write_output(data.decode(errors="replace"))
                    except BlockingIOError:
                        pass
            # Reconnect RTT/USB if they drop; restart J-Link if it died.
            if not rtt_sock:
                ensure_rtt()
            if not ser:
                ensure_usb()
            if not args.no_jlink and jlink_proc and jlink_proc.poll() is not None:
                print("[JLINK] Process exited; restarting")
                jlink_proc = None
                start_jlink()
                ensure_rtt()
            time.sleep(0.01)
    except KeyboardInterrupt:
        print("\n[*] Exiting...")
    finally:
        try:
            sel.close()
        except Exception:
            pass
        if ser:
            try:
                cast(SerialLike, ser).close()
            except Exception:
                pass
        if rtt_sock:
            try:
                rtt_sock.close()
            except Exception:
                pass
        if log_file:
            try:
                log_file.close()
                print("[LOG] Closed log file")
            except Exception:
                pass
        stop_jlink()


if __name__ == "__main__":
    main()
