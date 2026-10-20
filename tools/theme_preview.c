// Standalone preview renderer for Limine graphical themes
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <stdbool.h>
#include <string.h>

#define STB_IMAGE_IMPLEMENTATION
#include "../Limine/common/lib/stb_image.h"

// Builtin font from Limine (8x16 CP437 font)
static const uint8_t builtin_font[] = {
#include "font_data.inc"
};

struct theme_coord {
    int percent;
    int offset;
    bool is_set;
};

struct theme_canvas {
    uint32_t *pixels;
    int width;
    int height;
};

static struct theme_coord parse_coord(const char *str) {
    struct theme_coord coord = { .percent = 0, .offset = 0, .is_set = false };
    if (!str) return coord;
    while (*str == ' ' || *str == '\t') str++;
    if (*str == '\0') return coord;

    const char *pct = strchr(str, '%');
    if (pct) {
        int val = 0, sign = 1;
        const char *p = str;
        if (*p == '-') { sign = -1; p++; } else if (*p == '+') p++;
        while (p < pct) {
            if (*p >= '0' && *p <= '9') val = val * 10 + (*p - '0');
            p++;
        }
        coord.percent = val * sign;
        coord.is_set = true;

        p = pct + 1;
        while (*p == ' ' || *p == '\t') p++;
        if (*p == '+' || *p == '-') {
            int off_sign = (*p == '-') ? -1 : 1;
            p++;
            while (*p == ' ' || *p == '\t') p++;
            int off = 0;
            while (*p >= '0' && *p <= '9') {
                off = off * 10 + (*p - '0');
                p++;
            }
            coord.offset = off * off_sign;
        }
    } else {
        int off = 0, sign = 1;
        const char *p = str;
        if (*p == '-') { sign = -1; p++; } else if (*p == '+') p++;
        while (*p >= '0' && *p <= '9') {
            off = off * 10 + (*p - '0');
            p++;
        }
        coord.offset = off * sign;
        coord.is_set = true;
    }
    return coord;
}

static int eval_coord(struct theme_coord c, int container, int def) {
    if (!c.is_set) return def;
    return (int)((int64_t)container * c.percent / 100 + c.offset);
}

static bool parse_color(const char *str, uint32_t *col) {
    if (!str) return false;
    while (*str == ' ' || *str == '\t') str++;

    if (strcasecmp(str, "black") == 0) { *col = 0x000000; return true; }
    if (strcasecmp(str, "white") == 0) { *col = 0xffffff; return true; }
    if (strcasecmp(str, "gray") == 0) { *col = 0x808080; return true; }
    if (strcasecmp(str, "red") == 0) { *col = 0xff0000; return true; }
    if (strcasecmp(str, "green") == 0) { *col = 0x00ff00; return true; }
    if (strcasecmp(str, "blue") == 0) { *col = 0x0000ff; return true; }
    if (strcasecmp(str, "yellow") == 0) { *col = 0xffff00; return true; }

    if (*str == '#') str++;
    else if (str[0] == '0' && (str[1] == 'x' || str[1] == 'X')) str += 2;

    if (strlen(str) == 6) {
        unsigned int val = 0;
        if (sscanf(str, "%x", &val) == 1) {
            *col = val;
            return true;
        }
    }
    return false;
}

static void draw_rect(struct theme_canvas *canvas, int x, int y, int w, int h, uint32_t color) {
    int x1 = x < 0 ? 0 : x;
    int y1 = y < 0 ? 0 : y;
    int x2 = x + w > canvas->width ? canvas->width : x + w;
    int y2 = y + h > canvas->height ? canvas->height : y + h;
    if (x1 >= x2 || y1 >= y2) return;

    for (int cy = y1; cy < y2; cy++) {
        uint32_t *row = &canvas->pixels[cy * canvas->width];
        for (int cx = x1; cx < x2; cx++) {
            row[cx] = color;
        }
    }
}

static void draw_char(struct theme_canvas *canvas, char c, int x, int y, uint32_t fg, size_t scale) {
    uint8_t uc = (uint8_t)c;
    const uint8_t *glyph = &builtin_font[uc * 16];

    for (size_t row = 0; row < 16; row++) {
        uint8_t bits = glyph[row];
        for (size_t col = 0; col < 8; col++) {
            if (bits & (0x80 >> col)) {
                int px = x + (int)(col * scale);
                int py = y + (int)(row * scale);
                if (scale == 1) {
                    if (px >= 0 && px < canvas->width && py >= 0 && py < canvas->height) {
                        canvas->pixels[py * canvas->width + px] = fg;
                    }
                } else {
                    draw_rect(canvas, px, py, (int)scale, (int)scale, fg);
                }
            }
        }
    }
}

static void draw_string(struct theme_canvas *canvas, const char *str, int x, int y, uint32_t fg, size_t scale) {
    if (!str) return;
    int cur_x = x;
    while (*str) {
        if (*str == '\n') {
            y += (int)(16 * scale);
            cur_x = x;
        } else {
            draw_char(canvas, *str, cur_x, y, fg, scale);
            cur_x += (int)(8 * scale);
        }
        str++;
    }
}

static int string_width(const char *str, size_t scale) {
    if (!str) return 0;
    return (int)(strlen(str) * 8 * scale);
}

static void draw_image_stretched(struct theme_canvas *canvas, uint32_t *img, int img_w, int img_h) {
    if (!img) return;
    uint64_t x_step = ((uint64_t)img_w << 32) / (uint64_t)canvas->width;
    uint64_t y_step = ((uint64_t)img_h << 32) / (uint64_t)canvas->height;

    for (int y = 0; y < canvas->height; y++) {
        size_t sy = (size_t)(((uint64_t)y * y_step) >> 32);
        if (sy >= (size_t)img_h) sy = img_h - 1;
        const uint32_t *src_row = &img[sy * img_w];
        uint32_t *dst_row = &canvas->pixels[y * canvas->width];

        for (int x = 0; x < canvas->width; x++) {
            size_t sx = (size_t)(((uint64_t)x * x_step) >> 32);
            if (sx >= (size_t)img_w) sx = img_w - 1;
            dst_row[x] = src_row[sx] & 0x00ffffff;
        }
    }
}

static void write_bmp(const char *filename, uint32_t *pixels, int w, int h) {
    FILE *f = fopen(filename, "wb");
    if (!f) return;

    uint32_t row_size = w * 3;
    uint32_t padding = (4 - (row_size % 4)) % 4;
    uint32_t image_size = (row_size + padding) * h;
    uint32_t file_size = 54 + image_size;

    uint8_t header[54] = {
        'B', 'M',
        file_size & 0xff, (file_size >> 8) & 0xff, (file_size >> 16) & 0xff, (file_size >> 24) & 0xff,
        0, 0, 0, 0,
        54, 0, 0, 0,
        40, 0, 0, 0,
        w & 0xff, (w >> 8) & 0xff, (w >> 16) & 0xff, (w >> 24) & 0xff,
        h & 0xff, (h >> 8) & 0xff, (h >> 16) & 0xff, (h >> 24) & 0xff,
        1, 0,
        24, 0,
        0, 0, 0, 0,
        image_size & 0xff, (image_size >> 8) & 0xff, (image_size >> 16) & 0xff, (image_size >> 24) & 0xff,
        0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
    };
    fwrite(header, 1, 54, f);

    uint8_t pad_bytes[3] = {0, 0, 0};
    for (int y = h - 1; y >= 0; y--) {
        const uint32_t *row = &pixels[y * w];
        for (int x = 0; x < w; x++) {
            uint32_t px = row[x];
            uint8_t b = px & 0xff;
            uint8_t g = (px >> 8) & 0xff;
            uint8_t r = (px >> 16) & 0xff;
            fputc(b, f);
            fputc(g, f);
            fputc(r, f);
        }
        if (padding > 0) {
            fwrite(pad_bytes, 1, padding, f);
        }
    }
    fclose(f);
}

int main(int argc, char **argv) {
    const char *theme_file = (argc > 1) ? argv[1] : "themed-limine/theme.txt";
    const char *out_file = (argc > 2) ? argv[2] : "themed-limine/preview.bmp";

    printf("[*] Generating preview for '%s'...\n", theme_file);

    int canvas_w = 1920, canvas_h = 1080;
    uint32_t *pixels = calloc(canvas_w * canvas_h, sizeof(uint32_t));
    if (!pixels) {
        fprintf(stderr, "Out of memory\n");
        return 1;
    }
    struct theme_canvas canvas = { .pixels = pixels, .width = canvas_w, .height = canvas_h };

    // Default theme settings
    uint32_t desktop_color = 0x1a1235;
    char desktop_image[256] = "themed-limine/background.png";
    char title_text[256] = "System Boot";
    uint32_t title_color = 0xfdde27;

    struct theme_coord menu_left = { .percent = 8, .offset = 0, .is_set = true };
    struct theme_coord menu_top = { .percent = 28, .offset = 0, .is_set = true };
    struct theme_coord menu_width = { .percent = 38, .offset = 0, .is_set = true };
    struct theme_coord menu_height = { .percent = 46, .offset = 0, .is_set = true };

    uint32_t item_color = 0xf6e0b4;
    uint32_t sel_color = 0x350581;
    uint32_t sel_bg = 0xffb343;
    int item_height = 32;
    int item_spacing = 8;
    int item_padding = 12;

    struct theme_coord timeout_left = { .percent = 8, .offset = 0, .is_set = true };
    struct theme_coord timeout_top = { .percent = 78, .offset = 0, .is_set = true };
    uint32_t timeout_color = 0xffb343;

    // Load background image
    int img_w = 0, img_h = 0, channels = 0;
    uint32_t *bg_data = (uint32_t *)stbi_load(desktop_image, &img_w, &img_h, &channels, 4);
    if (bg_data) {
        printf("[+] Loaded background: %s (%dx%d)\n", desktop_image, img_w, img_h);
        draw_image_stretched(&canvas, bg_data, img_w, img_h);
        stbi_image_free(bg_data);
    } else {
        printf("[-] Could not load background image, using desktop-color\n");
        draw_rect(&canvas, 0, 0, canvas_w, canvas_h, desktop_color);
    }

    // Title
    int tw = string_width(title_text, 2);
    int mx = eval_coord(menu_left, canvas_w, 100);
    draw_string(&canvas, title_text, mx, 160, title_color, 2);

    // Boot Menu Entries
    const char *entries[] = {
        "CachyOS Linux (x86_64, Linux 6.13)",
        "CachyOS Linux (fallback initramfs)",
        "UEFI Firmware Settings"
    };
    int num_entries = 3;
    int selected = 0;

    int my = eval_coord(menu_top, canvas_h, 300);
    int mw = eval_coord(menu_width, canvas_w, 600);

    for (int i = 0; i < num_entries; i++) {
        int iy = my + i * (item_height + item_spacing);
        bool is_sel = (i == selected);

        if (is_sel) {
            draw_rect(&canvas, mx, iy, mw, item_height, sel_bg);
        }

        uint32_t fg = is_sel ? sel_color : item_color;
        int tx = mx + item_padding;
        int ty = iy + (item_height - 16) / 2;
        draw_string(&canvas, entries[i], tx, ty, fg, 1);
    }

    // Timeout countdown
    int tox = eval_coord(timeout_left, canvas_w, 100);
    int toy = eval_coord(timeout_top, canvas_h, 800);
    draw_string(&canvas, "Booting automatically in 5 seconds...", tox, toy, timeout_color, 1);

    // Key hints
    draw_string(&canvas, "Use ARROWS to select, ENTER to boot, 'E' to edit", mx, toy + 30, 0x8888aa, 1);

    write_bmp(out_file, canvas.pixels, canvas_w, canvas_h);
    printf("[+] Wrote preview to %s\n", out_file);

    free(pixels);
    return 0;
}
