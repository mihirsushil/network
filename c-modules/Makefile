# Makefile — builds the libpcap packet sniffer
#
# Prerequisites
#   macOS:  Xcode Command Line Tools  (xcode-select --install)
#           libpcap is included with the SDK
#   Linux:  gcc + libpcap-dev  (sudo apt install libpcap-dev)
#
# Usage
#   make          — build sniffer binary
#   make clean    — remove built binary
#   make run      — build and run with defaults (requires sudo)

CC      = gcc
CFLAGS  = -Wall -Wextra -O2 -std=c11
LDFLAGS = -lpcap
TARGET  = sniffer
SRC     = sniffer.c

# Default interface and packet count for `make run`
IFACE ?= en0
COUNT ?= 100

.PHONY: all clean run

all: $(TARGET)

$(TARGET): $(SRC)
	$(CC) $(CFLAGS) -o $@ $< $(LDFLAGS)

# Run with sudo — libpcap requires elevated privileges to open a raw socket,
# the same reason SSD firmware flash tools need root access on Linux.
run: $(TARGET)
	sudo ./$(TARGET) $(IFACE) $(COUNT)

clean:
	rm -f $(TARGET)
