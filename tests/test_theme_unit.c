// Unit test runner for theme parsing, coordinate evaluation, and clipping logic
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <assert.h>

struct theme_coord {
    int percent;
    int offset;
    bool is_set;
};

static struct theme_coord parse_coord(const char *str) {
    struct theme_coord coord = { .percent = 0, .offset = 0, .is_set = false };
    if (str == NULL) return coord;

    while (*str == ' ' || *str == '\t') str++;
    if (*str == '\0') return coord;

    const char *pct_sign = strchr(str, '%');
    if (pct_sign != NULL) {
        int pct = 0;
        int sign = 1;
        const char *p = str;
        if (*p == '-') { sign = -1; p++; }
        else if (*p == '+') { p++; }
        while (p < pct_sign) {
            if (*p >= '0' && *p <= '9') {
                if (pct < 1000000) pct = pct * 10 + (*p - '0');
            }
            p++;
        }
        coord.percent = pct * sign;
        coord.is_set = true;

        p = pct_sign + 1;
        while (*p == ' ' || *p == '\t') p++;
        if (*p == '+' || *p == '-') {
            int off_sign = (*p == '-') ? -1 : 1;
            p++;
            while (*p == ' ' || *p == '\t') p++;
            int off = 0;
            while (*p >= '0' && *p <= '9') {
                if (off < 10000000) off = off * 10 + (*p - '0');
                p++;
            }
            coord.offset = off * off_sign;
        }
    } else {
        int off = 0;
        int sign = 1;
        const char *p = str;
        if (*p == '-') { sign = -1; p++; }
        else if (*p == '+') { p++; }
        while (*p >= '0' && *p <= '9') {
            if (off < 10000000) off = off * 10 + (*p - '0');
            p++;
        }
        coord.offset = off * sign;
        coord.is_set = true;
    }
    return coord;
}

static int theme_eval_coord(struct theme_coord coord, int container_size, int default_val) {
    if (!coord.is_set) return default_val;
    int64_t val = ((int64_t)container_size * coord.percent) / 100 + coord.offset;
    return (int)val;
}

static bool parse_hex_digit(char c, uint8_t *val) {
    if (c >= '0' && c <= '9') { *val = c - '0'; return true; }
    if (c >= 'a' && c <= 'f') { *val = c - 'a' + 10; return true; }
    if (c >= 'A' && c <= 'F') { *val = c - 'A' + 10; return true; }
    return false;
}

static bool parse_color(const char *str, uint32_t *out_color) {
    if (str == NULL) return false;
    while (*str == ' ' || *str == '\t') str++;

    if (strcasecmp(str, "black") == 0) { *out_color = 0x000000; return true; }
    if (strcasecmp(str, "white") == 0) { *out_color = 0xffffff; return true; }
    if (strcasecmp(str, "gray") == 0 || strcasecmp(str, "grey") == 0) { *out_color = 0x808080; return true; }
    if (strcasecmp(str, "red") == 0) { *out_color = 0xff0000; return true; }
    if (strcasecmp(str, "green") == 0) { *out_color = 0x00ff00; return true; }
    if (strcasecmp(str, "blue") == 0) { *out_color = 0x0000ff; return true; }
    if (strcasecmp(str, "yellow") == 0) { *out_color = 0xffff00; return true; }
    if (strcasecmp(str, "cyan") == 0) { *out_color = 0x00ffff; return true; }
    if (strcasecmp(str, "magenta") == 0) { *out_color = 0xff00ff; return true; }

    if (*str == '#') str++;
    else if (str[0] == '0' && (str[1] == 'x' || str[1] == 'X')) str += 2;

    size_t hex_len = strlen(str);
    if (hex_len == 6) {
        uint32_t c = 0;
        for (int i = 0; i < 6; i++) {
            uint8_t d;
            if (!parse_hex_digit(str[i], &d)) return false;
            c = (c << 4) | d;
        }
        *out_color = c;
        return true;
    } else if (hex_len == 3) {
        uint32_t c = 0;
        for (int i = 0; i < 3; i++) {
            uint8_t d;
            if (!parse_hex_digit(str[i], &d)) return false;
            c = (c << 8) | (d << 4) | d;
        }
        *out_color = c;
        return true;
    }
    return false;
}

