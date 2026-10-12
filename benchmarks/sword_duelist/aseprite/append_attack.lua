-- Preserve the accepted 24-frame walk and append separately drawn attack cels.
local output=assert(app.params.output)
assert(not app.fs.isFile(output),'Refusing to overwrite an edited source')
local spr=assert(app.open(assert(app.params.source)))
local guide=assert(app.open(assert(app.params.guide)))
assert(#spr.frames==24 and (#guide.frames==16 or #guide.frames==20) and #spr.layers==6 and #guide.layers==6)
local walk=assert(spr.tags[1]);assert(walk.name=='walk')
for i,pose in ipairs(guide.frames) do
  local frame=spr:newEmptyFrame();frame.duration=pose.duration
  for index,layer in ipairs(spr.layers) do
    assert(layer.name==guide.layers[index].name)
    local cel=assert(guide.layers[index]:cel(pose))
    spr:newCel(layer,frame,cel.image:clone(),Point(cel.position.x,cel.position.y))
  end
end
walk.toFrame=spr.frames[24]
local ready=spr:newTag(spr.frames[25],spr.frames[25]);ready.name='ready'
local attack=spr:newTag(spr.frames[25],spr.frames[#spr.frames]);attack.name='attack'
local count=#spr.frames
guide:close();spr:saveAs(output);spr:close()
print('COMBAT_SOURCE_OK '..count)
