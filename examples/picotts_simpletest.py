# SPDX-FileCopyrightText: 2026 Mikey Sklar for Adafruit Industries
# SPDX-License-Identifier: MIT
"""Speak a few phrases through an I2S amplifier.

Needs a board with PSRAM, such as a Feather RP2350 with 8 MB PSRAM, and a MAX98357A amp:
BCLK to A0, LRC to A1, DIN to A2. For the Fruit Jam, see picotts_fruitjam.py.
"""

import time

import audiobusio
import board

import adafruit_picotts as speech

# On the RP2350, bit clock and word select must be consecutive GPIOs: A0 and A1 are GPIO26
# and GPIO27.
audio = audiobusio.I2SOut(board.A0, board.A1, board.A2)

tts = speech.TTS(audio)

while True:
    for text in (
        "Hello from Circuit Python.",
        "This is the S VOX Pico voice.",
        "Dr. Smith read 1,234 pages on the 1st of May.",
    ):
        start = time.monotonic()
        tts.say(text)
        print(f"{text} {time.monotonic() - start:.2f} s")
        time.sleep(1)
    time.sleep(3)
