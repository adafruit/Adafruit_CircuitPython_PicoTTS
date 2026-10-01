# SPDX-FileCopyrightText: 2026 Mikey Sklar for Adafruit Industries
# SPDX-License-Identifier: MIT

"""Speak three sentences on a Feather RP2350 with 8 MB PSRAM through a MAX98357A I2S amp.

Wiring: amp BCLK to D9, LRC to D10, DIN to D11, Vin to USB, GND to GND.
Copy en-US_ta.bin and en-US_lh0_sg.bin from the SVOX Pico lingware to /voices on CIRCUITPY.
"""

import array
import os
import time

import audiobusio
import audiocore
import board
import picotts

SAMPLE_RATE = 16000  # picotts always renders 16 kHz mono


def load(path):
    """Read a whole file into one buffer. The engine reads the voice from it in place."""
    buf = bytearray(os.stat(path)[6])
    with open(path, "rb") as f:
        f.readinto(buf)
    return buf


# Load the voice first, while the heap has the most room (1.43 MB, about 0.5 s).
engine = picotts.Engine(load("/voices/en-US_ta.bin"), load("/voices/en-US_lh0_sg.bin"))

# On the RP2040 and RP2350, bit clock and word select must be consecutive GPIOs: D9 and D10.
audio = audiobusio.I2SOut(board.D9, board.D10, board.D11)

# Render each sentence fully, then play it. Up to 8 s of audio (256 KB).
out = array.array("h", [0]) * (SAMPLE_RATE * 8)

for text in (
    "Hello from Circuit Python on the Feather.",
    "This is the S VOX Pico voice.",
    "Dr. Smith read 1,234 pages on the 1st of May.",
):
    print(text)
    engine.start(text)
    n = 0
    while engine.speaking and n < len(out):
        n += engine.render(memoryview(out)[n:])
    audio.play(audiocore.RawSample(memoryview(out)[:n], sample_rate=SAMPLE_RATE))
    while audio.playing:
        pass
    time.sleep(0.5)

engine.deinit()
