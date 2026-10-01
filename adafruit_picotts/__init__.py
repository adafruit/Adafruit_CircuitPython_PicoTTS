# SPDX-FileCopyrightText: 2026 Adafruit Industries
# SPDX-License-Identifier: MIT
"""
`adafruit_picotts`
================================================================================

Text to speech for CircuitPython using the SVOX Pico engine by SVOX AG (Apache-2.0).

The engine is a native ``.mpy`` (``picotts_native.<arch>.mpy``) and the en-US voice ships in
the package, so it runs on stock CircuitPython 11. It needs a board with PSRAM: about 2.5 MB of
RAM for the voice and the engine.

**Software and Dependencies:**

* Adafruit CircuitPython firmware 11 or later for the supported boards:
  https://circuitpython.org/downloads
"""

__version__ = "0.0.0+auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_CircuitPython_PicoTTS.git"

import array
import gc
import os

try:
    from adafruit_picotts import picotts_native as _native
except ImportError as e:
    raise ImportError(
        "picotts_native not found; needs CircuitPython 11 or later with native .mpy loading "
        "and a picotts_native.<arch>.mpy for this chip"
    ) from e

_SAMPLE_RATE = 16000
_NATURAL_WPM = 206  # Pico's speaking rate at <speed level="100">, measured
# Pico's markup accepts 20 to 500 % speed and 50 to 200 % pitch (svox/picotok.c).
_SPEED_MIN = 20
_SPEED_MAX = 500
_PITCH_MIN = 0.5
_PITCH_MAX = 2.0
# Mixer buffer in bytes. Same value and reasoning as adafruit_moonshine_klatt: the mixer fills
# halves of it from a background callback, so a stall longer than one half skips. Pass a
# MixerVoice from your own Mixer for a larger buffer if other code stalls the loop.
_MIXER_BUFFER_SIZE = 1024
# Speech buffer: one allocation in TTS(), the largest block the heap allows, capped at 30 s
# (960 KB). A handover to the mixer inside speech can leave a short dropout, and Pico speech is
# continuous, so a dropout inside a word sounds garbled. With 30 s, the pre-buffer renders a
# whole sentence of up to 15 s (half the ring) before it plays, and it plays as one run with no
# handover. _RESERVE is left free for the main loop.
_MAX_BUFFER_SAMPLES = 30 * _SAMPLE_RATE
_RESERVE = 16384
# Samples rendered per update() call: 10 ms of audio, about 4 ms of work on a 150 MHz RP2350.
# The native engine blocks background tasks while it works, so one call must stay well under
# the mixer's 16 ms half-buffer or playback starves. Pieces that sit next to each other in the
# ring play as one RawSample of up to half the ring.
_PIECE = 160
# A handover to the mixer inside speech leaves up to one mixer half-buffer of silence. 2 ms
# fades on both sides of it turn a click into a short dropout.
_EDGE = 32
# When a run has to end inside speech (longer text, or a long say(..., wait=False) queue), it
# ends at the quietest 10 ms of its last 300 ms instead, so the dropout lands in a pause.
_QUIET_WINDOW = 4800
_QUIET_BLOCK = 160
_VOICES = ("en-US",)
# Engine working memory. Pico keeps a fixed 1,000,000 byte block inside it; the rest is
# system overhead.
_MEMORY_SIZE = 1100000
_VOICE_DIR = __file__.rsplit("/", 1)[0]
_VOICE_FILES = {"en-US": ("en-US_ta.bin", "en-US_lh0_sg.bin")}


def _load(path):
    """Read a whole file into one buffer. The engine reads the voice from it in place."""
    buf = bytearray(os.stat(path)[6])
    with open(path, "rb") as f:
        f.readinto(buf)
    return buf


def _is_mixer_voice(obj) -> bool:
    # audiomixer exports only Mixer, not the MixerVoice type. Of the objects TTS accepts, only
    # a MixerVoice has a level.
    return hasattr(obj, "level")


