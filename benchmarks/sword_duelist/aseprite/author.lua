-- Original pixel clusters and explicit poses; no raster rotations or 3D renders.
local root = assert(app.params.root)
local destination = assert(app.params.output)
local study = app.params.study == 'true'
assert(not app.fs.isFile(destination), 'Refusing to overwrite an edited source')
local input = assert(io.open(root..'/brief.json', 'r'))
local brief = json.decode(input:read('*a')); input:close()
local C = {}
for name, value in pairs(brief.palette) do C[name] = Color{r=tonumber(value:sub(2,3),16),g=tonumber(value:sub(4,5),16),b=tonumber(value:sub(6,7),16),a=255} end
local spr = Sprite(brief.canvas[1], brief.canvas[2], ColorMode.RGB)
local layers = {}
for i, name in ipairs({'far limbs', 'coat and scarf', 'body and helmet', 'sword arm', 'steel sword'}) do
  local layer = i == 1 and spr.layers[1] or spr:newLayer()
  layer.name = name; layers[i] = layer
end
local image
local function pixel(x,y,c)
  x=math.floor(x+.5); y=math.floor(y+.5)
  assert(x>=0 and x<96 and y>=0 and y<80, 'Pose escapes canvas')
  image:drawPixel(x,y,C[c])
end
local function line(x0,y0,x1,y1,c)
  x0=math.floor(x0+.5);y0=math.floor(y0+.5);x1=math.floor(x1+.5);y1=math.floor(y1+.5)
  local dx,sx=math.abs(x1-x0), x0<x1 and 1 or -1
  local dy,sy=-math.abs(y1-y0), y0<y1 and 1 or -1
  local err=dx+dy
  while true do
    pixel(x0,y0,c);if x0==x1 and y0==y1 then break end
    local e=2*err;if e>=dy then err=err+dy;x0=x0+sx end;if e<=dx then err=err+dx;y0=y0+sy end
  end
