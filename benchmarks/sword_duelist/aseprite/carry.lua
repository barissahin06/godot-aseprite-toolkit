-- Replace only the weapon layers and their local finish; retain accepted artwork.
local source=assert(app.params.source)
local output=assert(app.params.output)
assert(not app.fs.isFile(output),'Refusing to overwrite an edited source')
local spr=assert(app.open(source))
local guide=assert(app.open(assert(app.params.guide)))
assert(#spr.frames==24 and #guide.frames==24 and #spr.layers==6 and #guide.layers==6)
local function sample(cel,x,y)
  local cx,cy=x-cel.position.x,y-cel.position.y
  if cx<0 or cy<0 or cx>=cel.image.width or cy>=cel.image.height then return 0 end
  return cel.image:getPixel(cx,cy)
end
for i,frame in ipairs(spr.frames) do
  assert(frame.duration==guide.frames[i].duration)
  local old,new={},{}
  for _,index in ipairs({4,5,6}) do
    assert(spr.layers[index].name==guide.layers[index].name)
    old[index]=assert(spr.layers[index]:cel(frame))
    new[index]=assert(guide.layers[index]:cel(guide.frames[i]))
  end
  local finish=Image(spr.width,spr.height,ColorMode.RGB)
  for y=0,spr.height-1 do for x=0,spr.width-1 do
    local selected=false
    for _,index in ipairs({4,5}) do
      selected=selected or app.pixelColor.rgbaA(sample(old[index],x,y))>0 or app.pixelColor.rgbaA(sample(new[index],x,y))>0
    end
    finish:drawPixel(x,y,sample(selected and new[6] or old[6],x,y))
  end end
  for _,index in ipairs({4,5}) do
    old[index].image=new[index].image:clone()
    old[index].position=Point(new[index].position.x,new[index].position.y)
  end
  old[6].image=finish;old[6].position=Point(0,0)
end
guide:close();spr:saveAs(output);spr:close()
print('CARRY_REVISION_OK 24')