class _Engine:
    """The native engine: renders 16 kHz mono samples for one text at a time. It reads the
    voice buffers, its working memory and the current text in place, so it keeps references to
    all of them."""

    def __init__(self, ta, sg, memory_size):
        self._ta = ta
        self._sg = sg
        self._text = None
        self._memory = bytearray(memory_size)
        self._state = bytearray(_native.state_size())
        status = _native.init(self._state, self._memory, ta, sg)
        if status:
            self._state = None
            raise RuntimeError(f"picotts failure: {status}")

    def deinit(self):
        if self._state is not None:
            _native.deinit(self._state)
        self._ta = self._sg = self._text = self._memory = self._state = None

    def start(self, text):
        # NUL-terminated; the NUL flushes the engine.
        self._text = text.encode("utf-8") + b"\0"
        _native.start(self._state, self._text)

    def stop(self):
        _native.stop(self._state)
        self._text = None

    @property
    def speaking(self):
        return _native.speaking(self._state)

    def render(self, buffer):
        n = _native.render(self._state, buffer)
        if n < 0:
            self._text = None
            raise RuntimeError(f"picotts failure: {n}")
        return n


class TTS:
    """Speak text through an audio output.

    :param audio: An audio output object with ``play()``, ``stop()`` and ``playing``, such as
        `audiobusio.I2SOut`, `audioio.AudioOut` or `audiopwmio.PWMAudioOut`. The library
        creates its own `audiomixer.Mixer` on it. Or an `audiomixer.MixerVoice` from the
        caller's mixer, whose sample rate must match `sample_rate`.
    """

    def __init__(self, audio) -> None:
        self._queue = []
        self._text_active = False  # the engine is rendering a text
        # Rendered pieces are (start, end, text_start, text_end) spans of one ring buffer, laid
        # down in order after the ones still playing or waiting, so nothing is allocated per
        # piece and the heap does not fragment.
        self._buf = None
        self._cap = 0
        self._pending = []  # rendered pieces waiting for the mixer voice, oldest first
        self._playing = None  # (start, end) of the span the mixer voice is playing
        self._piece_start = True  # the next piece is the first of its text
        # Pre-buffer: before speech starts, and after running dry, render until the ring is
        # full before playing, like adafruit_moonshine_klatt.
        self._filling = False
        self._rate = 150
        self._volume = 1.0
        self._pitch = 1.0
        self._voice_name = _VOICES[0]

        if _is_mixer_voice(audio):
            self._audio = None
            self._mixer = None
            self._mixer_voice = audio
        else:
            import audiomixer  # noqa: PLC0415

            self._audio = audio
            self._mixer = audiomixer.Mixer(
                voice_count=1,
                buffer_size=_MIXER_BUFFER_SIZE,
                sample_rate=_SAMPLE_RATE,
                channel_count=1,
                bits_per_sample=16,
                samples_signed=True,
            )
            self._mixer_voice = self._mixer.voice[0]
            audio.play(self._mixer)
        self._mixer_voice.level = self._volume
        # Long-lived allocations first (voice and engine, about 2.5 MB), then the speech buffer.
        ta_name, sg_name = _VOICE_FILES[self._voice_name]
        self._engine = _Engine(
            _load(_VOICE_DIR + "/" + ta_name), _load(_VOICE_DIR + "/" + sg_name), _MEMORY_SIZE
        )
        self._alloc_buffer()

    @property
    def sample_rate(self) -> int:
        """Sample rate of the speech output in Hz."""
        return _SAMPLE_RATE

    @property
    def speaking(self) -> bool:
        """True while speech is playing or queued."""
        return (
            self._mixer_voice.playing
            or bool(self._pending)
            or self._text_active
            or bool(self._queue)
        )

    @property
    def rate(self) -> int:
        """Speaking rate in words per minute. Default 150."""
        return self._rate

    @rate.setter
    def rate(self, value: int) -> None:
        if value <= 0:
            raise ValueError("rate must be > 0")
        self._rate = value

    @property
    def volume(self) -> float:
        """Volume from 0.0 to 1.0, applied as the mixer voice level. Default 1.0."""
        return self._volume

    @volume.setter
    def volume(self, value: float) -> None:
        self._volume = min(max(value, 0.0), 1.0)
        self._mixer_voice.level = self._volume

    @property
    def pitch(self) -> float:
        """Pitch multiplier, 1.0 is normal. Clamped to 0.5 to 2.0."""
        return self._pitch

    @pitch.setter
    def pitch(self, value: float) -> None:
        self._pitch = min(max(value, _PITCH_MIN), _PITCH_MAX)

    @property
    def voice(self) -> str:
        """Voice preset name. See `voices` for the ones available."""
        return self._voice_name

    @voice.setter
    def voice(self, name: str) -> None:
        if name not in _VOICES:
            raise ValueError(f"voice must be one of {_VOICES}")
        self._voice_name = name

    @property
    def voices(self) -> tuple:
        """Voice preset names available."""
        return _VOICES

    def say(self, text: str, *, wait: bool = True, interrupt: bool = False) -> None:
        """Speak ``text``. If speech is already playing, ``text`` is queued after it.

        :param str text: The text to speak.
        :param bool wait: If True, return when all queued speech ends. If False, return
            right away; call `update` in the main loop to keep speech going.
        :param bool interrupt: If True, stop current speech and clear the queue first.
        """
        if interrupt:
            self.stop()
        self._queue.append(text)
        self.update()
        if wait:
            while self.speaking:
                self.update()

    def update(self) -> None:
        """Render and queue the next chunk of speech when the mixer is ready for it. Call
        often from the main loop after ``say(..., wait=False)``."""
        if self._playing is not None and not self._mixer_voice.playing:
            self._playing = None
        if self._playing is None and not self._pending and self._more_to_render():
            self._filling = True  # nothing playing and nothing ready: pre-buffer first
        self._play_next()
        # One piece of work per call, so the caller's loop, and the handover to the mixer,
        # never wait for a whole sentence to render.
        piece = self._render_step()
        if piece is None:
            if self._filling:
                self._filling = False  # ring full, or the text is all rendered
                self._play_next()
        else:
            # A piece that carries on from the last pending one joins it, up to half the ring,
            # so the pending list stays a few entries long however small the pieces are.
            pending = self._pending
            prev = pending[-1] if pending else None
            if (
                prev is not None
                and not piece[2]
                and prev[1] == piece[0]
                and piece[1] - prev[0] <= self._cap // 2
            ):
                pending[-1] = (prev[0], piece[1], prev[2], piece[3])
            else:
                pending.append(piece)
            self._play_next()

    def _more_to_render(self):
        return self._text_active or bool(self._queue)

    def _play_next(self):
        if self._playing is None and self._pending and not self._filling:
            import audiocore  # noqa: PLC0415

            # Merge pieces that sit next to each other into one run, up to half the ring, so
            # the other half is free to render into while this run plays.
            pending = self._pending
            first = pending.pop(0)
            last = first
            limit = first[0] + self._cap // 2
            if self._cap - limit < 2 * _QUIET_WINDOW:
                limit = self._cap  # take the sliver up to the end of the ring along too
            while pending and pending[0][0] == last[1] and pending[0][1] <= limit:
                last = pending.pop(0)
            start, end = first[0], last[1]
            out = self._buf
            # A run that ends inside a text ends at a quiet point instead, so the handover to
            # the next run lands in a pause. When the run stops at the end of the ring, the rest
            # moves to the start of the ring, where the speech after it is rendered next.
            if not last[3] and end - start >= 2 * _QUIET_WINDOW:
                at_ring_end = end + _PIECE > self._cap
                if not (at_ring_end and pending):  # wrapped pieces already sit at the start
                    cut = self._quiet_point(start, end)
                    if cut < end:
                        if at_ring_end:
                            out[0 : end - cut] = out[cut:end]
                            pending.insert(0, (0, end - cut, False, last[3]))
                        else:
                            pending.insert(0, (cut, end, False, last[3]))
                        end = cut
            edge = min(_EDGE, (end - start) // 2)
            if not first[2]:  # starts inside a text
                for i in range(edge):
                    out[start + i] = out[start + i] * i // edge
            if not last[3]:  # ends inside a text
                for i in range(edge):
                    out[end - 1 - i] = out[end - 1 - i] * i // edge
            self._playing = (start, end)
            self._mixer_voice.play(
                audiocore.RawSample(memoryview(out)[start:end], sample_rate=_SAMPLE_RATE)
            )

    def _quiet_point(self, start, end):
        """End of the quietest _QUIET_BLOCK of samples in the last _QUIET_WINDOW of the span
        [start, end), keeping at least half of the span."""
        out = self._buf
        lo = max(start + (end - start) // 2, end - _QUIET_WINDOW)
        best = end
        best_level = None
        i = end - _QUIET_BLOCK
        while i >= lo:
            level = 0
            for k in range(i, i + _QUIET_BLOCK, 4):  # every 4th sample is enough to rank
                v = out[k]
                level += v if v >= 0 else -v
            if best_level is None or level < best_level:
                best_level = level
                best = i + _QUIET_BLOCK // 2
            i -= _QUIET_BLOCK
        return best

    def stop(self) -> None:
        """Stop speaking and clear the queue."""
        self._queue.clear()
        if self._text_active:
            self._engine.stop()
            self._text_active = False
        self._pending = []
        self._filling = False
        self._mixer_voice.stop()
        self._playing = None

    def _start_next_text(self):
        """Hand the next queued text to the engine with the current rate and pitch."""
        speed = min(max(self._rate * 100 // _NATURAL_WPM, _SPEED_MIN), _SPEED_MAX)
        pitch = int(self._pitch * 100)
        text = self._queue.pop(0)
        self._engine.start(f'<speed level="{speed}"><pitch level="{pitch}">{text}</pitch></speed>')
        self._text_active = True
        self._piece_start = True

    def _place(self, size):
        """Start of a free span of ``size`` samples in the ring buffer after the pieces still in
        use, or None until enough of them have played."""
        busy = self._pending if self._playing is None else [self._playing] + self._pending
        if not busy:
            return 0 if size <= self._cap else None
        tail = busy[0][0]  # start of the oldest span in use
        head = busy[-1][1]  # end of the newest
        if head > tail:  # in use: [tail, head), free: [head, cap) and [0, tail)
            if head + size <= self._cap:
                return head
            return 0 if size <= tail else None
        # Wrapped. In use: [tail, cap) and [0, head), free: [head, tail)
        return head if head + size <= tail else None

    def _render_step(self):
        """Render one piece. Returns it as (start, end, text_start, text_end), or None when
        nothing is left or there is no room in the ring until more of the queued pieces have
        played."""
        while True:
            if not self._text_active:
                if not self._queue:
                    return None
                self._start_next_text()
            size = min(_PIECE, self._cap)
            start = self._place(size)
            if start is None:
                return None
            n = self._engine.render(memoryview(self._buf)[start : start + size])
            text_start = self._piece_start
            self._piece_start = False
            text_end = not self._engine.speaking
            if text_end:
                self._text_active = False
            if n:
                return (start, start + n, text_start, text_end)
            # Nothing came out (the text was empty or already drained): try the next one.

    def _alloc_buffer(self):
        """Allocate the ring buffer: the largest single block the heap can give, up to 3 s,
        leaving _RESERVE free. gc.mem_free() counts scattered free space, so the size is found
        by trying allocations (binary search to within one piece)."""
        gc.collect()
        lo = 0
        hi = min(_MAX_BUFFER_SAMPLES, (gc.mem_free() - _RESERVE) // 2)
        while hi - lo > _PIECE:
            mid = (lo + hi) // 2
            try:
                # One allocation; array("h", bytes(n)) would briefly need twice the memory.
                array.array("h", [0]) * mid  # allocated and dropped: only testing that it fits
                lo = mid
            except MemoryError:
                hi = mid
        if hi > lo:
            try:
                array.array("h", [0]) * hi  # allocated and dropped: only testing that it fits
                lo = hi
            except MemoryError:
                pass
        if lo < _PIECE:
            raise MemoryError("not enough RAM for the speech buffer")
        gc.collect()
        self._buf = array.array("h", [0]) * lo
        self._cap = lo

    def deinit(self) -> None:
        """Stop speaking and release the engine and the mixer this object created. The audio
        output and a caller's mixer are not deinitialized; the caller owns them."""
        self.stop()
        self._buf = None
        if self._engine is not None:
            self._engine.deinit()
            self._engine = None
        if self._mixer is not None:
            self._audio.stop()
            self._mixer.deinit()
            self._mixer = None

    def __enter__(self) -> "TTS":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.deinit()
