Introduction
============


.. image:: https://readthedocs.org/projects/adafruit-circuitpython-picotts/badge/?version=latest
    :target: https://docs.circuitpython.org/projects/picotts/en/latest/
    :alt: Documentation Status


.. image:: https://raw.githubusercontent.com/adafruit/Adafruit_CircuitPython_Bundle/main/badges/adafruit_discord.svg
    :target: https://adafru.it/discord
    :alt: Discord


.. image:: https://github.com/adafruit/Adafruit_CircuitPython_PicoTTS/workflows/Build%20CI/badge.svg
    :target: https://github.com/adafruit/Adafruit_CircuitPython_PicoTTS/actions
    :alt: Build Status


.. image:: https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json
    :target: https://github.com/astral-sh/ruff
    :alt: Code Style: Ruff

Text to speech for CircuitPython using the `SVOX Pico <https://github.com/lllucius/esp32_picotts>`_
engine by SVOX AG, released under the Apache License 2.0. It speaks English (en-US) at 16 kHz,
handles numbers, abbreviations and dates on the board, and plays through ``audiomixer``. The
engine and voice ship in the library, so it runs on stock CircuitPython with no core module.

``say()`` waits until the text has been spoken. ``say(text, wait=False)`` returns right away;
call ``update()`` from your main loop to keep speaking.


Dependencies
=============
This library depends on:

* `Adafruit CircuitPython <https://github.com/adafruit/circuitpython>`_ 11 or later

The engine is a precompiled native module, ``picotts_native.armv7emsp.mpy``, for the RP2350.
The engine needs about 1.1 MB of RAM and the en-US voice (``en_US_ta.bin`` and
``en_US_lh0_sg.bin``, in the library) another 1.43 MB, about 2.5 MB in all, so it needs a
board with PSRAM:

================================  ===================================
Board                             Status
================================  ===================================
Fruit Jam (RP2350)                Working
Feather RP2350 with 8 MB PSRAM    Runs, audio check pending
================================  ===================================

This library does not run on Blinka.

Please ensure all dependencies are available on the CircuitPython filesystem.
This is easily achieved by downloading
`the Adafruit library and driver bundle <https://circuitpython.org/libraries>`_
or individual libraries can be installed using
`circup <https://github.com/adafruit/circup>`_.

Installing to a Connected CircuitPython Device with Circup
==========================================================

Make sure that you have ``circup`` installed in your Python environment.
Install it with the following command if necessary:

.. code-block:: shell

    pip3 install circup

With ``circup`` installed and your CircuitPython device connected use the
following command to install:

.. code-block:: shell

    circup install adafruit_picotts

Or the following command to update an existing version:

.. code-block:: shell

    circup update

Usage Example
=============

.. code-block:: python

    import audiobusio
    import board

    import adafruit_picotts as speech

    audio = audiobusio.I2SOut(board.A0, board.A1, board.A2)
    tts = speech.TTS(audio)
    tts.say("Hello from Circuit Python.")

See ``examples/picotts_fruitjam.py`` for the Fruit Jam's TLV320 DAC.

Speed and memory
================

Rendering takes about 0.6 times real time on the RP2350, but the engine analyzes each sentence
before any of it is spoken, which takes from under a second to several seconds for a long
sentence. ``TTS`` fills a buffer before it starts playing, so a sentence of up to 15 s plays
without a break.

``TTS()`` loads the voice and allocates its buffers once, taking the largest block the heap
allows for the speech buffer (up to 30 s of audio, 960 KB). Create it early, before other large
allocations.

Building the engine
===================

``src/svox`` is the SVOX Pico engine source. ``src/Makefile`` builds it with
``py/dynruntime.mk`` into ``adafruit_picotts/picotts_native.<arch>.mpy``:

.. code-block:: shell

    cd src
    make MPY_DIR=path/to/circuitpython ARCH=armv7emsp

Use the CircuitPython tree of the version the file will run on.

Credits
=======

The speech engine and en-US voice are SVOX Pico, Copyright (C) 2008-2009 SVOX AG, licensed under
the Apache License 2.0. This library is MIT licensed.

Documentation
=============
API documentation for this library can be found on `Read the Docs <https://docs.circuitpython.org/projects/picotts/en/latest/>`_.

For information on building library documentation, please check out
`this guide <https://learn.adafruit.com/creating-and-sharing-a-circuitpython-library/sharing-our-docs-on-readthedocs#sphinx-5-1>`_.

Contributing
============

Contributions are welcome! Please read our `Code of Conduct
<https://github.com/adafruit/Adafruit_CircuitPython_PicoTTS/blob/HEAD/CODE_OF_CONDUCT.md>`_
before contributing to help this project stay welcoming.
