#!/usr/bin/env python3
"""
Limine Theme System Test & Validation Suite
Tests:
1. Syntax and property parsing on all packaged themes
2. Handling of missing assets (images, fonts, box slices)
3. Handling of malformed configurations and unknown properties
4. Layout calculation at diverse resolutions (4K down to 640x480)
5. Coordinate parser edge cases
"""

import os
import sys
import tempfile
from PIL import Image
from preview_theme import render_preview, parse_coord, parse_color, strip_theme_comments

def test_coordinate_parsing():
    print("[*] Testing coordinate parser...")
    assert parse_coord("50%", 1000) == 500
    assert parse_coord("50%-100", 1000) == 400
    assert parse_coord("25%+50", 1000) == 300
    assert parse_coord("100%", 1920) == 1920
    assert parse_coord("0%", 1080) == 0
    assert parse_coord("450", 1000) == 450
    assert parse_coord("-50", 1000) == -50
    assert parse_coord("", 1000, 42) == 42
    assert parse_coord("invalid", 1000, 100) == 100
    print("[+] Coordinate parsing tests passed!")

def test_color_parsing():
    print("[*] Testing color parser...")
    assert parse_color("#ffffff") == (255, 255, 255)
    assert parse_color("#000000") == (0, 0, 0)
    assert parse_color("#fdde27") == (253, 222, 39)
    assert parse_color("white") == (255, 255, 255)
    assert parse_color("black") == (0, 0, 0)
    assert parse_color("cyan") == (0, 255, 255)
    assert parse_color("invalid_color", (10, 20, 30)) == (10, 20, 30)
    print("[+] Color parsing tests passed!")

def test_packaged_themes():
    print("[*] Testing packaged example themes...")
    themes = [
        "themes/sekiro/theme.txt",
        "themes/spatial-glass/theme.txt",
        "themes/cyberpunk-2077/theme.txt",
        "themes/artorias/theme.txt"
    ]
    with tempfile.TemporaryDirectory() as tmpdir:
        for t in themes:
            assert os.path.exists(t), f"Theme missing: {t}"
            out_png = os.path.join(tmpdir, "out.png")
            render_preview(t, out_png, 1920, 1080)
            assert os.path.exists(out_png) and os.path.getsize(out_png) > 1000
            print(f"    [+] {t} rendered successfully at 1080p")
    print("[+] All packaged themes verified!")

def test_resolutions():
    print("[*] Testing multi-resolution scaling...")
    resolutions = [
        (3840, 2160, "4K UHD"),
        (1920, 1080, "1080p FHD"),
        (1280, 720,  "720p HD"),
        (800,  600,  "SVGA"),
        (640,  480,  "VGA Low-Res")
    ]
    theme = "themes/sekiro/theme.txt"
    with tempfile.TemporaryDirectory() as tmpdir:
        for w, h, label in resolutions:
            out_png = os.path.join(tmpdir, f"out_{w}x{h}.png")
            render_preview(theme, out_png, w, h)
            assert os.path.exists(out_png) and os.path.getsize(out_png) > 1000
            print(f"    [+] {label} ({w}x{h}) rendered successfully")
    print("[+] Multi-resolution scaling tests passed!")

def test_resilience_and_fallbacks():
    print("[*] Testing resilience to malformed config & missing assets...")
    with tempfile.TemporaryDirectory() as tmpdir:
        # Theme pointing to non-existent assets and malformed keys
        broken_theme = os.path.join(tmpdir, "broken_theme.txt")
        with open(broken_theme, "w") as f:
            f.write("""
# Malformed and missing assets theme
desktop-image: "non_existent_wallpaper.png"
desktop-color: "not_a_color"
title-text: "Resilience Test"
title-font: "missing_font.pf2"
unknown_global_property: 12345

+ unknown_component {
    foo = bar
}

+ boot_menu {
    left = 50%-200
    top = 30%
    width = 400
    height = 300
    item_font = "ghost_font.pf2"
    selected_item_pixmap_style = "non_existent_*.png"
    malformed_line_without_equals
}

+ label {
    id = "__timeout__"
    left = 10%
    top = 80%
    text = "Auto boot in %d s"
}
""")
        out_png = os.path.join(tmpdir, "broken_out.png")
        # Must not raise exceptions, must produce usable fallback preview
        render_preview(broken_theme, out_png, 1024, 768)
        assert os.path.exists(out_png) and os.path.getsize(out_png) > 1000
        print("    [+] Handled missing images, missing fonts, unknown blocks, and invalid colors gracefully")
    print("[+] Resilience tests passed!")

def test_comment_stripping_and_hex_colors():
    print("[*] Testing comment stripping and quoted/hex preservation...")
    assert strip_theme_comments("# full line comment") == ""
    assert strip_theme_comments("   # indented comment") == ""
    assert strip_theme_comments('color = "#58a6ff"') == 'color = "#58a6ff"'
    assert strip_theme_comments('color = "#58a6ff" # inline comment') == 'color = "#58a6ff"'
    assert strip_theme_comments('color = #58a6ff') == 'color = #58a6ff'
    assert strip_theme_comments('color = #58a6ff # inline comment') == 'color = #58a6ff'
    assert strip_theme_comments('text = "Option #1: Boot"') == 'text = "Option #1: Boot"'
    assert strip_theme_comments('image: "bg.png" // C++ comment') == 'image: "bg.png"'
    print("[+] Comment stripping and hex color preservation tests passed!")

def test_rendered_hex_colors():
    print("[*] Testing rendered hex color fidelity...")
    with tempfile.TemporaryDirectory() as tmpdir:
        theme_path = os.path.join(tmpdir, "color_test_theme.txt")
        with open(theme_path, "w") as f:
            f.write("""
desktop-color: "#123456"
title-text: ""
+ boot_menu {
    left = 0
    top = 0
    width = 10
    height = 10
}
""")
        out_png = os.path.join(tmpdir, "out.png")
        render_preview(theme_path, out_png, 100, 100)
        im = Image.open(out_png)
        # Verify corner pixel matches parsed hex color #123456
        corner_pixel = im.getpixel((95, 95))[:3]
        expected = (0x12, 0x34, 0x56)
        assert corner_pixel == expected, f"Expected {expected}, got {corner_pixel}"
        print(f"    [+] Pixel color verified: {corner_pixel} == {expected}")
    print("[+] Rendered hex color fidelity test passed!")

if __name__ == '__main__':
    print("========================================")
    print(" Limine Theme Engine Validation Suite")
    print("========================================")
    test_coordinate_parsing()
    test_color_parsing()
    test_packaged_themes()
    test_resolutions()
    test_resilience_and_fallbacks()
    test_comment_stripping_and_hex_colors()
    test_rendered_hex_colors()
    print("========================================")
    print(" ALL TESTS PASSED SUCCESSFULLY! ")
    print("========================================")
