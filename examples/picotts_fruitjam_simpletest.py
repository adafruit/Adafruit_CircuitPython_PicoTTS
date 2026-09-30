# SPDX-FileCopyrightText: 2026 Mikey Sklar for Adafruit Industries
# SPDX-License-Identifier: MIT

"""Speak three sentences on the Fruit Jam with the picotts core module."""

import array
import time

import adafruit_tlv320
import audiobusio
import audiocore
import board
import picotts
import pwmio

SAMPLE_RATE = 16000  # picotts always renders 16 kHz mono
VOLUME = 0.75  # 0.0 to 1.0

mclk = pwmio.PWMOut(board.I2S_MCLK, frequency=15_000_000, duty_cycle=2**15)
dac = adafruit_tlv320.TLV320DAC3100(board.I2C())
# The driver has no 16 kHz clock setting. Set up 48 kHz, then raise the DAC oversampling
# (DOSR, page 0 registers 0x0D and 0x0E) from 128 to 384 on the same PLL, giving 16 kHz.
dac.configure_clocks(sample_rate=48000, bit_depth=16, mclk_freq=mclk.frequency)
dac._page0._write_register(0x0D, 384 >> 8)
dac._page0._write_register(0x0E, 384 & 0xFF)
dac.headphone_output = True
dac.speaker_output = True
dac.dac_volume = -63 + VOLUME * 86

audio = audiobusio.I2SOut(board.I2S_BCLK, board.I2S_WS, board.I2S_DIN)
engine = picotts.Engine()

# Render each sentence fully, then play it. Up to 8 s of audio (256 KB).
out = array.array("h", [0]) * (SAMPLE_RATE * 8)

for text in (
    "Hello from Circuit Python on the Fruit Jam.",
    "This is the S VOX Pico voice, built into the firmware.",
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
