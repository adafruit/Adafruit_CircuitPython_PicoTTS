// SPDX-FileCopyrightText: Copyright (c) 2026 Mikey Sklar for Adafruit Industries
//
// SPDX-License-Identifier: MIT

// picotts_native: the SVOX Pico engine as a native .mpy, driven by adafruit_picotts.Engine.
//
// Engine state lives in a bytearray from state_size(), so this module keeps no globals. The
// Python side owns every buffer (state, working memory, voice, text) and keeps them alive while
// the engine uses them; the engine reads the voice and text in place.

#include "py/dynruntime.h"

#include "picoapi.h"

#define VOICE ((const pico_Char *)"en-US")

// pico_getData is called with at most this many bytes, as in the SVOX examples.
#define CHUNK_BYTES (1024)

typedef struct {
    pico_System system;
    pico_Engine engine;
    const pico_Char *text;   // NUL-terminated; the NUL flushes the engine
    size_t text_len;         // including the NUL
    size_t text_pos;
    // pico_getData fails if one output item does not fit, and items are up to 255 bytes. When
    // less room than that is left in the caller's buffer, output goes here first.
    int16_t carry[128];
    uint16_t carry_len;
    uint16_t carry_pos;
} state_t;

static state_t *get_state(mp_obj_t obj) {
    mp_buffer_info_t buf;
    mp_get_buffer_raise(obj, &buf, MP_BUFFER_RW);
    if (buf.len < sizeof(state_t)) {
        mp_raise_ValueError(MP_ERROR_TEXT("state too small"));
    }
    return (state_t *)buf.buf;
}

static void stop(state_t *s) {
    s->text = NULL;
    s->text_len = 0;
    s->text_pos = 0;
    s->carry_len = 0;
    s->carry_pos = 0;
}

// state_size() -> int: bytes needed for the state bytearray.
static mp_obj_t state_size(void) {
    return mp_obj_new_int(sizeof(state_t));
}
static MP_DEFINE_CONST_FUN_OBJ_0(state_size_obj, state_size);

