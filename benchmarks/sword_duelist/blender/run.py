"""Reproduce the Blender route with bounded native tools and checked publication."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw
from aseprite_mcp.core.runtime import checkpoint, publish, run_native, workspace_lock


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BRIEF = json.loads((HERE.parent/"brief.json").read_text(encoding="utf-8"))


def indexed_frames(raw: Path, output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    palette = [{"name":name,"rgb":list(bytes.fromhex(color[1:]))} for name,color in BRIEF["palette"].items()]
    colors = [tuple(entry["rgb"]) for entry in palette]
    timeline = json.loads((raw/"timeline.json").read_text(encoding="utf-8"))
    for entry in timeline:
        image = Image.open(raw/entry["file"]).convert("RGBA")
        assert image.size == tuple(BRIEF["canvas"])
        indices = []
        for r,g,b,a in image.get_flattened_data():
            if a < 128:
                indices.append(0)
            else:
                indices.append(1+min(range(len(colors)),key=lambda i:sum((v-c)**2 for v,c in zip((r,g,b),colors[i]))))
        result = Image.new("P",image.size)
        result.putpalette([0,0,0]+[value for rgb in colors for value in rgb]+[0]*(768-3-3*len(colors)))
        result.putdata(indices)
        result.info["transparency"] = 0
        result.save(output/entry["file"])
        bounds = result.convert("RGBA").getchannel("A").getbbox()
        assert bounds and 0<bounds[0]<bounds[2]<96 and 0<bounds[1]<bounds[3]<80, (entry,bounds)
    data = {"palette":palette,"frames":timeline}
    (output/"import.json").write_text(json.dumps(data,indent=2)+"\n",encoding="utf-8")
    return data


def review_export(folder: Path) -> None:
    metadata = json.loads((folder/"sheet.json").read_text(encoding="utf-8"))
    frames = list(metadata["frames"].values())
    expected = [duration for clip in BRIEF["clips"].values() for duration in clip["durations_ms"]]
    assert len(frames)==32 and [frame["duration"] for frame in frames]==expected
    assert [(tag["name"],tag["from"],tag["to"]) for tag in metadata["meta"]["frameTags"]]==[("idle",0,7),("walk",8,19),("attack",20,31)]
    sheet = Image.open(folder/"sheet.png").convert("RGBA")
    palette = {tuple(bytes.fromhex(color[1:])) for color in BRIEF["palette"].values()}
    assert {pixel[:3] for pixel in sheet.get_flattened_data() if pixel[3]} <= palette
    contact = Image.new("RGBA",(8*192,4*176),"#202333")
    draw = ImageDraw.Draw(contact)
    images = []
    for index,frame in enumerate(frames):
        rect = frame["frame"]
        image = sheet.crop((rect["x"],rect["y"],rect["x"]+96,rect["y"]+80))
        bounds = image.getchannel("A").getbbox()
        assert bounds and 0<bounds[0]<bounds[2]<96 and 0<bounds[1]<bounds[3]<80, (index,bounds)
        background = Image.new("RGBA",image.size,"#202333")
        background.alpha_composite(image)
        contact.alpha_composite(background.resize((192,160),Image.Resampling.NEAREST),(index%8*192,index//8*176))
        label = "idle" if index<8 else "walk" if index<20 else "attack"
        draw.text((index%8*192+4,index//8*176+160),label+" "+str(index),fill="white")
        images.append(background)
    contact.save(folder/"contact.png")
    images[0].save(folder/"idle.png")
    images[0].resize((768,640),Image.Resampling.NEAREST).save(folder/"idle_nearest.png")
    for name,lo,hi in (("idle",0,8),("walk",8,20),("attack",20,32)):
        clip = images[lo:hi]
        clip[0].save(folder/(name+".gif"),save_all=True,append_images=clip[1:],
                     duration=expected[lo:hi],loop=0,disposal=2)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--blender",default="C:/Program Files/Blender Foundation/Blender 5.2/blender.exe")
    parser.add_argument("--aseprite",default="C:/Tools/Aseprite/aseprite.exe")
    parser.add_argument("--reuse-render",action="store_true")
    args = parser.parse_args()
    folder = ROOT/"generated/benchmarks/sword_duelist/blender"
    raw = folder/"raw"
    if not args.reuse_render:
        result = run_native(args.blender,["--background","--factory-startup","--python",str(HERE/"author.py"),
                                         "--","--output",str(raw)],ROOT,240)
        assert "BLENDER_DUELIST_AUTHORED" in result["log"]
    indexed_frames(raw,folder/"indexed")
    stage = folder/"duelist.aseprite"
    result = run_native(args.aseprite,["--batch","--script-param","folder="+str(folder/"indexed"),
                                      "--script-param","output="+str(stage),"--script",str(HERE/"import.lua")],ROOT)
    assert "BLENDER_DUELIST_IMPORTED" in result["log"]
    run_native(args.aseprite,["--batch","--list-tags","--list-slices",str(stage),"--sheet-type","horizontal",
                             "--sheet",str(folder/"sheet.png"),"--data",str(folder/"sheet.json")],ROOT)
    review_export(folder)
    slices = json.loads((folder/"sheet.json").read_text())["meta"]["slices"]
    assert slices[0]["keys"][0]["pivot"] == {"x":44,"y":70}
    with workspace_lock(ROOT):
        names = [(HERE/name).relative_to(ROOT).as_posix() for name in ("duelist.aseprite","duelist.blend") if (HERE/name).is_file()]
        if names:
            checkpoint(ROOT,names,"Before reproducing Blender duelist")
        changed = publish(ROOT,{HERE/"duelist.aseprite":stage.read_bytes(),HERE/"duelist.blend":(raw/"ashguard.blend").read_bytes()})
    print(json.dumps({"ok":True,"frames":32,"palette_colors":len(BRIEF["palette"]),"changed":changed,
                      "source":str(HERE/"duelist.aseprite"),"contact_sheet":str(folder/"contact.png")},indent=2))


if __name__ == "__main__":
    main()
