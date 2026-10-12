-- Paint only visible material pixels; the accepted pose layers stay untouched.
local source=assert(app.params.source)
local output=assert(app.params.output)
assert(not app.fs.isFile(output),'Refusing to overwrite an edited source')
local function read(path)
  local file=assert(io.open(path,'r'));local value=json.decode(file:read('*a'));file:close();return value
end
local brief=read(assert(app.params.brief))
local poses=read(assert(app.params.poses))
local spr=assert(app.open(source))
assert(spr.colorMode==ColorMode.RGB and #spr.frames==24 and #spr.layers==5)
local C,groups={},{}
for name,hex in pairs(brief.palette) do
  C[name]=app.pixelColor.rgba(tonumber(hex:sub(2,3),16),tonumber(hex:sub(4,5),16),tonumber(hex:sub(6,7),16),255)
end
local function allowed(names)
  local set={};for _,name in ipairs(names) do set[C[name]]=true end;return set
end
groups.steel=allowed({'steel_shadow','steel','steel_light','highlight','blade_edge'})
groups.cloth=allowed({'coat_shadow','coat','coat_light'})
groups.scarf=allowed({'scarf_shadow','scarf','scarf_light'})
groups.leather=allowed({'dark','neutral','bronze_shadow','bronze','bronze_light'})
groups.leg=allowed({'dark','neutral','steel_shadow','steel'})
local originals={};for i,layer in ipairs(spr.layers) do originals[i]=layer end
app.activeLayer=originals[5]
local finish=spr:newLayer();finish.name='Material finish'
local image,frame,painted
local function sample(layer_index,x,y)
  local cel=originals[layer_index]:cel(frame)
  if not cel then return 0 end
  local cx,cy=x-cel.position.x,y-cel.position.y
  if cx<0 or cy<0 or cx>=cel.image.width or cy>=cel.image.height then return 0 end
  return cel.image:getPixel(cx,cy)
end
local function paint(x,y,color,index,group)
  x=math.floor(x+.5);y=math.floor(y+.5)
  if x<0 or x>=96 or y<0 or y>=80 then return end
  if not group[sample(index,x,y)] then return end
  for upper=index+1,5 do if app.pixelColor.rgbaA(sample(upper,x,y))>0 then return end end
  image:drawPixel(x,y,C[color]);painted=painted+1
end
local function line(x0,y0,x1,y1,color,index,group)
  x0=math.floor(x0+.5);y0=math.floor(y0+.5);x1=math.floor(x1+.5);y1=math.floor(y1+.5)
  local dx,sx=math.abs(x1-x0),x0<x1 and 1 or -1
  local dy,sy=-math.abs(y1-y0),y0<y1 and 1 or -1
  local error=dx+dy
  while true do
    paint(x0,y0,color,index,group);if x0==x1 and y0==y1 then break end
    local twice=2*error;if twice>=dy then error=error+dy;x0=x0+sx end;if twice<=dx then error=error+dx;y0=y0+sy end
  end
end
local total=0
for i,p in ipairs(poses) do
  frame=spr.frames[i];image=Image(96,80,ColorMode.RGB);painted=0
  local dx,dy=p.dx,p.dy
  local hy=p.head_dy
  -- Broad crown/cheek planes and a helmet rim; avoid isolated texture noise.
  line(41+dx,18+hy,44+dx,17+hy,'steel_light',3,groups.steel)
  line(42+dx,18+hy,44+dx,18+hy,'highlight',3,groups.steel)
  line(40+dx,21+hy,41+dx,25+hy,'neutral',3,groups.steel)
  line(46+dx,19+hy,48+dx,21+hy,'steel_light',3,groups.steel)
  line(44+dx,26+hy,46+dx,26+hy,'highlight',3,groups.steel)
  paint(48+dx,26+hy,'steel_shadow',3,groups.steel)
  paint(42+dx,27+hy,'bronze',3,groups.steel)
  -- Chest edge, overlapping plate, belt and a small warm fastening.
  line(46+dx,34+dy,46+dx,38+dy,'steel_light',3,groups.steel)
  paint(46+dx,35+dy,'highlight',3,groups.steel)
  line(43+dx,35+dy,43+dx,38+dy,'steel_shadow',3,groups.steel)
  paint(44+dx,38+dy,'steel',3,groups.steel)
  line(41+dx,40+dy,42+dx,43+dy,'coat',3,groups.cloth)
  line(44+dx,42+dy,45+dx,43+dy,'coat_light',3,groups.cloth)
  paint(45+dx,45+dy,'bronze_light',3,groups.leather)
  -- Woven scarf fold and a restrained stitched coat hem.
  line(41+dx,30+hy,44+dx,31+hy,'scarf_light',3,groups.scarf)
  line(43+dx,32+hy,46+dx,31+hy,'scarf_shadow',3,groups.scarf)
  line(29+dx,33+p.wave+dy,33+dx,33+p.wave+dy,'scarf_shadow',2,groups.scarf)
  line(36+dx,31+dy,38+dx,31+dy,'scarf_light',2,groups.scarf)
  line(46+dx,51+dy,48+dx,54+p.wave+dy,'coat_light',2,groups.cloth)
  line(37+dx,54-p.wave+dy,39+dx,53-p.wave+dy,'coat',2,groups.cloth)
  -- Shoulder bevel and bracer fastening follow the accepted arm endpoints.
  line(48+dx,33+dy,50+dx,32+dy,'steel_light',4,groups.steel)
  paint(50+dx,33+dy,'highlight',4,groups.steel)
  line(51+dx,34+dy,51+dx,36+dy,'steel_shadow',4,groups.steel)
  paint(49+dx,35+dy,'bronze_light',4,groups.steel)
  line(p.e[1],p.e[2]+1,p.h[1],p.h[2]-1,'steel_light',4,groups.steel)
  paint(p.h[1]-1,p.h[2],'bronze_light',4,groups.leather)
  -- Knee planes and leather straps stay attached to their own limbs.
  paint(p.fk[1],p.fk[2]-1,'steel_light',3,groups.steel)
  paint(p.fk[1]-1,p.fk[2]+1,'neutral',3,groups.steel)
  line(p.fk[1],p.fk[2]+4,p.ff[1],p.ff[2]-6,'steel_shadow',3,groups.leg)
  paint(p.ff[1],p.ff[2]-4,'bronze',3,groups.leather)
  paint(p.ff[1]-1,p.ff[2]-2,'skin_shadow',3,groups.leather)
  -- Rear limbs use quieter highlights to separate depth without changing shape.
  for y=34,69 do for x=20,60 do
    if sample(1,x,y)==C.steel_shadow then paint(x,y,'neutral',1,groups.leg)
    elseif sample(1,x,y)==C.coat_light then paint(x,y,'coat',1,groups.cloth) end
  end end
  assert(painted>=35,'Missing material features in pose '..i)
  total=total+painted
  spr:newCel(finish,frame,image,Point(0,0))
end
assert(#spr.layers==6 and #spr.frames==24)
spr:saveAs(output);spr:close()
print('DETAIL_FINISH_OK '..total)
