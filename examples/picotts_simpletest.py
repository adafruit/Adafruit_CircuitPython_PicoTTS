# SPDX-FileCopyrightText: 2026 Mikey Sklar for Adafruit Industries
# SPDX-License-Identifier: MIT
"""Speak a few phrases through an I2S amplifier.

Needs a board with PSRAM, such as a Feather RP2350 with 8 MB PSRAM, and a MAX98357A amp:
BCLK to D9, LRC to D10, DIN to D11. For the Fruit Jam, see picotts_fruitjam.py.
"""

import time

import audiobusio
import board

import adafruit_picotts as speech

# On the RP2350, bit clock and word select must be consecutive GPIOs: D9 and D10.
audio = audiobusio.I2SOut(board.D9, board.D10, board.D11)

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
