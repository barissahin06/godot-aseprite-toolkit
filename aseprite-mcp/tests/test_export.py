"""Export and import tools (export.py)."""
import os
import struct

from conftest import BASE, ok, run

from aseprite_mcp.tools import animation, export


def png_size(path):
    with open(path, "rb") as f:
        data = f.read(24)
    return struct.unpack(">II", data[16:24])


def test_export_frame_scaled(sprite):
    out = f"{BASE}/frame1.png"
    ok(run(export.export_frame(sprite, 1, out, 8)))
    assert png_size(out) == (256, 256)


def test_export_spritesheet_with_data(sprite):
    ok(run(animation.add_frames(sprite, 3, 100)))
    out = f"{BASE}/sheet.png"
    data = f"{BASE}/sheet.json"
    ok(run(export.export_spritesheet(sprite, out, "horizontal", data, 2, 1)))
    assert os.path.exists(out) and os.path.exists(data)


def test_export_spritesheet_tag_filter(sprite):
    ok(run(animation.set_tag(sprite, "clip", 1, 2, "forward")))
    out = f"{BASE}/sheet_tag.png"
    ok(run(export.export_spritesheet(sprite, out, "horizontal", "", 1, 0, "clip")))
    w, h = png_size(out)
    assert (w, h) == (64, 32), "tag filter must export only the 2 tagged frames"


def test_export_layers(sprite):
    result = ok(run(export.export_layers(sprite, f"{BASE}/layers")))
    assert ".png" in result


def test_export_tag_gif(sprite):
    out = f"{BASE}/clip.gif"
    ok(run(export.export_tag(sprite, "clip", out, 4)))
    assert os.path.exists(out)


def test_import_image_as_layer(sprite):
    ok(run(export.import_image_as_layer(sprite, f"{BASE}/frame1.png", "ref", 1, 0, 0)))
