# SerialRTT

[![CI](https://github.com/crabel99/SerialRTT/actions/workflows/ci.yml/badge.svg)](https://github.com/crabel99/SerialRTT/actions/workflows/ci.yml)
[![Doxygen](https://github.com/crabel99/SerialRTT/actions/workflows/doxygen.yml/badge.svg)](https://github.com/crabel99/SerialRTT/actions/workflows/doxygen.yml)

API docs: <https://crabel99.github.io/SerialRTT/>

`SerialRTT` is an Arduino `Stream` implementation backed by SEGGER RTT.

It is intended as a fast debug-output alternative to USB CDC serial for Cortex-M/A/R, RISC-V, and ARMv8-AR projects where a J-Link debugger is available.

## Features

- `Stream`/`Print` compatible API (`print`, `println`, `printf`, `read`, `available`)
- No USB stack dependency for debug logging
- Works with SEGGER RTT Viewer and J-Link GDB workflows
- Optional non-blocking write mode via `SEGGER_RTT_MODE_NO_BLOCK_SKIP`

## Installation

Add as a library dependency in PlatformIO or copy into your `lib/` folder.

## Quick Start

```cpp
#include <Arduino.h>
#include <SerialRTT.h>

void setup() {
  SerialRTT.begin();
  SerialRTT.println("SerialRTT online");
}

void loop() {
  static uint32_t counter = 0;
  SerialRTT.print("count=");
  SerialRTT.println(counter++);
  delay(500);
}
```

See [examples/basic_serial_rtt/basic_serial_rtt.ino](examples/basic_serial_rtt/basic_serial_rtt.ino) for a complete example.

## Compatibility

- Framework: Arduino
- Primary target: ARM Cortex-M boards where SEGGER RTT is usable
- Typical workflow: firmware + J-Link + RTT Viewer

## PlatformIO Integration

Example `platformio.ini` snippet using J-Link RTT and the bundled pre-test
helper script:

```ini
[env:test_samd]
platform = atmelsam
framework = arduino
board = adafruit_feather_m0
upload_protocol = jlink
debug_tool = jlink
test_port = socket://localhost:19021
extra_scripts = pre:$PROJECT_LIBDEPS_DIR/$PIOENV/SerialRTT/scripts/pre_test.py
lib_deps =
  https://github.com/crabel99/SerialRTT.git

build_flags =
  -DBUFFER_SIZE_UP=8192
  -DSERIALRTT_USE_SKIP_NO_LOCK
```

Notes:

- `scripts/pre_test.py` starts `JLinkGDBServerCLExe` and opens the RTT socket.
- When used as a lib dependency, reference it via `$PROJECT_LIBDEPS_DIR/$PIOENV/SerialRTT/scripts/pre_test.py`.
- Set `JLINK_DEVICE` to a SEGGER-supported device name if auto-detection is not sufficient.

Standard PlatformIO options used by the pre-test script:

```ini
test_port = socket://localhost:19021
upload_protocol = jlink       ; SWD
; upload_protocol = jlink-jtag ; JTAG
```

## SEGGER RTT Subtree

This repo vendors SEGGER RTT under `src/SEGGER_RTT` via git subtree.

One-time setup:

```bash
git subtree add --prefix src/SEGGER_RTT https://github.com/SEGGERMicro/RTT.git main --squash
```

Updates are handled by the scheduled workflow in `.github/workflows/segger-subtree.yml`.

## Licensing

This repository includes code under multiple licenses:

- Project wrapper/integration code: MIT (see `LICENSE`)
- Bundled SEGGER RTT source files: SEGGER RTT license terms in file headers

See `THIRD_PARTY_NOTICES.md` for details.
