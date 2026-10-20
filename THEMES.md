# Limine Native Graphical Theming System

This document outlines the architecture, declarative theme format, component specifications, asset guidelines, and installation procedures for Limine's graphical theme engine.

---

## 1. Quick Start: Enabling a Theme

To enable graphical theming, set `theme_path:` in your `limine.conf`:

```ini
# Limine Configuration with Theme
timeout: 5
interface_resolution: 1920x1080
theme_path: boot():/themes/astronaut/theme.txt

/CachyOS Linux
    protocol: linux
    kernel_path: boot():/vmlinuz-linux-cachyos
    kernel_cmdline: root=UUID=xxxx rw quiet
    module_path: boot():/initramfs-linux-cachyos.img

/UEFI Firmware Settings
    protocol: efi_chainload
    image_path: boot():/EFI/BOOT/BOOTX64.EFI
```

If the theme file or its assets are missing, or if memory allocation fails, Limine **guarantees a safe fallback** to its built-in terminal boot menu without blocking the boot process.

---

## 2. Directory Layout of a Theme

A theme directory contains `theme.txt` alongside all its visual assets:

```
themes/my-theme/
├── theme.txt              # Declarative theme configuration
├── background.png         # Static wallpaper OR animated GIF
├── font.pf2               # GNU GRUB PFF2 binary font
├── logo.png               # Optional decorative logo/banner
├── item_*.png             # Normal entry button slices (3-slice or 9-slice)
├── selected_item_*.png    # Selected entry button slices
└── icons/                 # Operating system and distro icons
    ├── linux.png
    ├── arch.png
    ├── cachyos.png
    ├── windows.png
    └── efi.png
```

---

## 3. Theme Syntax & Supported Components

Theme files use a declarative key-value format inspired by GNU GRUB 2's `gfxmenu`:

### 3.1 Proportional Coordinates
Coordinates support percentage-of-screen and pixel offsets:
- `50%` (halfway across the screen)
- `50%-250` (centered with a 500px width: $50\% - 250\text{px}$)
- `10%+24` (10 percent plus 24px padding)
- `400` (absolute pixel value)

### 3.2 Colors
Colors can be specified as:
- Hex: `"#fdde27"`, `"#350581"`, `"0xffb343"`
- 3-digit Hex: `"#fff"`, `"#000"`
- Names: `white`, `black`, `gray`, `red`, `green`, `blue`, `yellow`, `cyan`, `magenta`

---

### 3.3 Component Reference

#### Global Properties
```ini
desktop-image: "background.png"    # Background image (PNG, JPEG, QOI, or animated GIF)
desktop-color: "#1a1235"          # Solid fallback background color
title-text: "System Boot"         # Header title text
title-color: "#fdde27"            # Header title color
title-font: "font.pf2"            # Optional PFF2 font for header title
```

#### Boot Menu Component (`+ boot_menu { ... }`)
```ini
+ boot_menu {
    left = 50%-250                # Horizontal position
    top = 34%                     # Vertical position
    width = 500                   # Menu container width
    height = 50%                  # Menu container height

    # Layout style: "vertical" (default standard list) or "spatial" (VisionOS card deck)
    layout = "spatial"
    card_width = 270              # Spatial card width
    card_height = 350             # Spatial card height

    item_height = 40              # Row height per entry (vertical mode)
    item_spacing = 36             # Gap between items (vertical or spatial cards)
    item_padding = 16             # Text horizontal inset

    item_font = "font.pf2"        # PFF2 font for unselected items
    selected_item_font = "font.pf2" # PFF2 font for selected item

    item_color = "#f6e0b4"        # Unselected text color
    selected_item_color = "#ffffff" # Selected text color
    selected_item_bg_color = "#ffb343" # Fallback pill highlight color

    # Box styles (3-slice or 9-slice)
    item_pixmap_style = "item_*.png"
    selected_item_pixmap_style = "selected_item_*.png"

    # OS / Distro Icons
    icon_width = 28
    icon_height = 28
    item_icon_space = 12
}
```

