#include "SerialRTT.h"

#include <stdarg.h>
#include <stdio.h>
#include <string.h>

extern "C" {
#include "SEGGER_RTT/RTT/SEGGER_RTT.h"
}

// ============================================================================
// Write Method Selection
// ============================================================================
// Gate between blocking SEGGER_RTT_Write and non-blocking
// SEGGER_RTT_WriteSkipNoLock based on configuration.
//
// Define SERIALRTT_USE_SKIP_NO_LOCK to use non-blocking writes,
// or set SEGGER_RTT_MODE_DEFAULT=SEGGER_RTT_MODE_NO_BLOCK_SKIP
// ============================================================================

#if defined(SERIALRTT_USE_SKIP_NO_LOCK) ||                                                         \
    (defined(SEGGER_RTT_MODE_DEFAULT) && SEGGER_RTT_MODE_DEFAULT == SEGGER_RTT_MODE_NO_BLOCK_SKIP)
#define SERIALRTT_WRITE(buffer, pData, NumBytes) SEGGER_RTT_WriteSkipNoLock(buffer, pData, NumBytes)
#else
#define SERIALRTT_WRITE(buffer, pData, NumBytes) SEGGER_RTT_Write(buffer, pData, NumBytes)
#endif

void SerialRTT_::begin() {
    SEGGER_RTT_Init();
}

size_t SerialRTT_::write(uint8_t c) {
    return SERIALRTT_WRITE(0, &c, 1);
}
int SerialRTT_::available() {
    return SEGGER_RTT_HasData(0);
}
int SerialRTT_::read() {
    uint8_t c = 0;
    return SEGGER_RTT_Read(0, &c, 1) > 0 ? c : -1;
}
int SerialRTT_::peek() {
    return -1;
}
void SerialRTT_::flush() {}

size_t SerialRTT_::print(const __FlashStringHelper *str) {
    return SERIALRTT_WRITE(0, reinterpret_cast<const char *>(str),
                           strlen(reinterpret_cast<const char *>(str)));
}

size_t SerialRTT_::print(const String &str) {
    return SERIALRTT_WRITE(0, str.c_str(), str.length());
}

size_t SerialRTT_::print(const char str[]) {
    return SERIALRTT_WRITE(0, str, strlen(str));
}

size_t SerialRTT_::print(char c) {
    return SERIALRTT_WRITE(0, &c, 1);
}

size_t SerialRTT_::print(unsigned char num, int base) {
    char buf[8 * sizeof(unsigned char) + 1];
    char *str = &buf[sizeof(buf) - 1];
    *str = '\0';

    if (base < 2)
        base = 10;

    do {
        unsigned char m = num % base;
        *--str = m < 10 ? m + '0' : m + 'A' - 10;
        num /= base;
    } while (num);

    return SERIALRTT_WRITE(0, str, strlen(str));
}

size_t SerialRTT_::print(int num, int base) {
    if (base == 10 && num < 0) {
        const unsigned int magnitude = static_cast<unsigned int>(-(num + 1)) + 1U;
        return print('-') + print(magnitude, base);
    }
    return print(static_cast<unsigned int>(num), base);
}

size_t SerialRTT_::print(unsigned int num, int base) {
    return print((unsigned long)num, base);
}

size_t SerialRTT_::print(long num, int base) {
    if (base == 10 && num < 0) {
        const unsigned long magnitude = static_cast<unsigned long>(-(num + 1L)) + 1UL;
        return print('-') + print(magnitude, base);
    }
    return print(static_cast<unsigned long>(num), base);
}

size_t SerialRTT_::print(unsigned long num, int base) {
    char buf[8 * sizeof(unsigned long) + 1];
    char *str = &buf[sizeof(buf) - 1];
    *str = '\0';

    if (base < 2)
        base = 10;

    do {
        unsigned long m = num % base;
        *--str = m < 10 ? m + '0' : m + 'A' - 10;
        num /= base;
    } while (num);

    return SERIALRTT_WRITE(0, str, strlen(str));
}