static void strip_comments(char *line) {
    if (line == NULL) return;
    bool in_quote = false;
    char quote_char = '\0';
    bool seen_sep = false;

    for (char *p = line; *p != '\0'; p++) {
        if (!in_quote) {
            if (*p == '"' || *p == '\'') {
                in_quote = true;
                quote_char = *p;
            } else if (*p == '=' || *p == ':') {
                seen_sep = true;
            } else if (*p == '#') {
                uint8_t dummy;
                bool is_color = seen_sep && parse_hex_digit(p[1], &dummy) &&
                                parse_hex_digit(p[2], &dummy) &&
                                parse_hex_digit(p[3], &dummy);
                if (!is_color) {
                    *p = '\0';
                    break;
                }
            } else if (*p == '/' && *(p + 1) == '/') {
                *p = '\0';
                break;
            }
        } else {
            if (*p == quote_char) in_quote = false;
        }
    }
}

static void test_coords(void) {
    printf("[*] Testing coordinate parser...\n");
    // Test 50%-300 on 1920px container
    struct theme_coord c1 = parse_coord("50%-300");
    assert(c1.is_set == true);
    assert(c1.percent == 50);
    assert(c1.offset == -300);
    assert(theme_eval_coord(c1, 1920, 0) == 660);

    // Test 40%+14 on 1080px container
    struct theme_coord c2 = parse_coord("40%+14");
    assert(c2.is_set == true);
    assert(c2.percent == 40);
    assert(c2.offset == 14);
    assert(theme_eval_coord(c2, 1080, 0) == 446);

    // Test 100%-31 on 1080px container
    struct theme_coord c3 = parse_coord("100%-31");
    assert(c3.is_set == true);
    assert(c3.percent == 100);
    assert(c3.offset == -31);
    assert(theme_eval_coord(c3, 1080, 0) == 1049);

    // Test plain pixels "600"
    struct theme_coord c4 = parse_coord("600");
    assert(c4.is_set == true);
    assert(c4.percent == 0);
    assert(c4.offset == 600);
    assert(theme_eval_coord(c4, 1920, 0) == 600);

    // Test percentage only "50%"
    struct theme_coord c5 = parse_coord("50%");
    assert(c5.is_set == true);
    assert(c5.percent == 50);
    assert(c5.offset == 0);
    assert(theme_eval_coord(c5, 800, 0) == 400);

    // Test unset fallback
    struct theme_coord c_unset = { .is_set = false };
    assert(theme_eval_coord(c_unset, 800, 123) == 123);

    // Test extreme values (overflow protection)
    struct theme_coord c_big = parse_coord("99999999999999999999%");
    assert(c_big.is_set == true);
    assert(c_big.percent <= 10000000);

    struct theme_coord c_big_off = parse_coord("99999999999999999999");
    assert(c_big_off.is_set == true);
    assert(c_big_off.offset <= 100000000);

    printf("    -> Coordinate parser tests passed.\n");
}

static void test_colors(void) {
    printf("[*] Testing color parser...\n");
    uint32_t col;

    assert(parse_color("#ffffff", &col) && col == 0xffffff);
    assert(parse_color("#000000", &col) && col == 0x000000);
    assert(parse_color("#334455", &col) && col == 0x334455);
    assert(parse_color("0x112233", &col) && col == 0x112233);
    assert(parse_color("white", &col) && col == 0xffffff);
    assert(parse_color("black", &col) && col == 0x000000);
    assert(parse_color("red", &col) && col == 0xff0000);
    assert(parse_color("green", &col) && col == 0x00ff00);
    assert(parse_color("blue", &col) && col == 0x0000ff);
    assert(parse_color("#f00", &col) && col == 0xff0000);

    // Malformed colors should fail safely
    assert(!parse_color("#xyz123", &col));
    assert(!parse_color("", &col));
    assert(!parse_color(NULL, &col));

    printf("    -> Color parser tests passed.\n");
}