#### Label Component (`+ label { ... }`)
Themes can declare multiple label components for titles, subtitles, hotkey legends, or timers:
```ini
# Static Title or Subtitle Label
+ label {
    left = 8%
    top = 17%
    width = 38%
    align = "left"                # Alignment: left, center, right
    text = "KNIGHT ARTORIAS"
    color = "#e5c07b"
    font = "font.pf2"
}

# Dynamic Timeout Countdown Label
+ label {
    id = "__timeout__"            # Special ID for automatic boot timer
    left = 8%
    top = 78%
    width = 38%
    align = "left"
    text = "Rekindling realm in %d seconds..." # '%d' dynamically substituted
    color = "#e5c07b"
    font = "font.pf2"
}
```

#### Decorative Image Widget (`+ image { ... }`)
```ini
+ image {
    left = 50%-180
    top = 10%
    width = 360
    height = 96
    file = "logo.png"
}
```

---

## 4. Advanced Features

### 4.1 Animated Backgrounds (GIF)
Limine natively decodes multi-frame GIFs via its hardened `stb_image` integration.
- Supports looping animations with per-frame delay metadata.
- Frame stepping occurs seamlessly during both countdown and idle states.
- Keystrokes immediately interrupt sleep intervals with **zero input lag**.

### 4.2 3-Slice and 9-Slice Pixmap Boxes
When `item_pixmap_style` or `selected_item_pixmap_style` contains a `*` wildcard:
- **3-Slice Horizontal**: Resolves `_w.png` (left cap), `_c.png` (center), and `_e.png` (right cap).
- **9-Slice Full Box**: Resolves `_nw.png`, `_n.png`, `_ne.png`, `_w.png`, `_c.png`, `_e.png`, `_sw.png`, `_s.png`, `_se.png`.
- Corners preserve their original aspect ratio and resolution while borders and centers scale to fit.

### 4.3 Automatic Distro & OS Icon Matching
When `icon_width` and `icon_height` are specified, Limine inspects the boot entry name (e.g., `"CachyOS Linux"`, `"Arch Linux"`, `"Windows 11"`, `"UEFI Settings"`):
1. Matches extracted keywords against `<theme_dir>/icons/<token>.png`.
2. Falls back to `<theme_dir>/icons/linux.png`, `efi.png`, or `unknown.png`.
3. Caches loaded icons in memory to ensure maximum rendering speed.

---

## 5. Packaged Example Themes

This repository includes five fully functional example themes in `themes/`:

1. **`themes/artorias/`**:
   - Inspired by **Knight Artorias the Abysswalker** (`~/Pictures/WALLPAPERS/Artorias 1.png`).
   - Features ethereal soul-cyan and ancient gold accents, 3-slice illuminated selection pill with glowing left beacon, multi-label lore headers, decorative soul divider line, crisp monochrome distro icons, and Victor Mono PFF2 typography.
2. **`themes/astronaut/`**:
   - Inspired by the active SDDM `sddm-astronaut-theme` (`hyprland_kath`).
   - Features a 24-frame looping animated GIF background, asymmetrical left card, gold accents, and amber pills.
3. **`themes/modern/`**:
   - Cyberpunk Night City aesthetic with high-contrast typography, teal accents, and OS icons.
4. **`themes/minecraft/`**:
   - Authentic Minegrub theme with 9-slice stone buttons, Minecraft logo widget, and `Minecraft24.pf2` font.
5. **`themes/terminal-dark/`**:
   - Clean dark terminal theme with 3-slice selection pill, `vmi24b.pf2` monospaced font, and distro icons.

---

## 6. Testing & Previewing Themes Offline

You can preview and test themes offline without running a VM or modifying bootloaders:

```bash
# Render a 1080p preview of any theme:
python3 tools/preview_theme.py themes/astronaut/theme.txt preview.png

# Generate an animated GIF preview for animated themes:
python3 tools/preview_theme.py themes/astronaut/theme.txt preview.gif

# Run the complete test suite:
python3 tools/test_themes.py
```
