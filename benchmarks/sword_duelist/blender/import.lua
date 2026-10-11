-- Native palette-indexed cels; the render and deliberately drawn pixel finishing
-- remain separate editable layers. This never mutates an existing source.
local folder = assert(app.params.folder)
local output = assert(app.params.output)
local stream = assert(io.open(folder..'/import.json','r'))
local data = json.decode(stream:read('*a'));stream:close()
local spr = Sprite(96,80,ColorMode.INDEXED)
local palette = spr.palettes[1]
palette:resize(#data.palette+1)
palette:setColor(0,Color{r=0,g=0,b=0,a=0})
local indices = {}
for index,entry in ipairs(data.palette) do
  local rgb = entry.rgb
  palette:setColor(index,Color{r=rgb[1],g=rgb[2],b=rgb[3],a=255})
  indices[entry.name] = index
end
local base = spr.layers[1];base.name = 'Rendered geometry'
local retouch = spr:newLayer();retouch.name = 'Pixel finishing - outline visor rivets'
local count = 0
local function paint(image,x,y,color)
  if x>=0 and x<96 and y>=0 and y<80 then image:drawPixel(x,y,color);count=count+1 end
end
local starts,ends = {},{}
for index,entry in ipairs(data.frames) do
  local frame = index==1 and spr.frames[1] or spr:newEmptyFrame()
  frame.duration = entry.duration_ms/1000
  local rendered = Image{fromFile=folder..'/'..entry.file}
  assert(rendered.width==96 and rendered.height==80 and rendered.colorMode==ColorMode.INDEXED)
  spr:newCel(base,frame,rendered,Point(0,0))
  local finishing = Image(96,80,ColorMode.INDEXED)
  for y=1,78 do for x=1,94 do
    if rendered:getPixel(x,y)==0 and (rendered:getPixel(x-1,y)>0 or
      rendered:getPixel(x+1,y)>0 or rendered:getPixel(x,y-1)>0 or rendered:getPixel(x,y+1)>0) then
      paint(finishing,x,y,indices.outline)
    end
  end end
  -- Two-pixel visor and single-pixel warm rivets restore features lost at 54 px.
  local visor = entry.retouch_anchors.visor
  for dx=-1,0 do
    if rendered:getPixel(visor[1]+dx,visor[2])>0 then
      paint(finishing,visor[1]+dx,visor[2],indices.outline)
    end
  end
  for _,name in ipairs({'rivet','temple'}) do
    local point = entry.retouch_anchors[name]
    if rendered:getPixel(point[1],point[2])>0 then
      paint(finishing,point[1],point[2],indices.bronze_light)
    end
  end
  spr:newCel(retouch,frame,finishing,Point(0,0))
  starts[entry.clip] = starts[entry.clip] or index
  ends[entry.clip] = index
end
for _,name in ipairs({'idle','walk','attack'}) do
  local tag = spr:newTag(spr.frames[starts[name]],spr.frames[ends[name]])
  tag.name = name
  tag.aniDir = AniDir.FORWARD
end
local ground = spr:newSlice(Rectangle(0,0,96,80));ground.name='ground';ground.pivot=Point(44,70)
spr.data = json.encode({name='Ashguard duelist',source='Editable Blender rig and mesh',
  contact_seconds=.28,chain_ready_seconds=.54,retouch_pixel_operations=count})
assert(#spr.frames==32 and #spr.layers==2 and #spr.tags==3 and count>500)
spr:saveAs(output);spr:close()
print('BLENDER_DUELIST_IMPORTED '..count)
