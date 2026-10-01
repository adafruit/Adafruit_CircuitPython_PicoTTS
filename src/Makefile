# SPDX-FileCopyrightText: 2026 Mikey Sklar for Adafruit Industries
# SPDX-License-Identifier: MIT
#
# picotts_native: the SVOX Pico engine (svox/, Apache-2.0) as a native .mpy for one architecture.
#   make MPY_DIR=path/to/circuitpython ARCH=armv7emsp
# Writes ../adafruit_picotts/picotts_native.$(ARCH).mpy. Use the CircuitPython tree whose firmware
# will load it (the .mpy version must match). Needs the arch's gcc on PATH and, for mpy_ld,
# `pip install pyelftools ar`. Boards find the file by microcontroller.cpu.architecture.

MPY_DIR ?= ../../circuitpython
ARCH ?= armv7emsp
MOD = picotts_native
SRC = picotts_native.c shim.c $(wildcard svox/*.c)
LINK_RUNTIME = 1
OUT = ../adafruit_picotts/$(MOD).$(ARCH).mpy

# CIRCUITPY selects the svox platform without file I/O (svox/picopltf.h). The engine is
# third-party code built as-is, so its warnings are silenced. genhdr/mpversion.h is generated
# below; CircuitPython's mpconfig.h includes it.
CFLAGS_EXTRA = -I$(CURDIR)/build-gen -I$(CURDIR)/svox -DCIRCUITPY -w -Os \
	-fno-single-precision-constant -fno-short-enums

all: $(OUT)

$(OUT): $(MOD).mpy
	cp $< $@

build-gen/genhdr/mpversion.h:
	mkdir -p build-gen/genhdr
	python3 $(MPY_DIR)/py/makeversionhdr.py $@

$(SRC): build-gen/genhdr/mpversion.h

include $(MPY_DIR)/py/dynruntime.mk