size_t SerialRTT_::print(long long num, int base) {
    if (base == 10 && num < 0) {
        const unsigned long long magnitude = static_cast<unsigned long long>(-(num + 1LL)) + 1ULL;
        return print('-') + print(magnitude, base);
    }
    return print(static_cast<unsigned long long>(num), base);
}

size_t SerialRTT_::print(unsigned long long num, int base) {
    char buf[8 * sizeof(unsigned long long) + 1];
    char *str = &buf[sizeof(buf) - 1];
    *str = '\0';

    if (base < 2)
        base = 10;

    do {
        unsigned long long m = num % base;
        *--str = m < 10 ? m + '0' : m + 'A' - 10;
        num /= base;
    } while (num);

    return SERIALRTT_WRITE(0, str, strlen(str));
}

size_t SerialRTT_::print(double num, int digits) {
    char buf[32];
    char format[8];
    snprintf(format, sizeof(format), "%%.%dlf", digits);
    int len = snprintf(buf, sizeof(buf), format, num);
    if (len > 0) {
        return SERIALRTT_WRITE(0, buf, len);
    }
    return 0;
}

size_t SerialRTT_::print(const Printable &p) {
    return p.printTo(*this);
}

size_t SerialRTT_::println(const __FlashStringHelper *str) {
    size_t n = print(str);
    return n + SERIALRTT_WRITE(0, "\n", 1);
}

size_t SerialRTT_::println(const String &str) {
    size_t n = print(str);
    return n + SERIALRTT_WRITE(0, "\n", 1);
}

size_t SerialRTT_::println(const char str[]) {
    size_t n = print(str);
    return n + SERIALRTT_WRITE(0, "\n", 1);
}

size_t SerialRTT_::println(char c) {
    size_t n = print(c);
    return n + SERIALRTT_WRITE(0, "\n", 1);
}

size_t SerialRTT_::println(unsigned char num, int base) {
    size_t n = print(num, base);
    return n + SERIALRTT_WRITE(0, "\n", 1);
}

size_t SerialRTT_::println(int num, int base) {
    size_t n = print(num, base);
    return n + SERIALRTT_WRITE(0, "\n", 1);
}

size_t SerialRTT_::println(unsigned int num, int base) {
    size_t n = print(num, base);
    return n + SERIALRTT_WRITE(0, "\n", 1);
}

size_t SerialRTT_::println(long num, int base) {
    size_t n = print(num, base);
    return n + SERIALRTT_WRITE(0, "\n", 1);
}

size_t SerialRTT_::println(unsigned long num, int base) {
    size_t n = print(num, base);
    return n + SERIALRTT_WRITE(0, "\n", 1);
}

size_t SerialRTT_::println(long long num, int base) {
    size_t n = print(num, base);
    return n + SERIALRTT_WRITE(0, "\n", 1);
}

size_t SerialRTT_::println(unsigned long long num, int base) {
    size_t n = print(num, base);
    return n + SERIALRTT_WRITE(0, "\n", 1);
}

size_t SerialRTT_::println(double num, int digits) {
    size_t n = print(num, digits);
    return n + SERIALRTT_WRITE(0, "\n", 1);
}

size_t SerialRTT_::println(const Printable &p) {
    size_t n = print(p);
    return n + SERIALRTT_WRITE(0, "\n", 1);
}

size_t SerialRTT_::println(void) {
    return SERIALRTT_WRITE(0, "\n", 1);
}

void SerialRTT_::printf(const char *format, ...) {
    char buffer[128]; // Temporary buffer
    va_list args;
    va_start(args, format);
    vsnprintf(buffer, sizeof(buffer), format, args);
    va_end(args);
    SERIALRTT_WRITE(0, buffer, strlen(buffer));
}

size_t SerialRTT_::readBytes(char *buffer, size_t length) {
    return SEGGER_RTT_Read(0, buffer, length);
}

String SerialRTT_::readString() {
    String result;
    char buffer[64]; // Temporary buffer
    size_t bytesRead = readBytes(buffer, sizeof(buffer) - 1);
    if (bytesRead > 0) {
        buffer[bytesRead] = '\0'; // Null-terminate
        result = String(buffer);
    }
    return result;
}

SerialRTT_ SerialRTT;
