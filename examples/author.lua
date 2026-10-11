-- Independent geometric fixtures; never overwrite an artist's native source.
local root = app.params.root
assert(root)
local function paint(image,x,y,w,h,color)
  for yy=y,y+h-1 do for xx=x,x+w-1 do image:drawPixel(xx,yy,color) end end
end
local cream = Color{r=239,g=221,b=170,a=255}
local cyan = Color{r=61,g=168,b=188,a=255}
local dark = Color{r=48,g=43,b=58,a=255}
local gold = Color{r=225,g=166,b=64,a=255}
local function sprite(kind)
  local file = root..'/sources/'..kind..'.aseprite'
  if app.fs.isFile(file) then return end
  local spr = Sprite(32,32,ColorMode.RGB)
  spr.layers[1].name = kind == 'rig' and 'body' or (kind == 'environment' and 'back' or 'art')
  local img = Image(32,32,ColorMode.RGB)
  if kind == 'rig' then
    paint(img,12,6,8,8,cream);paint(img,10,14,12,10,cyan)
    paint(img,11,24,4,5,dark);paint(img,17,24,4,5,dark)
  elseif kind == 'fx' then
    paint(img,14,12,4,8,gold);paint(img,12,14,8,4,cream)
  elseif kind == 'ui' then
    paint(img,4,4,24,24,gold);paint(img,6,6,20,20,dark);paint(img,10,10,12,12,cyan)
  else
    paint(img,0,0,32,32,dark);paint(img,0,24,32,8,cyan)
  end
  spr:newCel(spr.layers[1],spr.frames[1],img,Point(0,0))
  if kind == 'rig' or kind == 'environment' then
    local layer = spr:newLayer();layer.name = kind == 'rig' and 'weapon' or 'banner'
    local part = Image(32,32,ColorMode.RGB)
    if kind == 'rig' then paint(part,22,9,2,15,cream);paint(part,20,19,6,2,gold)
    else paint(part,9,4,2,18,cream);paint(part,11,5,12,7,gold) end
    spr:newCel(layer,spr.frames[1],part,Point(0,0))
  end
  for index=2,3 do
    local frame=spr:newEmptyFrame();frame.duration=.12
    for _,layer in ipairs(spr.layers) do
      local original=layer:cel(spr.frames[1])
      spr:newCel(layer,frame,original.image:clone(),original.position)
    end
    if kind == 'fx' then
      local cel=spr.layers[1]:cel(frame)
      cel.opacity=index==2 and 190 or 100
      cel.position=Point(index-1,0)
    elseif kind == 'environment' then
      spr.layers[2]:cel(frame).position=Point(index-2,0)
    end
  end
  spr.frames[1].duration=.12
  local tag=spr:newTag(spr.frames[1],spr.frames[3]);tag.name='default'
  if kind == 'rig' then
    for _,entry in ipairs({{'body',16,28},{'weapon',22,20}}) do
      local slice=spr:newSlice(Rectangle(0,0,32,32));slice.name=entry[1];slice.pivot=Point(entry[2],entry[3])
    end
  end
  spr:saveAs(file);spr:close()
end
for _,kind in ipairs({'rig','fx','ui','environment'}) do sprite(kind) end
print('EXAMPLES_AUTHORED')