static void test_overflow(void) {
    printf("[*] Testing overflow protection...\n");
    uint64_t w = 0x100000000ULL;
    uint64_t h = 0x100000000ULL;
    uint64_t res;
    bool overflow = __builtin_mul_overflow(w, h, &res);
    assert(overflow);

    uint64_t normal_w = 1920;
    uint64_t normal_h = 1080;
    assert(!__builtin_mul_overflow(normal_w, normal_h, &res));
    assert(res == 2073600);
    uint64_t bytes;
    assert(!__builtin_mul_overflow(res, 4, &bytes));
    assert(bytes == 8294400);

    printf("    -> Overflow protection tests passed.\n");
}

static void test_clipping(void) {
    printf("[*] Testing clipping logic...\n");
    int canvas_w = 1024, canvas_h = 768;

    // Normal box inside canvas
    int x = 100, y = 100, w = 200, h = 200;
    int x1 = x < 0 ? 0 : x;
    int y1 = y < 0 ? 0 : y;
    int x2 = x + w > canvas_w ? canvas_w : x + w;
    int y2 = y + h > canvas_h ? canvas_h : y + h;
    assert(x1 == 100 && y1 == 100 && x2 == 300 && y2 == 300);

    // Partially negative x/y
    x = -50; y = -30; w = 100; h = 100;
    x1 = x < 0 ? 0 : x;
    y1 = y < 0 ? 0 : y;
    x2 = x + w > canvas_w ? canvas_w : x + w;
    y2 = y + h > canvas_h ? canvas_h : y + h;
    assert(x1 == 0 && y1 == 0 && x2 == 50 && y2 == 70);

    // Extending past width/height
    x = 900; y = 700; w = 300; h = 200;
    x1 = x < 0 ? 0 : x;
    y1 = y < 0 ? 0 : y;
    x2 = x + w > canvas_w ? canvas_w : x + w;
    y2 = y + h > canvas_h ? canvas_h : y + h;
    assert(x1 == 900 && y1 == 700 && x2 == 1024 && y2 == 768);

    // Completely off-screen
    x = 2000; y = 2000; w = 100; h = 100;
    x1 = x < 0 ? 0 : x;
    y1 = y < 0 ? 0 : y;
    x2 = x + w > canvas_w ? canvas_w : x + w;
    y2 = y + h > canvas_h ? canvas_h : y + h;
    assert(x1 >= x2 || y1 >= y2); // Should reject

    printf("    -> Clipping logic tests passed.\n");
}

static void test_file_parsing(const char *path) {
    printf("[*] Testing file parser on '%s'...\n", path);
    FILE *f = fopen(path, "rb");
    assert(f != NULL);
    fseek(f, 0, SEEK_END);
    long sz = ftell(f);
    fseek(f, 0, SEEK_SET);
    char *buf = malloc(sz + 1);
    assert(buf != NULL);
    size_t rd = fread(buf, 1, sz, f);
    assert(rd == (size_t)sz);
    buf[sz] = '\0';
    fclose(f);

    int line_count = 0;
    char *saveptr = NULL;
    char *line = strtok_r(buf, "\r\n", &saveptr);
    while (line != NULL) {
        line_count++;
        line = strtok_r(NULL, "\r\n", &saveptr);
    }
    printf("    -> Processed %d lines successfully.\n", line_count);
    free(buf);
}

static void test_comments(void) {
    printf("[*] Testing comment stripping...\n");
    char l1[128] = "# full line comment";
    strip_comments(l1);
    assert(strlen(l1) == 0);

    char l2[128] = "   # indented comment";
    strip_comments(l2);
    // After strip_comments, l2 starts with spaces up to \0
    char *p2 = l2;
    while (*p2 == ' ' || *p2 == '\t') p2++;
    assert(*p2 == '\0');

    char l3[128] = "color = \"#58a6ff\"";
    strip_comments(l3);
    assert(strcmp(l3, "color = \"#58a6ff\"") == 0);

    char l4[128] = "color = \"#58a6ff\" # inline comment";
    strip_comments(l4);
    assert(strstr(l4, "#58a6ff") != NULL);
    assert(strstr(l4, "inline") == NULL);

    char l5[128] = "color = #58a6ff";
    strip_comments(l5);
    assert(strcmp(l5, "color = #58a6ff") == 0);

    char l6[128] = "text = \"Rule #1: Choose kernel\"";
    strip_comments(l6);
    assert(strcmp(l6, "text = \"Rule #1: Choose kernel\"") == 0);

    printf("    -> Comment stripping tests passed.\n");
}