end
local function polygon(points,c)
  local miny,maxy=80,0
  for _,p in ipairs(points) do miny=math.min(miny,p[2]);maxy=math.max(maxy,p[2]) end
  for y=math.floor(miny),math.ceil(maxy) do
    local edges={}
    for i,a in ipairs(points) do
      local b=points[i%#points+1]
      if (a[2]<=y and b[2]>y) or (b[2]<=y and a[2]>y) then edges[#edges+1]=a[1]+(y-a[2])*(b[1]-a[1])/(b[2]-a[2]) end
    end
    table.sort(edges)
    for i=1,#edges,2 do for x=math.ceil(edges[i]),math.floor(edges[i+1]) do pixel(x,y,c) end end
  end
  for i,a in ipairs(points) do local b=points[i%#points+1];line(a[1],a[2],b[1],b[2],c) end
end
local function shifted(points,dx,dy,c)
  local result={};for i,p in ipairs(points) do result[i]={p[1]+dx,p[2]+dy} end
  polygon(result,c)
end
local function segment(a,b,width,shade,light)
  local dx,dy=b[1]-a[1],b[2]-a[2];local length=math.sqrt(dx*dx+dy*dy)
  assert(length>0)
  local nx,ny=-dy/length,dx/length
  local function shape(w,c)
    local r=(w-1)/2
    polygon({{a[1]+nx*r,a[2]+ny*r},{b[1]+nx*r,b[2]+ny*r},{b[1]-nx*r,b[2]-ny*r},{a[1]-nx*r,a[2]-ny*r}},c)
  end
  shape(width,'outline');shape(width-2,shade)
  if light then line(a[1]-nx,a[2]-ny,b[1]-nx,b[2]-ny,light) end
end
local function boot(ankle,direction,far,mode)
  local x,y=ankle[1],ankle[2]
  if mode == 'heel' then
    polygon({{x-2,y-5},{x+2,y-5},{x+2,y-2},{x+5,y-2},{x+5,y-1},{x-2,y+1}},'outline')
  elseif mode == 'toe' then
    polygon({{x-2,y-5},{x+2,y-4},{x+2,y-1},{x+5,y},{x+5,y+1},{x-2,y-1}},'outline')
  else
    polygon({{x-2,y-5},{x+2,y-5},{x+2,y-1},{x+5*direction,y},{x+5*direction,y+1},{x-2,y+1}},'outline')
  end
  local shade=far and 'dark' or 'bronze_shadow'
  if mode=='heel' then
    polygon({{x-1,y-4},{x+1,y-4},{x+1,y-2},{x+3,y-2},{x-1,y}},shade)
  elseif mode=='toe' then
    polygon({{x-1,y-4},{x+1,y-3},{x+1,y-1},{x+3,y},{x-1,y-2}},shade)
  else
    polygon({{x-1,y-4},{x+1,y-4},{x+1,y-1},{x+3*direction,y},{x-1,y}},shade)
  end
  if not far then
    line(x,y-4,x+1,y-2,'bronze')
    if mode=='heel' then line(x-1,y+1,x+4,y-1,'neutral')
    elseif mode=='toe' then line(x-1,y-1,x+4,y+1,'neutral')
    else line(x-1,y+1,x+4*direction,y+1,'neutral') end
  end
end
local function legs(p,far)
  local dx,dy=p.dx or 0,p.dy or 0
  local hip=far and {41+dx,48+dy} or {47+dx,48+dy}
  local knee=far and p.bk or p.fk
  local ankle=far and p.bf or p.ff
  segment(hip,knee,7,far and 'dark' or 'neutral',far and 'neutral' or 'steel_shadow')
  segment(knee,{ankle[1],ankle[2]-3},6,far and 'dark' or 'neutral',far and nil or 'steel_shadow')
  if not far then
    polygon({{knee[1]-2,knee[2]-2},{knee[1]+2,knee[2]-2},{knee[1]+2,knee[2]+1},{knee[1],knee[2]+3},{knee[1]-2,knee[2]+1}},'steel_shadow')
    line(knee[1],knee[2]-2,knee[1]+2,knee[2]-1,'steel')
  end
  boot(ankle,1,far,far and p.bmode or p.fmode)
end
local function body(p)
  local dx,dy=p.dx or 0,p.dy or 0
  if p.profile then
    shifted({{40,31},{45,30},{49,33},{48,42},{47,49},{39,49},{38,39}},dx,dy,'outline')
    shifted({{40,33},{44,32},{47,34},{46,43},{45,47},{40,47},{39,39}},dx,dy,'coat_shadow')
    shifted({{44,35},{47,35},{46,42},{43,45},{42,39}},dx,dy,'coat')
    shifted({{43,31},{46,32},{49,34},{47,40},{43,41},{41,36}},dx,dy,'steel_shadow')
    shifted({{43,32},{46,33},{47,35},{46,39},{43,39},{42,36}},dx,dy,'steel')
    line(44+dx,33+dy,46+dx,34+dy,'steel_light')
    line(45+dx,34+dy,46+dx,35+dy,'highlight')
    line(41+dx,42+dy,47+dx,44+dy,'coat_light')
    line(40+dx,44+dy,47+dx,45+dy,'bronze')
    pixel(45+dx,45+dy,'bronze_light')
  else
  shifted({{39,31},{45,29},{51,33},{51,43},{49,49},{39,49},{36,40}},dx,dy,'outline')
  shifted({{39,33},{45,31},{49,33},{49,44},{47,47},{39,47},{38,39}},dx,dy,'coat_shadow')
  shifted({{43,34},{48,34},{48,43},{44,45},{43,40}},dx,dy,'coat')
  -- Breastplate: broad planes, a small warm reflected edge and no scattered noise.
  shifted({{39,31},{45,30},{50,33},{48,40},{42,42},{38,38}},dx,dy,'steel_shadow')
  shifted({{40,32},{45,31},{48,33},{47,38},{43,40},{40,37}},dx,dy,'steel')
  shifted({{41,32},{45,31},{47,33},{46,35},{42,36}},dx,dy,'steel_light')
  line(41+dx,32+dy,45+dx,31+dy,'highlight');line(39+dx,37+dy,41+dx,40+dy,'bronze_shadow')
  line(40+dx,43+dy,48+dx,44+dy,'outline');line(40+dx,44+dy,48+dx,45+dy,'bronze')
  polygon({{44+dx,44+dy},{46+dx,44+dy},{46+dx,46+dy},{44+dx,46+dy}},'bronze_light')
  end
  dy=p.head_dy or dy
  -- Helmet profile with a dark visor and stepped jaw silhouette.
  shifted({{40,16},{46,16},{49,19},{50,22},{52,23},{50,25},{49,29},{43,30},{39,27},{38,21}},dx,dy,'outline')
  shifted({{41,17},{46,17},{48,20},{49,23},{49,26},{47,28},{42,28},{40,25},{39,21}},dx,dy,'steel_shadow')
  shifted({{41,18},{45,17},{47,19},{47,21},{42,22},{40,21}},dx,dy,'steel')
  line(42+dx,18+dy,45+dx,18+dy,'steel_light');pixel(46+dx,19+dy,'highlight')
  shifted({{42,22},{50,21},{50,24},{43,25}},dx,dy,'outline')
  line(46+dx,23+dy,49+dx,22+dy,'scarf_light')
  shifted({{43,25},{48,24},{49,26},{47,28},{43,28}},dx,dy,'steel')
  line(44+dx,26+dy,47+dx,25+dy,'steel_light');line(43+dx,28+dy,46+dx,29+dy,'bronze_shadow')
  -- Scarf folds in front of the collar.
  shifted({{39,28},{43,29},{49,28},{50,30},{47,33},{40,32},{38,30}},dx,dy,'scarf_shadow')
  line(40+dx,29+dy,47+dx,30+dy,'scarf');line(42+dx,30+dy,47+dx,29+dy,'scarf_light')
end
local function coat(p)
  local dx,dy=p.dx or 0,p.dy or 0;local wave=p.wave or 0
  shifted({{39,40},{48,42},{49,49},{53,56+wave},{47,57+wave},{44,51},{40,58-wave},{34,56-wave},{37,48}},dx,dy,'outline')
  shifted({{39,43},{42,44},{42,50},{39,56-wave},{36,55-wave},{39,48}},dx,dy,'coat_shadow')
  shifted({{44,44},{47,45},{47,49},{51,55+wave},{47,55+wave},{44,49}},dx,dy,'coat')
  line(46+dx,48+dy,49+dx,54+wave+dy,'coat_light')
  line(38+dx,53-wave+dy,37+dx,55-wave+dy,'coat')
  shifted({{40,29},{35,29},{30,32+wave},{25,31+wave},{23,34+wave},{31,35+wave},{37,32},{41,32}},dx,dy,'outline')
  shifted({{39,30},{35,30},{30,33+wave},{25,32+wave},{26,34+wave},{31,34+wave},{37,31}},dx,dy,'scarf')
  line(30+dx,33+wave+dy,34+dx,31+dy,'scarf_light')
end
local function arm(p,far)
  local dx,dy=p.dx or 0,p.dy or 0
  local shoulder=far and {39+dx,34+dy} or {49+dx,34+dy}
  local elbow=far and (p.be or {35+dx,41+dy}) or p.e
  local hand=far and (p.bh or {40+dx,46+dy}) or p.h
  segment(shoulder,elbow,6,far and 'coat_shadow' or 'coat',far and nil or 'coat_light')
  segment(elbow,hand,5,far and 'dark' or 'steel_shadow',far and nil or 'steel')
  polygon({{hand[1]-2,hand[2]-1},{hand[1]+1,hand[2]-2},{hand[1]+2,hand[2]+1},{hand[1],hand[2]+2},{hand[1]-2,hand[2]+1}},'outline')
  line(hand[1]-1,hand[2],hand[1]+1,hand[2],far and 'bronze_shadow' or 'bronze')
  if not far then
    shifted({{47,31},{51,31},{54,34},{52,38},{48,37},{46,34}},dx,dy,'outline')
    shifted({{48,32},{51,32},{53,34},{51,36},{48,35}},dx,dy,'steel')
    line(49+dx,32+dy,51+dx,33+dy,'steel_light')
  end
end
local function sword(p)
  local h,t=p.h,p.tip;local vx,vy=t[1]-h[1],t[2]-h[2];local n=math.sqrt(vx*vx+vy*vy);vx=vx/n;vy=vy/n
  local nx,ny=-vy,vx;local a={h[1]+vx*4,h[2]+vy*4}
  local endtip={t[1],t[2]}
  polygon({{a[1]+nx*2,a[2]+ny*2},{t[1]+nx,t[2]+ny},{t[1]+vx,t[2]+vy},{t[1]-nx,t[2]-ny},{a[1]-nx*2,a[2]-ny*2}},'outline')
  segment(a,endtip,3,'steel_light','blade_edge')
  line(a[1]+nx,a[2]+ny,t[1],t[2],'steel')
  local g={h[1]+vx*3,h[2]+vy*3}
  line(g[1]+nx*4,g[2]+ny*4,g[1]-nx*4,g[2]-ny*4,'outline')
  line(g[1]+nx*3,g[2]+ny*3,g[1]-nx*3,g[2]-ny*3,'bronze')
  pixel(g[1],g[2],'bronze_light');line(h[1]-vx*3,h[2]-vy*3,h[1]+vx,h[2]+vy,'bronze_shadow')
end
local neutral={dx=0,dy=0,fk={48,58},ff={50,68},bk={38,58},bf={35,68},e={55,39},h={55,44},tip={64,19}}
local function idle(i)
  local p={};for k,v in pairs(neutral) do p[k]=v end
  local ys={0,0,-1,-1,-1,0,0,0};p.dy=ys[i];p.wave=({0,-1,-1,0,1,1,0,0})[i]
  p.e={55,39+p.dy};p.h={55,44+p.dy};p.tip={64,19+p.dy};return p
end
local walklegs={
  {{53,57},{60,68},{38,57},{31,68}},{{52,56},{57,68},{37,59},{33,66}},
  {{50,57},{53,68},{39,60},{37,64}},{{47,57},{48,68},{42,57},{41,63}},
  {{43,57},{41,68},{47,55},{48,64}},{{40,57},{36,68},{50,55},{54,67}},
  {{38,57},{31,68},{51,57},{60,68}},{{37,59},{33,66},{50,56},{57,68}},
  {{39,60},{37,64},{48,57},{53,68}},{{42,57},{41,63},{45,57},{48,68}},
  {{47,55},{48,64},{41,57},{41,68}},{{50,55},{54,67},{38,57},{36,68}}
}
local function walk(i)
  local v=walklegs[i];local bob=({0,-1,-1,0,1,1,0,-1,-1,0,1,1})[i]
  local sway=({0,1,2,2,1,0,-1,-2,-2,-1,0,0})[i]
  return {dx=0,dy=bob,fk=v[1],ff=v[2],bk=v[3],bf=v[4],e={54+sway,38+bob},h={54+sway,43+bob},tip={63+sway,18+bob},wave=({0,0,1,1,1,0,0,-1,-1,-1,0,0})[i],be={36-sway,40+bob},bh={40-sway,46+bob}}
end
-- Eight deliberately posed contact/down/passing/up keys, repeated on the other leg.
local study_legs={
  {{52,58},{56,68},{38,58},{32,68},'heel','toe'},
  {{54,60},{50,68},{39,58},{33,65},'flat','air'},
  {{46,58},{44,68},{47,55},{40,63},'flat','air'},
  {{41,57},{38,68},{51,56},{51,65},'flat','air'},
  {{38,58},{32,68},{52,58},{56,68},'toe','heel'},
  {{39,58},{33,65},{52,60},{50,68},'air','flat'},
  {{49,55},{40,63},{44,58},{44,68},'air','flat'},
  {{53,56},{51,65},{39,57},{38,68},'air','flat'}
}
local function study_walk(i)
  local v=study_legs[i]
  local dy=({0,2,0,-2,0,2,0,-2})[i]
  local h=({{54,44},{54,45},{55,43},{56,41},{57,42},{57,43},{56,43},{55,43}})[i]
  local be=({{44,40},{45,42},{41,42},{36,39},{34,39},{34,41},{37,41},{41,39}})[i]
  local bh=({{49,45},{50,45},{44,47},{34,45},{30,45},{32,47},{38,47},{45,43}})[i]
  return {profile=true,dx=({0,0,-1,-1,0,0,1,1})[i],dy=dy,head_dy=dy/2,
    fk=v[1],ff=v[2],bk=v[3],bf=v[4],fmode=v[5],bmode=v[6],
    e={h[1],h[2]-5},h=h,tip={h[1]+9,h[2]-25},be=be,bh=bh,
    wave=({0,1,1,0,0,-1,-1,0})[i]}
end
local function study_between(i,t)
  local a,b=study_walk(i),study_walk(i%8+1)
  local p={}
  for name,value in pairs(a) do
    if type(value)=='number' then p[name]=value+(b[name]-value)*t
    elseif type(value)=='table' then p[name]={value[1]+(b[name][1]-value[1])*t,value[2]+(b[name][2]-value[2])*t}
    else p[name]=value end
  end
  -- A push-off leaves contact immediately; a landing remains airborne until its key.
  if t>0 then
    if a.fmode=='toe' and b.fmode=='air' then p.fmode='air' end
    if a.bmode=='toe' and b.bmode=='air' then p.bmode='air' end
  end
  return p
end
local attacks={
  {0,0,{53,35},{48,31},{36,9}}, {-1,1,{47,30},{40,28},{17,14}},
  {-2,1,{44,29},{39,27},{15,15}}, {1,0,{53,28},{54,24},{49,2}},
  {5,1,{61,33},{67,34},{90,34}}, {6,2,{61,39},{66,43},{85,57}},
  {5,2,{58,44},{60,48},{74,67}}, {4,1,{54,44},{55,47},{70,62}},
  {2,0,{53,41},{55,45},{70,48}}, {1,0,{54,40},{55,44},{68,32}},
  {0,0,{55,39},{55,44},{65,23}}, {0,0,{55,39},{55,44},{64,19}}
}
local function attack(i)
  local v=attacks[i];local lunge=math.max(0,v[1])
  return {dx=v[1],dy=v[2],e=v[3],h=v[4],tip=v[5],fk={49+lunge,58},ff={52+lunge,68},bk={38,58},bf={33,68},wave=i<5 and -1 or 1,be={36+v[1],39+v[2]},bh={39+v[1],44+v[2]}}
end
local count=0
local ranges={}
local contacts={}
local subdivisions=study and (app.params.inbetweens=='true' and 3 or 1) or 1
local study_durations={};for i=1,8*subdivisions do study_durations[i]=120/subdivisions end
for _,clip in ipairs(study and {'walk'} or {'idle','walk','attack'}) do
  local first=count+1
  for i,ms in ipairs(study and study_durations or brief.clips[clip].durations_ms) do
    count=count+1
    local frame=count==1 and spr.frames[1] or spr:newEmptyFrame();frame.duration=ms/1000
    local phase=math.floor((i-1)/subdivisions)+1
    local part=(i-1)%subdivisions
    local p=study and study_between(phase,part/subdivisions) or (clip=='idle' and idle(i) or (clip=='walk' and walk(i) or attack(i)))
    if study then
      local points={}
      for _,entry in ipairs({{'near',p.ff,p.fmode},{'far',p.bf,p.bmode}}) do
        if entry[3]~='air' then points[#points+1]={foot=entry[1],mode=entry[3],pixel={math.floor(entry[2][1]+(entry[3]=='heel' and -2 or 5)+.5),math.floor(entry[2][2]+1.5)}} end
      end
      contacts[#contacts+1]={frame=i-1,duration_ms=ms,key=part==0,phase=({'contact','down','passing','up','contact','down','passing','up'})[phase],contacts=points}
    end
    for layer_index,layer in ipairs(layers) do
      image=Image(96,80,ColorMode.RGB)
      if layer_index==1 then legs(p,true);arm(p,true)
      elseif layer_index==2 then coat(p)
      elseif layer_index==3 then legs(p,false);body(p)
      elseif layer_index==4 then arm(p,false)
      else sword(p) end
      spr:newCel(layer,frame,image,Point(0,0))
    end
  end
  ranges[#ranges+1]={clip,first,count}
end
-- Appending a frame at a tag's end expands that tag; define ranges after drawing.
for _,range in ipairs(ranges) do
  local tag=spr:newTag(spr.frames[range[2]],spr.frames[range[3]]);tag.name=range[1]
end
local palette=Palette(21);palette:setColor(0,Color{r=0,g=0,b=0,a=0})
local names={'outline','dark','neutral','steel_shadow','steel','steel_light','highlight','coat_shadow','coat','coat_light','scarf_shadow','scarf','scarf_light','bronze_shadow','bronze','bronze_light','skin_shadow','skin','skin_light','blade_edge'}
for i,name in ipairs(names) do palette:setColor(i,C[name]) end
spr:setPalette(palette)
local pivot=spr:newSlice(Rectangle(0,0,96,80));pivot.name='ground';pivot.pivot=Point(brief.anchor[1],brief.anchor[2])
if study then
  local motion={stride_pixels=48,cycle_seconds=.96,velocity_pixels_per_second=50,anchor={brief.anchor[1],brief.anchor[2]},poses=contacts}
  spr.data=json.encode(motion)
  if app.params.motion then local file=assert(io.open(app.params.motion,'w'));file:write(json.encode(motion));file:close() end
end
spr:saveAs(destination);spr:close()
print('DUELIST_AUTHORED '..count)
