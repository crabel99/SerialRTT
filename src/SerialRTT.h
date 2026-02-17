/**
 * @file SerialRTT.h
 * @brief Arduino Stream-compatible SEGGER RTT serial implementation.
 *
 * Typical usage:
 * @code{.cpp}
 * #include <SerialRTT.h>
 *
 * void setup() {
 *   SerialRTT.begin();
 *   SerialRTT.println("SerialRTT online");
 * }
 * @endcode
 */

#pragma once

#include <Arduino.h>

/**
 * @defgroup SerialRTTCore SerialRTT API
 * @brief Stream-style RTT input/output API.
 * @{
 */

#ifdef __cplusplus // Ensure this is only compiled in C++
/**
 * @brief Implementation of `Stream` that interfaces with SEGGER RTT for debugging output.
 * @ingroup SerialRTTCore
 */
class SerialRTT_ : public Stream {
  public:
    /**
     * @brief Default constructor.
     */
    SerialRTT_() = default;

    /**
     * @brief Default destructor.
     */
    ~SerialRTT_() = default;

    /**
     * @brief Initialize RTT communication. This must be called before using any other methods.
     */
    void begin();

    /**
     * @brief Write a single character to RTT.
     * @param c The character to write.
     * @return The number of bytes written.
     */
    size_t write(uint8_t c) override;

    /**
     * @brief Check if data is available for reading.
     * @return The number of bytes available for reading.
     */
    int available() override;

    /**
     * @brief Read a single character from RTT.
     * @return The character read.
     */
    int read() override;

    /**
     * @brief Peek at the next available character.
     * @return The next character without removing it from the buffer.
     */
    int peek() override;

    /**
     * @brief Flush the RTT buffer.
     */
    void flush() override;

    /** @name Print API
     *  @brief Print and println overloads.
     *  @{ */
    /** @brief Print a flash-resident string. */
    size_t print(const __FlashStringHelper *);
    /** @brief Print an Arduino String. */
    size_t print(const String &);
    /** @brief Print a null-terminated C string. */
    size_t print(const char[]);
    /** @brief Print a single character. */
    size_t print(char);
    /** @brief Print an unsigned 8-bit value in the specified base. */
    size_t print(unsigned char, int = DEC);
    /** @brief Print a signed int in the specified base. */
    size_t print(int, int = DEC);
    /** @brief Print an unsigned int in the specified base. */
    size_t print(unsigned int, int = DEC);
    /** @brief Print a signed long in the specified base. */
    size_t print(long, int = DEC);
    /** @brief Print an unsigned long in the specified base. */
    size_t print(unsigned long, int = DEC);
    /** @brief Print a signed 64-bit value in the specified base. */
    size_t print(long long, int = DEC);
    /** @brief Print an unsigned 64-bit value in the specified base. */
    size_t print(unsigned long long, int = DEC);
    /** @brief Print a floating-point value with the given precision. */
    size_t print(double, int = 2);
    /** @brief Print a Printable implementation. */
    size_t print(const Printable &);

    /** @brief Print a flash-resident string, followed by a newline. */
    size_t println(const __FlashStringHelper *);
    /** @brief Print an Arduino String, followed by a newline. */
    size_t println(const String &);
    /** @brief Print a null-terminated C string, followed by a newline. */
    size_t println(const char[]);
    /** @brief Print a single character, followed by a newline. */
    size_t println(char);
    /** @brief Print an unsigned 8-bit value, followed by a newline. */
    size_t println(unsigned char, int = DEC);
    /** @brief Print a signed int, followed by a newline. */
    size_t println(int, int = DEC);
    /** @brief Print an unsigned int, followed by a newline. */
    size_t println(unsigned int, int = DEC);
    /** @brief Print a signed long, followed by a newline. */
    size_t println(long, int = DEC);
    /** @brief Print an unsigned long, followed by a newline. */
    size_t println(unsigned long, int = DEC);
    /** @brief Print a signed 64-bit value, followed by a newline. */
    size_t println(long long, int = DEC);
    /** @brief Print an unsigned 64-bit value, followed by a newline. */
    size_t println(unsigned long long, int = DEC);
    /** @brief Print a floating-point value, followed by a newline. */
    size_t println(double, int = 2);
    /** @brief Print a Printable implementation, followed by a newline. */
    size_t println(const Printable &);
    /** @brief Print only a newline. */
    size_t println(void);
    /** @} */

    /** @name Read API
     *  @brief Input helpers and buffered reads.
     *  @{ */
    /**
     * @brief Read multiple bytes into a buffer.
     * @param buffer The buffer to read into.
     * @param length The number of bytes to read.
     * @return The number of bytes read.
     */
    size_t readBytes(char *buffer, size_t length);

    /**
     * @brief Read a string from RTT.
     * @return The string read.
     */
    String readString();
    /** @} */

    /**
     * @brief Print formatted data to RTT.
     * @param format The format string.
     * @param ... The values to format.
     */
    void printf(const char *format, ...);
};

/**
 * @brief Global instance of SerialRTT for use like Serial.
 */
extern SerialRTT_ SerialRTT;

#endif /*__cplusplus*/

/** @} */