// init(state, memory, ta, sg) -> int: 0, or the Pico status on failure. memory is the engine's
// working memory (about 1.1 MB); ta and sg are the contents of the two voice files.
static mp_obj_t init(size_t n_args, const mp_obj_t *args) {
    state_t *s = get_state(args[0]);
    mp_buffer_info_t memory, ta, sg;
    mp_get_buffer_raise(args[1], &memory, MP_BUFFER_RW);
    mp_get_buffer_raise(args[2], &ta, MP_BUFFER_READ);
    mp_get_buffer_raise(args[3], &sg, MP_BUFFER_READ);
    stop(s);
    s->system = NULL;
    s->engine = NULL;
    pico_Status status = pico_initialize(memory.buf, memory.len, &s->system);
    if (status == PICO_OK) {
        status = pico_defineVoice(s->system, VOICE, sg.buf, ta.buf);
    }
    if (status == PICO_OK) {
        status = pico_newEngine(s->system, VOICE, &s->engine);
    }
    if (status != PICO_OK && s->system != NULL) {
        pico_terminate(&s->system);
        s->system = NULL;
    }
    return mp_obj_new_int(status);
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(init_obj, 4, 4, init);

// deinit(state): release the engine. Safe to call more than once.
static mp_obj_t deinit(mp_obj_t state) {
    state_t *s = get_state(state);
    if (s->engine != NULL) {
        pico_disposeEngine(s->system, &s->engine);
        s->engine = NULL;
    }
    if (s->system != NULL) {
        pico_terminate(&s->system);
        s->system = NULL;
    }
    stop(s);
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_1(deinit_obj, deinit);

// start(state, text): start speaking text, a NUL-terminated bytes. Drops any text not yet
// rendered.
static mp_obj_t start(mp_obj_t state, mp_obj_t text) {
    state_t *s = get_state(state);
    mp_buffer_info_t buf;
    mp_get_buffer_raise(text, &buf, MP_BUFFER_READ);
    pico_resetEngine(s->engine, PICO_RESET_SOFT);
    stop(s);
    s->text = buf.buf;
    s->text_len = buf.len;
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_2(start_obj, start);

// stop(state): drop any text not yet rendered.
static mp_obj_t stop_fun(mp_obj_t state) {
    state_t *s = get_state(state);
    pico_resetEngine(s->engine, PICO_RESET_SOFT);
    stop(s);
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_1(stop_obj, stop_fun);

// speaking(state) -> bool: True until render() has returned every sample for the text.
static mp_obj_t speaking(mp_obj_t state) {
    state_t *s = get_state(state);
    return mp_obj_new_bool(s->text != NULL || s->carry_pos < s->carry_len);
}
static MP_DEFINE_CONST_FUN_OBJ_1(speaking_obj, speaking);

// render(state, out) -> int: samples written to out, a buffer of 16-bit samples. Fewer than out
// holds only when the text is finished. Negative on an engine failure (the Pico status).
static mp_obj_t render(mp_obj_t state, mp_obj_t out) {
    state_t *s = get_state(state);
    mp_buffer_info_t buf;
    mp_get_buffer_raise(out, &buf, MP_BUFFER_WRITE);
    int16_t *buffer = buf.buf;
    size_t length = buf.len / sizeof(int16_t);
    size_t n = 0;
    while (n < length) {
        if (s->carry_pos < s->carry_len) {
            size_t k = length - n;
            if (k > (size_t)(s->carry_len - s->carry_pos)) {
                k = s->carry_len - s->carry_pos;
            }
            memcpy(buffer + n, s->carry + s->carry_pos, k * sizeof(int16_t));
            s->carry_pos += k;
            n += k;
            continue;
        }
        if (s->text == NULL) {
            break;
        }
        if (s->text_pos < s->text_len) {
            size_t remaining = s->text_len - s->text_pos;
            pico_Int16 sent = 0;
            pico_Status status = pico_putTextUtf8(s->engine, s->text + s->text_pos,
                (pico_Int16)(remaining < 32767 ? remaining : 32767), &sent);
            if (status != PICO_OK) {
                pico_resetEngine(s->engine, PICO_RESET_SOFT);
                stop(s);
                return mp_obj_new_int(status < 0 ? status : -status);
            }
            s->text_pos += sent;
        }
        // Straight into the caller's buffer when an item surely fits, else through carry.
        bool direct = (length - n) * sizeof(int16_t) >= sizeof(s->carry);
        int16_t *dest = direct ? buffer + n : s->carry;
        size_t want = sizeof(s->carry);
        if (direct) {
            want = (length - n) * sizeof(int16_t);
            if (want > CHUNK_BYTES) {
                want = CHUNK_BYTES;
            }
        }
        pico_Int16 got = 0;
        pico_Int16 type = 0;
        pico_Status status = pico_getData(s->engine, dest, (pico_Int16)want, &got, &type);
        if (direct) {
            n += got / sizeof(int16_t);
        } else {
            s->carry_len = got / sizeof(int16_t);
            s->carry_pos = 0;
        }
        if (status == PICO_STEP_IDLE && s->text_pos >= s->text_len) {
            // All text is in and the engine has nothing more to give: done once carry drains.
            s->text = NULL;
        } else if (status != PICO_STEP_BUSY && status != PICO_STEP_IDLE) {
            pico_resetEngine(s->engine, PICO_RESET_SOFT);
            stop(s);
            return mp_obj_new_int(status < 0 ? status : -status);
        }
    }
    return mp_obj_new_int(n);
}
static MP_DEFINE_CONST_FUN_OBJ_2(render_obj, render);

mp_obj_t mpy_init(mp_obj_fun_bc_t *self, size_t n_args, size_t n_kw, mp_obj_t *args) {
    MP_DYNRUNTIME_INIT_ENTRY
    mp_store_global(MP_QSTR_state_size, MP_OBJ_FROM_PTR(&state_size_obj));
    mp_store_global(MP_QSTR_init, MP_OBJ_FROM_PTR(&init_obj));
    mp_store_global(MP_QSTR_deinit, MP_OBJ_FROM_PTR(&deinit_obj));
    mp_store_global(MP_QSTR_start, MP_OBJ_FROM_PTR(&start_obj));
    mp_store_global(MP_QSTR_stop, MP_OBJ_FROM_PTR(&stop_obj));
    mp_store_global(MP_QSTR_speaking, MP_OBJ_FROM_PTR(&speaking_obj));
    mp_store_global(MP_QSTR_render, MP_OBJ_FROM_PTR(&render_obj));
    MP_DYNRUNTIME_INIT_EXIT
}
