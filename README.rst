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
engine by SVOX AG, released under the Apache License 2.0. It speaks English (en-US) at 16 kHz
and handles numbers, abbreviations and dates on the board.

The engine and its 1.4 MB voice are built into the firmware as the ``picotts`` core module. This
library will add a higher level API on top of it. For now, see the example for using
``picotts`` directly.


Dependencies
=============
This library depends on:

* `Adafruit CircuitPython <https://github.com/adafruit/circuitpython>`_ firmware built with the
  ``picotts`` core module

The engine needs about 1.1 MB of RAM and the voice about 1.4 MB of firmware flash, so
``picotts`` is only enabled on boards with PSRAM and room for it:

======================  =============================================
Board                   Status
======================  =============================================
Fruit Jam (RP2350)      Working
======================  =============================================

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

    import array

    import picotts

    engine = picotts.Engine()
    engine.start("Hello from Circuit Python.")
    out = array.array("h", [0]) * (16000 * 4)
    n = 0
    while engine.speaking and n < len(out):
        n += engine.render(memoryview(out)[n:])
    # out[:n] now holds 16 kHz mono speech, ready for audiocore.RawSample

See ``examples/picotts_fruitjam_simpletest.py`` for playback on the Fruit Jam.

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
