"""Independent MCP protocol/native acceptance; real game sources are never edited."""
import asyncio
import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

BASE=Path(__file__).resolve().parents[2]

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

async def main():
    count=0
    with tempfile.TemporaryDirectory(prefix='MCP bağımsız proje ') as directory:
        root=Path(directory)
        examples=root/'examples'
        shutil.copytree(BASE/'examples',examples,ignore=shutil.ignore_patterns('.godot','*.import','parts','rig.tscn','fx','ui','environment','*.publish-tmp'))
        project=examples/'project'
        env=dict(os.environ,ART_REPO=str(root),ART_PROJECT=str(project))
        parameters=StdioServerParameters(command=sys.executable,args=['-m','pixelspark_art_mcp'],cwd=str(root),env=env)
        async with stdio_client(parameters) as (reader,writer):
            async with ClientSession(reader,writer) as client:
                await client.initialize()
                async def call(name,args,failed=False):
                    nonlocal count
                    result=await client.call_tool(name,args)
                    assert result.isError == failed,(name,result)
                    count+=1
                    if failed:
                        return result
                    if result.structuredContent is not None:
                        return result.structuredContent
                    return json.loads(next(c.text for c in result.content if c.type == 'text'))
                tools=await client.list_tools()
                assert {'batch_edit_sprite','edit_animation','build_asset','review_asset'} <= {t.name for t in tools.tools}
                await call('inspect_workspace',{})
                sources={p.name:digest(p) for p in (examples/'sources').glob('*.aseprite')}
                motion=project/'rig/motion.tres'
                original_motion=digest(motion)
                scenes={}
                for kind in ['rig','fx','ui','environment']:
                    result=await call('build_asset',{'recipe_path':f'examples/recipes/{kind}.json'})
                    scenes[kind]=result['scene']
                    repeated=await call('build_asset',{'recipe_path':f'examples/recipes/{kind}.json'})
                    assert not repeated.get('changed',[]) and not repeated.get('changed_textures',[]) and not repeated.get('changed_views',[]), repeated
                assert digest(motion)==original_motion
                assert sources=={p.name:digest(p) for p in (examples/'sources').glob('*.aseprite')}
                recipe=examples/'recipes/fx.json'
                config=json.loads(recipe.read_text())
                config['animations']={'default':{'loop':False,'markers':{'contact':.12,'chain_ready':.24}}}
                config['required_markers']={'default':['contact','chain_ready']}
                recipe.write_text(json.dumps(config))
                await call('build_asset',{'recipe_path':'examples/recipes/fx.json'})
                repeated=await call('build_asset',{'recipe_path':'examples/recipes/fx.json'})
                assert not repeated['changed'],repeated
                await call('import_godot_assets',{})
                for kind,scene in scenes.items():
                    await call('inspect_godot_scene',{'scene':scene,'report_path':f'generated/{kind}-inspection.json'})
                clips=await call('inspect_godot_scene',{'scene':scenes['fx']})
                clip=clips['animations'][0]
                assert not clip['loop'] and abs(clip['seconds']-.36)<.0001
                assert abs(clip['markers']['contact']-.12)<.0001 and abs(clip['markers']['chain_ready']-.24)<.0001
                shutil.copyfile(Path(__file__).with_name('frame_playback.gd'),project/'frame_playback.gd')
                playback=await call('run_godot_script',{'script_path':'examples/project/frame_playback.gd','arguments':[scenes['fx']]})
                assert 'FRAME_PLAYBACK_OK' in playback['log']
                await call('edit_animation',{'library_path':'examples/project/rig/motion.tres','clip':'attack','patch':{'markers':{'other':0.3}}},True)
                assert digest(motion)==original_motion
                await call('edit_animation',{'library_path':'examples/project/rig/motion.tres','clip':'attack','patch':{'tracks':[{'path':'Skeleton2D/root/body/weapon:rotation','keys':[[0.3,-0.8]],'interpolation':'linear'}],'markers':{'contact':0.32}}})
                report=await call('inspect_godot_scene',{'scene':scenes['rig']})
                clips={c['name']:c for c in report['animations']}
                assert abs(clips['attack']['markers']['contact']-0.32)<0.0001
                assert abs(clips['idle']['markers']['contact']-0.3)<0.0001
                source='examples/sources/rig.aseprite'
                await call('edit_aseprite',{'source_path':source,'script':'local layer=app.sprite.layers[1]; app.layer=layer; app.frame=1; app.range.layers={layer}; app.range.frames={1,2}; app.command.LinkCels(); assert(layer:cel(1).image.id==layer:cel(2).image.id, "Expected linked fixture")'})
                await call('build_asset',{'recipe_path':'examples/recipes/rig.json'})
                before=digest(root/source)
                await call('batch_edit_sprite',{'source_path':source,'operations':[{'op':'palette_remap','args':{'layer_name':'body','start_frame':1,'end_frame':1,'mappings':[{'from':'#3DA8BC','to':'#AC3D52'}]}},{'op':'cel_position','args':{'layer_name':'body','frame_index':999,'x':1,'y':1}}]},True)
                assert digest(root/source)==before
                result=await call('batch_edit_sprite',{'source_path':source,'operations':[{'op':'palette_remap','args':{'layer_name':'body','start_frame':1,'end_frame':1,'mappings':[{'from':'#3DA8BC','to':'#AC3D52'}]}},{'op':'frame_duration','args':{'frame_index':1,'duration_ms':160}}]})
                assert digest(root/source)!=before
                rebuilt=await call('build_asset',{'recipe_path':'examples/recipes/rig.json'})
                assert rebuilt['changed_views']==['body-01.tres'],rebuilt
                restored=await call('restore_source_revision',{'revision':result['checkpoint']['revision']})
                assert digest(root/source)==before
                await call('build_asset',{'recipe_path':'examples/recipes/rig.json'})
                for kind,scene in scenes.items():
                    args={'scene':scene,'duration':0.6,'output_dir':f'generated/review/{kind}','source_path':f'examples/sources/{kind}.aseprite'}
                    if kind=='rig':
                        args['animation']='attack'
                    if kind=='fx':
                        args['effects']=['example_fx']
                        args.update(animation='default',fps=50,duration=.36)
                    review=await call('review_asset',args)
                    assert review['viewport']==[320,180] and all(m['frames']==18 for m in review['modes'].values())
                    assert (root/f'generated/review/{kind}/index.html').is_file()
                    if kind=='fx':
                        assert review['sample_times'][0]==0 and review['timeline']['sampling']=='exact_animation_player'
                        assert [key['captured_samples'] for key in review['timeline']['frame_keys']]==[list(range(6)),list(range(6,12)),list(range(12,18))]
                        assert not review['unsampled_frame_keys']
                        shutil.copyfile(Path(__file__).with_name('review_playback.gd'),project/'review_playback.gd')
                        checked=await call('run_godot_script',{'script_path':'examples/project/review_playback.gd','arguments':[scene,str(root/'generated/review/fx'),str(Path(__file__).resolve().parents[1]/'pixelspark_art_mcp/review.gd')]})
                        assert 'REVIEW_PLAYBACK_OK' in checked['log']
                        await call('review_asset',{'scene':scene,'animation':'default','duration':.36,'fps':30,'output_dir':'generated/review/bad-sampling','baseline_dir':'generated/review/fx'},True)
                        assert not (root/'generated/review/bad-sampling').exists()
                await call('capture_animation',{'scene':scenes['rig'],'animation':'idle','times':[0.0,0.3,0.6],'output_dir':'generated/exact'})
                compared=await call('review_asset',{'scene':scenes['rig'],'animation':'attack','duration':0.6,'output_dir':'generated/review/comparison','baseline_dir':'generated/review/rig'})
                assert len(compared['baseline_changed_pixels'])==4
        destination=Path(os.environ.get('ART_TEST_REPORTS',str(BASE/'generated/native-acceptance'))).resolve()
        destination.mkdir(parents=True,exist_ok=True)
        shutil.copytree(root/'generated/review',destination/'review',dirs_exist_ok=True)
        (destination/'verification.json').write_text(json.dumps({'ok':True,'checks':count,'workspace':'isolated temporary directory','viewport':[320,180]},indent=2)+'\n')
    print(f'NATIVE_TOOLKIT PASS: {count} protocol checks; four independent asset families')

if __name__=='__main__':
    asyncio.run(main())
