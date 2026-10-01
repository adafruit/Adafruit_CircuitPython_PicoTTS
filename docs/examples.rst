Simple test
------------

Ensure your device works with this simple test. It speaks through a MAX98357A I2S amp on D9,
D10 and D11 of a board with PSRAM, such as a Feather RP2350 with 8 MB PSRAM.

.. literalinclude:: ../examples/picotts_simpletest.py
    :caption: examples/picotts_simpletest.py
    :linenos:

Fruit Jam
---------

Speak through the Fruit Jam's TLV320 DAC, on the speaker and headphone jack.

.. literalinclude:: ../examples/picotts_fruitjam.py
    :caption: examples/picotts_fruitjam.py
    :linenos:
