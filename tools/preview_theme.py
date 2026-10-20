#!/usr/bin/env python3
"""
Limine Theme Preview Generator (Milestone 2)
Renders an exact pixel simulation of a Limine theme with:
- Multi-frame Animated GIF backgrounds
- PFF2 (.pf2) fonts
- 3-slice and 9-slice pixmap boxes (item_pixmap_style, selected_item_pixmap_style)
- Per-entry icon discovery and rendering
- Decorative `+ image` widgets
"""

import sys
import os
import re
import struct
from PIL import Image, ImageDraw

def parse_coord(coord_str, container_size, default_val=0):
    if not coord_str:
        return default_val
    coord_str = coord_str.strip()
    m = re.match(r'^([+-]?\d+)\s*%(?:\s*([+-]\s*\d+))?$', coord_str)
    if m:
        pct = int(m.group(1))
        offset = int(m.group(2).replace(' ', '')) if m.group(2) else 0
        return int(container_size * pct / 100) + offset
    m_num = re.match(r'^[+-]?\d+$', coord_str)
    if m_num:
        return int(coord_str)
    return default_val

def strip_theme_comments(line):
    out = []
    in_quote = False
    quote_char = None
    i = 0
    while i < len(line):
        ch = line[i]
        if not in_quote:
            if ch in ('"', "'"):
                in_quote = True
                quote_char = ch
                out.append(ch)
            elif ch == '#':
                rest = line[i+1:]
                m = re.match(r'^[0-9a-fA-F]{3,8}(?:\s|$)', rest)
                if m and any(sep in ''.join(out) for sep in ('=', ':')):
                    out.append(ch)
                else:
                    break
            elif ch == '/' and i + 1 < len(line) and line[i+1] == '/':
                break
            else:
                out.append(ch)
        else:
            out.append(ch)
            if ch == quote_char:
                in_quote = False
        i += 1
    return ''.join(out).strip()

def parse_color(color_str, default_color=(255, 255, 255)):
    if not color_str:
        return default_color
    color_str = color_str.strip().lower()
    named = {
        'black': (0, 0, 0),
        'white': (255, 255, 255),
        'gray': (128, 128, 128),
        'grey': (128, 128, 128),
        'red': (255, 0, 0),
        'green': (0, 255, 0),
        'blue': (0, 0, 255),
        'yellow': (255, 255, 0),
        'cyan': (0, 255, 255),
        'magenta': (255, 0, 255),
    }
    if color_str in named:
        return named[color_str]
    if color_str.startswith('#'):
        hex_val = color_str[1:]
    elif color_str.startswith('0x'):
        hex_val = color_str[2:]
    else:
        hex_val = color_str

    if len(hex_val) == 6:
        r = int(hex_val[0:2], 16)
        g = int(hex_val[2:4], 16)
        b = int(hex_val[4:6], 16)
        return (r, g, b)
    elif len(hex_val) == 3:
        r = int(hex_val[0]*2, 16)
        g = int(hex_val[1]*2, 16)
        b = int(hex_val[2]*2, 16)
        return (r, g, b)
    return default_color

def load_builtin_font():
    font_path = os.path.join(os.path.dirname(__file__), '..', 'Limine', 'common', 'lib', 'gterm.c')
    if not os.path.exists(font_path):
        return None
    with open(font_path, 'r', errors='ignore') as f:
        content = f.read()
    m = re.search(r'uint8_t\s+builtin_font\[4096\]\s*=\s*\{([^}]+)\};', content, re.DOTALL)
    if not m:
        return None
    hex_vals = re.findall(r'0x[0-9a-fA-F]+|\b\d+\b', m.group(1))
    return bytes(int(x, 0) for x in hex_vals)

def draw_builtin_string(draw, font_bytes, text, x, y, color, scale=1):
    if not font_bytes or not text:
        return
    cur_x = x
    for ch in text:
        code = ord(ch) if ord(ch) < 256 else ord('?')
        glyph = font_bytes[code * 16 : (code + 1) * 16]
        for row in range(16):
            b = glyph[row]
            for col in range(8):
                if (b >> (7 - col)) & 1:
                    px = cur_x + col * scale
                    py = y + row * scale
                    if scale == 1:
                        draw.point((px, py), fill=color)
                    else:
                        draw.rectangle([px, py, px + scale - 1, py + scale - 1], fill=color)
        cur_x += 8 * scale

class PFF2Font:
    def __init__(self, path):
        with open(path, 'rb') as f:
            self.data = f.read()
        self.glyphs = {}
        self.ascent = 16
        self.descent = 0
        self.point_size = 16
        self._parse()

    def _parse(self):
        pos = 0
        while pos + 8 <= len(self.data):
            sec_name = self.data[pos:pos+4].decode('latin1', errors='replace')
            sec_len = struct.unpack('>I', self.data[pos+4:pos+8])[0]
            pos += 8
            if sec_name == 'PTSZ' and sec_len >= 2:
                self.point_size = struct.unpack('>H', self.data[pos:pos+2])[0]
            elif sec_name == 'ASCE' and sec_len >= 2:
                self.ascent = struct.unpack('>h', self.data[pos:pos+2])[0]
            elif sec_name == 'DESC' and sec_len >= 2:
                self.descent = struct.unpack('>h', self.data[pos:pos+2])[0]
            elif sec_name == 'CHIX':
                num = sec_len // 9
                for i in range(num):
                    ep = pos + i * 9
                    code, flags, offset = struct.unpack('>IBI', self.data[ep:ep+9])
                    self.glyphs[code] = offset
            elif sec_name == 'DATA':
                break
            pos += sec_len

    def get_glyph(self, cp):
        offset = self.glyphs.get(cp)
        if offset is None or offset + 10 > len(self.data):
            return None
        w, h, xoff, yoff, dwidth = struct.unpack('>HHhhh', self.data[offset:offset+10])
        total_bits = w * h
        total_bytes = (total_bits + 7) // 8
        bmp = self.data[offset+10 : offset+10 + total_bytes]
        return { 'w': w, 'h': h, 'xoff': xoff, 'yoff': yoff, 'dwidth': dwidth, 'bmp': bmp }

    def string_width(self, text):
        total = 0
        for ch in text:
            g = self.get_glyph(ord(ch))
            if g:
                total += g['dwidth']
            else:
                total += self.point_size // 2
        return total

    def draw_string(self, draw, text, x, y, color):
        cur_x = x
        for ch in text:
            g = self.get_glyph(ord(ch))
            if not g:
                cur_x += self.point_size // 2
                continue
            gx = cur_x + g['xoff']
            gy = y + self.ascent - g['yoff'] - g['h']
            bit_index = 0
            for r in range(g['h']):
                for c in range(g['w']):
                    bit = (g['bmp'][bit_index >> 3] >> (7 - (bit_index & 7))) & 1
                    bit_index += 1
                    if bit:
                        draw.point((gx + c, gy + r), fill=color)
            cur_x += g['dwidth']

class PixmapBox:
    def __init__(self, theme_dir, pattern):
        self.loaded = False
        self.is_3slice = False
        self.is_single = False
        self.slices = {}
        if not pattern:
            return

        def load_img(slice_name):
            if '*' in pattern:
                sub = pattern.replace('*', slice_name)
            else:
                sub = pattern
            p = os.path.join(theme_dir, sub)
            if os.path.exists(p):
                return Image.open(p).convert('RGBA')
            return None

        if '*' not in pattern:
            img = load_img('')
            if img:
                self.slices['c'] = img
                self.is_single = True
                self.loaded = True
            return

        nw = load_img('nw')
        if nw:
            self.slices['nw'] = nw
            for k in ('n', 'ne', 'w', 'c', 'e', 'sw', 's', 'se'):
                img = load_img(k)
                if img: self.slices[k] = img
            self.loaded = True
            self.is_3slice = False
            return

        w = load_img('w')
        c = load_img('c')
        e = load_img('e')
        if w or c or e:
            if w: self.slices['w'] = w
            if c: self.slices['c'] = c
            if e: self.slices['e'] = e
            self.loaded = True
            self.is_3slice = True

    def draw(self, canvas, x, y, w, h):
        if not self.loaded or w <= 0 or h <= 0:
            return
        if self.is_single and 'c' in self.slices:
            s = self.slices['c'].resize((w, h), Image.Resampling.LANCZOS)
            canvas.paste(s, (x, y), s)
            return

        if self.is_3slice:
            lw = self.slices['w'].width if 'w' in self.slices else 0
            rw = self.slices['e'].width if 'e' in self.slices else 0
            if lw + rw > w:
                lw = w // 2
                rw = w - lw
            cw = w - lw - rw
            if 'w' in self.slices and lw > 0:
                s = self.slices['w'].resize((lw, h), Image.Resampling.LANCZOS)
                canvas.paste(s, (x, y), s)
            if 'c' in self.slices and cw > 0:
                s = self.slices['c'].resize((cw, h), Image.Resampling.LANCZOS)
                canvas.paste(s, (x + lw, y), s)
            if 'e' in self.slices and rw > 0:
                s = self.slices['e'].resize((rw, h), Image.Resampling.LANCZOS)
                canvas.paste(s, (x + lw + cw, y), s)
            return

        # 9-slice
        nw_w = self.slices['nw'].width if 'nw' in self.slices else 0
        nw_h = self.slices['nw'].height if 'nw' in self.slices else 0
        ne_w = self.slices['ne'].width if 'ne' in self.slices else 0
        ne_h = self.slices['ne'].height if 'ne' in self.slices else 0
        sw_w = self.slices['sw'].width if 'sw' in self.slices else 0
        sw_h = self.slices['sw'].height if 'sw' in self.slices else 0
        se_w = self.slices['se'].width if 'se' in self.slices else 0
        se_h = self.slices['se'].height if 'se' in self.slices else 0

        lw = max(nw_w, sw_w)
        rw = max(ne_w, se_w)
        th = max(nw_h, ne_h)
        bh = max(sw_h, se_h)
        if lw + rw > w: lw = w // 2; rw = w - lw
        if th + bh > h: th = h // 2; bh = h - th
        cw = w - lw - rw
        ch = h - th - bh

        if 'nw' in self.slices:
            s = self.slices['nw'].resize((lw, th))
            canvas.paste(s, (x, y), s)
        if 'ne' in self.slices:
            s = self.slices['ne'].resize((rw, th))
            canvas.paste(s, (x + w - rw, y), s)
        if 'sw' in self.slices:
            s = self.slices['sw'].resize((lw, bh))
            canvas.paste(s, (x, y + h - bh), s)
        if 'se' in self.slices:
            s = self.slices['se'].resize((rw, bh))
            canvas.paste(s, (x + w - rw, y + h - bh), s)

        if 'n' in self.slices and cw > 0:
            s = self.slices['n'].resize((cw, th))
            canvas.paste(s, (x + lw, y), s)
        if 's' in self.slices and cw > 0:
            s = self.slices['s'].resize((cw, bh))
            canvas.paste(s, (x + lw, y + h - bh), s)
        if 'w' in self.slices and ch > 0:
            s = self.slices['w'].resize((lw, ch))
            canvas.paste(s, (x, y + th), s)
        if 'e' in self.slices and ch > 0:
            s = self.slices['e'].resize((rw, ch))
            canvas.paste(s, (x + w - rw, y + th), s)

        if 'c' in self.slices and cw > 0 and ch > 0:
            s = self.slices['c'].resize((cw, ch))
            canvas.paste(s, (x + lw, y + th), s)

def find_icon(theme_dir, entry_name):
    clean = re.sub(r'[^a-zA-Z0-9_\-\s]', ' ', entry_name).lower()
    tokens = clean.split()
    for t in tokens:
        for loc in (os.path.join(theme_dir, 'icons', f"{t}.png"), os.path.join(theme_dir, f"{t}.png")):
            if os.path.exists(loc):
                return Image.open(loc).convert('RGBA')
    for fb in ('linux', 'gnu-linux', 'efi', 'os', 'unknown'):
        loc = os.path.join(theme_dir, 'icons', f"{fb}.png")
        if os.path.exists(loc):
            return Image.open(loc).convert('RGBA')
    return None

def resolve_font(theme_dir, font_name):
    if not font_name:
        return None
    for p in (os.path.join(theme_dir, font_name),
              os.path.join(theme_dir, f"{font_name}.pf2"),
              os.path.join(theme_dir, f"{font_name.replace(' ', '')}.pf2")):
        if os.path.exists(p):
            try:
                return PFF2Font(p)
            except Exception:
                pass
    return None

def render_preview(theme_file, output_image, width=1920, height=1080):
    theme_dir = os.path.dirname(os.path.abspath(theme_file))
    font_bytes = load_builtin_font()

    # Defaults
    desktop_image = None
    desktop_color = (26, 18, 53)
    title_text = "System Boot"
    title_color = (253, 222, 39)
    title_font_name = None

    menu_left = "8%"
    menu_top = "28%"
    menu_width = "38%"
    menu_height = "46%"
    item_color = (246, 224, 180)
    selected_item_color = (53, 5, 129)
    selected_item_bg_color = (255, 179, 67)
    item_height = 36
    item_spacing = 8
    item_padding = 12
    item_font_name = None
    selected_item_font_name = None
    item_pixmap_style = None
    selected_item_pixmap_style = None
    icon_width = 32
    icon_height = 32
    item_icon_space = 10

    timeout_left = "8%"
    timeout_top = "78%"
    timeout_width = "40%"
    timeout_text = "Booting automatically in %d seconds..."
    timeout_color = (255, 179, 67)
    timeout_font_name = None

    decorative_images = []
    current_img_widget = None

    labels = []
    current_label_widget = None

    # Parse theme file
    current_section = 'global'
    with open(theme_file, 'r', encoding='utf-8', errors='ignore') as f:
        for raw_line in f:
            line = strip_theme_comments(raw_line)
            if not line:
                continue

            if line == '}':
                current_section = 'global'
                current_img_widget = None
                current_label_widget = None
                continue
            if line.startswith('+'):
                block = line[1:].replace('{', '').strip().lower()
                current_section = block
                if block == 'image':
                    current_img_widget = {}
                    decorative_images.append(current_img_widget)
                elif block == 'label':
                    current_label_widget = {
                        'id': None,
                        'text': '',
                        'color': (255, 179, 67),
                        'align': 'left',
                        'font': None,
                        'left': '8%',
                        'top': '78%',
                        'width': '50%',
                        'height': '24'
                    }
                    labels.append(current_label_widget)
                continue

            sep = '=' if '=' in line else (':' if ':' in line else None)
            if not sep:
                continue
            key, val = [p.strip() for p in line.split(sep, 1)]
            val = val.strip(' "\'')
            key_l = key.lower().replace('-', '_')

            if current_section == 'global':
                if key_l in ('desktop_image',): desktop_image = val
                elif key_l in ('desktop_color',): desktop_color = parse_color(val, desktop_color)
                elif key_l in ('title_text',): title_text = val
                elif key_l in ('title_color',): title_color = parse_color(val, title_color)
                elif key_l in ('title_font',): title_font_name = val

            elif current_section in ('boot_menu',):
                if key_l == 'left': menu_left = val
                elif key_l == 'top': menu_top = val
                elif key_l == 'width': menu_width = val
                elif key_l == 'height': menu_height = val
                elif key_l == 'item_color': item_color = parse_color(val, item_color)
                elif key_l == 'selected_item_color': selected_item_color = parse_color(val, selected_item_color)
                elif key_l == 'selected_item_bg_color': selected_item_bg_color = parse_color(val, selected_item_bg_color)
                elif key_l == 'item_height': item_height = int(val)
                elif key_l == 'item_spacing': item_spacing = int(val)
                elif key_l == 'item_padding': item_padding = int(val)
                elif key_l == 'item_font': item_font_name = val
                elif key_l == 'selected_item_font': selected_item_font_name = val
                elif key_l == 'item_pixmap_style': item_pixmap_style = val
                elif key_l == 'selected_item_pixmap_style': selected_item_pixmap_style = val
                elif key_l == 'icon_width': icon_width = int(val)
                elif key_l == 'icon_height': icon_height = int(val)
                elif key_l == 'item_icon_space': item_icon_space = int(val)

            elif current_section in ('label',):
                if current_label_widget is not None:
                    if key_l == 'id': current_label_widget['id'] = val
                    elif key_l == 'text': current_label_widget['text'] = val
                    elif key_l == 'color': current_label_widget['color'] = parse_color(val, current_label_widget['color'])
                    elif key_l == 'font': current_label_widget['font'] = val
                    elif key_l == 'align': current_label_widget['align'] = val.lower()
                    elif key_l == 'left': current_label_widget['left'] = val
                    elif key_l == 'top': current_label_widget['top'] = val
                    elif key_l == 'width': current_label_widget['width'] = val
                    elif key_l == 'height': current_label_widget['height'] = val
                if key_l == 'left': timeout_left = val
                elif key_l == 'top': timeout_top = val
                elif key_l == 'width': timeout_width = val
                elif key_l == 'text': timeout_text = val
                elif key_l == 'color': timeout_color = parse_color(val, timeout_color)
                elif key_l == 'font': timeout_font_name = val

            elif current_section in ('image',):
                if current_img_widget is not None:
                    if key_l in ('file', 'file_path'): current_img_widget['file'] = val
                    elif key_l == 'left': current_img_widget['left'] = val
                    elif key_l == 'top': current_img_widget['top'] = val
                    elif key_l == 'width': current_img_widget['width'] = val
                    elif key_l == 'height': current_img_widget['height'] = val

    # Load resources
    title_font = resolve_font(theme_dir, title_font_name)
    item_font = resolve_font(theme_dir, item_font_name)
    selected_item_font = resolve_font(theme_dir, selected_item_font_name) or item_font
    timeout_font = resolve_font(theme_dir, timeout_font_name)

    item_box = PixmapBox(theme_dir, item_pixmap_style)
    selected_item_box = PixmapBox(theme_dir, selected_item_pixmap_style)

    # Layout evaluation
    m_left = parse_coord(menu_left, width, int(width * 0.1))
    m_top = parse_coord(menu_top, height, int(height * 0.3))
    m_width = parse_coord(menu_width, width, int(width * 0.4))
    m_height = parse_coord(menu_height, height, int(height * 0.4))
    t_left = parse_coord(timeout_left, width, m_left)
    t_top = parse_coord(timeout_top, height, int(height * 0.78))

    # Discover entries from accompanying limine.conf if present
    entries = []
    conf_path = os.path.join(theme_dir, "limine.conf")
    if os.path.exists(conf_path):
        with open(conf_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                sline = line.strip()
                if sline.startswith('/') and not sline.startswith('//'):
                    name = sline.lstrip('/')
                    if name and not any(name.lower().startswith(x) for x in ['protocol:', 'path:', 'module_path:', 'cmdline:', 'comment:']):
                        entries.append(name)
                elif sline.startswith('//'):
                    name = sline.lstrip('/')
                    if name and not any(name.lower().startswith(x) for x in ['protocol:', 'path:', 'module_path:', 'cmdline:', 'comment:']):
                        entries.append("[+] " + name)

    if not entries:
        entries = [
            "CachyOS Linux (x86_64, Linux 6.13)",
            "CachyOS Linux (fallback initramfs)",
            "UEFI Firmware Settings"
        ]
    selected_idx = 0

    def render_overlay(frame_img, remaining_seconds=5):
        canvas = frame_img.convert('RGBA')
        draw = ImageDraw.Draw(canvas)

        # 1. Decorative images
        for iw in decorative_images:
            f = iw.get('file')
            if not f: continue
            ip = os.path.join(theme_dir, f)
            if os.path.exists(ip):
                im = Image.open(ip).convert('RGBA')
                wx = parse_coord(iw.get('left'), width, 0)
                wy = parse_coord(iw.get('top'), height, 0)
                ww = parse_coord(iw.get('width'), width, im.width)
                wh = parse_coord(iw.get('height'), height, im.height)
                sim = im.resize((ww, wh), Image.Resampling.LANCZOS)
                canvas.paste(sim, (wx, wy), sim)

        # 2. Header title
        if title_text:
            if title_font:
                tw = title_font.string_width(title_text)
                tx = (width - tw) // 2
                title_font.draw_string(draw, title_text, tx, 40, title_color)
            else:
                title_y = m_top - 50 if m_top > 60 else 30
                draw_builtin_string(draw, font_bytes, title_text, m_left, title_y, title_color, scale=2)

        # 3. Boot entries
        cur_y = m_top
        for i, entry in enumerate(entries):
            is_sel = (i == selected_idx)
            if is_sel:
                if selected_item_box.loaded:
                    selected_item_box.draw(canvas, m_left, cur_y, m_width, item_height)
                else:
                    draw.rectangle([m_left, cur_y, m_left + m_width, cur_y + item_height], fill=selected_item_bg_color)
                fg = selected_item_color
                f_obj = selected_item_font
            else:
                if item_box.loaded:
                    item_box.draw(canvas, m_left, cur_y, m_width, item_height)
                fg = item_color
                f_obj = item_font

            text_x = m_left + item_padding
            icon = find_icon(theme_dir, entry)
            if icon:
                s_icon = icon.resize((icon_width, icon_height), Image.Resampling.LANCZOS)
                iy = cur_y + (item_height - icon_height) // 2
                canvas.paste(s_icon, (text_x, iy), s_icon)
                text_x += icon_width + item_icon_space

            if f_obj:
                text_y = cur_y + (item_height - f_obj.point_size) // 2
                f_obj.draw_string(draw, entry, text_x, text_y, fg)
            else:
                text_y = cur_y + (item_height - 16) // 2
                draw_builtin_string(draw, font_bytes, entry, text_x, text_y, fg, scale=1)

            cur_y += item_height + item_spacing

        # 4. Labels (countdown, headers, subtitles, hints)
        if labels:
            for lbl in labels:
                l_id = lbl.get('id')
                l_text = lbl.get('text', '')
                if l_id == '__timeout__':
                    if remaining_seconds <= 0:
                        continue
                    l_text = l_text.replace('%d', str(remaining_seconds))

                l_left = parse_coord(lbl.get('left', '10%'), width, int(width * 0.1))
                l_top = parse_coord(lbl.get('top', '80%'), height, int(height * 0.8))
                l_width = parse_coord(lbl.get('width', '80%'), width, int(width * 0.8))
                l_font = resolve_font(theme_dir, lbl.get('font'))
                l_color = lbl.get('color', (170, 170, 170))
                l_align = lbl.get('align', 'center')

                if l_font:
                    t_w = l_font.string_width(l_text)
                    if l_align == 'center':
                        l_x = l_left + (l_width - t_w) // 2
                    elif l_align == 'right':
                        l_x = l_left + l_width - t_w
                    else:
                        l_x = l_left
                    l_font.draw_string(draw, l_text, l_x, l_top, l_color)
                else:
                    t_w = len(l_text) * 8
                    if l_align == 'center':
                        l_x = l_left + (l_width - t_w) // 2
                    elif l_align == 'right':
                        l_x = l_left + l_width - t_w
                    else:
                        l_x = l_left
                    draw_builtin_string(draw, font_bytes, l_text, l_x, l_top, l_color, scale=1)
        else:
            # 4. Default Timeout label
            t_text = timeout_text.replace('%d', str(remaining_seconds))
            if timeout_font:
                timeout_font.draw_string(draw, t_text, t_left, t_top, timeout_color)
            else:
                draw_builtin_string(draw, font_bytes, t_text, t_left, t_top, timeout_color, scale=1)

            # 5. Default Navigation hint
            hint = "Use ARROWS to select, ENTER to boot, 'E' to edit"
            draw_builtin_string(draw, font_bytes, hint, m_left, t_top + 32, (180, 180, 200), scale=1)

        return canvas.convert('RGB')

    img_path = os.path.join(theme_dir, desktop_image) if desktop_image else None
    if img_path and os.path.exists(img_path):
        src_img = Image.open(img_path)
        n_frames = getattr(src_img, 'n_frames', 1)

        if output_image.endswith('.gif') and n_frames > 1:
            print(f"[*] Rendering {n_frames} animated frames with Milestone 2 elements...")
            frames = []
            durations = []
            for frame_idx in range(n_frames):
                src_img.seek(frame_idx)
                frame = src_img.convert('RGB').resize((width, height), Image.Resampling.LANCZOS)
                dur = src_img.info.get('duration', 80)
                durations.append(dur if dur > 10 else 80)
                countdown = max(1, 5 - int(frame_idx / (n_frames / 4)))
                frames.append(render_overlay(frame, countdown))

            frames[0].save(
                output_image,
                save_all=True,
                append_images=frames[1:],
                duration=durations,
                loop=0,
                optimize=True
            )
            print(f"[+] Animated preview generated: {output_image}")
            return
        else:
            bg = src_img.convert('RGB').resize((width, height), Image.Resampling.LANCZOS)
    else:
        bg = Image.new('RGB', (width, height), color=desktop_color)

    final_img = render_overlay(bg, 5)
    final_img.save(output_image)
    print(f"[+] Preview generated: {output_image}")

if __name__ == '__main__':
    theme_file = sys.argv[1] if len(sys.argv) > 1 else 'themed-limine/theme.txt'
    output_file = sys.argv[2] if len(sys.argv) > 2 else 'themed-limine/preview.png'
    render_preview(theme_file, output_file)
