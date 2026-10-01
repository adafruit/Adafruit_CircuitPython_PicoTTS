// SPDX-FileCopyrightText: Copyright (c) 2026 Mikey Sklar for Adafruit Industries
//
// SPDX-License-Identifier: MIT

// Minimal libc for the native module: a native .mpy cannot call the firmware C library.
#include <stddef.h>
#include <stdarg.h>

int picotts_errno_value;
int *__errno(void) { return &picotts_errno_value; }

size_t strlen(const char *s) { const char *p = s; while (*p) p++; return p - s; }
int strcmp(const char *a, const char *b) {
    while (*a && *a == *b) { a++; b++; }
    return (unsigned char)*a - (unsigned char)*b;
}
int strncmp(const char *a, const char *b, size_t n) {
    for (; n; n--, a++, b++) {
        if (*a != *b || !*a) return (unsigned char)*a - (unsigned char)*b;
    }
    return 0;
}
int memcmp(const void *a, const void *b, size_t n) {
    const unsigned char *x = a, *y = b;
    for (; n; n--, x++, y++) if (*x != *y) return *x - *y;
    return 0;
}
char *strchr(const char *s, int c) {
    for (;; s++) { if (*s == (char)c) return (char *)s; if (!*s) return NULL; }
}
char *strstr(const char *h, const char *n) {
    size_t k = strlen(n);
    for (; *h; h++) if (!strncmp(h, n, k)) return (char *)h;
    return k ? NULL : (char *)h;
}
char *strcpy(char *d, const char *s) { char *r = d; while ((*d++ = *s++)); return r; }
char *strcat(char *d, const char *s) { strcpy(d + strlen(d), s); return d; }
int atoi(const char *s) {
    int v = 0, neg = 0;
    while (*s == 32) s++;
    if (*s == 45) { neg = 1; s++; } else if (*s == 43) s++;
    while (*s >= 48 && *s <= 57) v = v * 10 + (*s++ - 48);
    return neg ? -v : v;
}
// Only used for engine diagnostic messages; they come out empty.
int vsprintf(char *d, const char *f, va_list ap) { (void)f; (void)ap; d[0] = 0; return 0; }