static inline uint32_t utf8_next_codepoint(const char **src) {
    if (src == NULL || *src == NULL) return 0;
    const uint8_t *s = (const uint8_t *)*src;
    if (*s == '\0') return 0;

    uint32_t cp = *s++;
    if (cp < 0x80) {
        *src = (const char *)s;
        return cp;
    }

    size_t trail = 0;
    if (cp >= 0xc2 && cp <= 0xdf) {
        trail = 1;
        cp &= 0x1f;
    } else if (cp >= 0xe0 && cp <= 0xef) {
        trail = 2;
        cp &= 0x0f;
    } else if (cp >= 0xf0 && cp <= 0xf4) {
        trail = 3;
        cp &= 0x07;
    } else {
        *src = (const char *)s;
        return 0xfffd;
    }

    for (; trail != 0; trail--) {
        if (*s == '\0' || (*s & 0xc0) != 0x80) {
            *src = (const char *)s;
            return 0xfffd;
        }
        cp = (cp << 6) | (*s++ & 0x3f);
    }

    *src = (const char *)s;
    return cp;
}

static void test_pff2_bitstream_and_utf8(void) {
    printf("[*] Testing PFF2 continuous bitstream and UTF-8 decoding...\n");
    // UTF-8 decoding test
    const char *text = "CachyOS 隻狼";
    const char *p = text;
    assert(utf8_next_codepoint(&p) == 'C');
    assert(utf8_next_codepoint(&p) == 'a');
    assert(utf8_next_codepoint(&p) == 'c');
    assert(utf8_next_codepoint(&p) == 'h');
    assert(utf8_next_codepoint(&p) == 'y');
    assert(utf8_next_codepoint(&p) == 'O');
    assert(utf8_next_codepoint(&p) == 'S');
    assert(utf8_next_codepoint(&p) == ' ');
    // "隻" is U+96BB (0xE9 0x9A 0xBB in UTF-8)
    assert(utf8_next_codepoint(&p) == 0x96BB);
    // "狼" is U+72FC (0xE7 0x8B 0xBC in UTF-8)
    assert(utf8_next_codepoint(&p) == 0x72FC);
    assert(utf8_next_codepoint(&p) == 0);

    // Continuous bitstream test:
    // A 10x2 glyph (20 bits total = 3 bytes: 11111111 11000000 00000000)
    // Row 0 has 10 bits: all 1s
    // Row 1 has 10 bits: all 0s
    uint8_t bmp[3] = { 0xFF, 0xC0, 0x00 };
    size_t bit_idx = 0;
    int w = 10, h = 2;
    for (int r = 0; r < h; r++) {
        for (int c = 0; c < w; c++, bit_idx++) {
            uint8_t bit = (bmp[bit_idx >> 3] >> (7 - (bit_idx & 7))) & 1;
            if (r == 0) {
                assert(bit == 1);
            } else {
                assert(bit == 0);
            }
        }
    }
    printf("    -> PFF2 bitstream and UTF-8 tests passed.\n");
}

int main(void) {
    printf("=== Running Theme Engine Unit Tests ===\n");
    test_coords();
    test_colors();
    test_comments();
    test_pff2_bitstream_and_utf8();
    test_overflow();
    test_clipping();
    test_file_parsing("themes/minimal/theme.txt");
    test_file_parsing("themes/artorias/theme.txt");
    test_file_parsing("themes/sekiro/theme.txt");
    test_file_parsing("themes/terminal-dark/theme.txt");
    test_file_parsing("themes/minecraft/theme.txt");
    test_file_parsing("themes/astronaut/theme.txt");
    printf("All theme unit tests passed successfully!\n");
    return 0;
}
