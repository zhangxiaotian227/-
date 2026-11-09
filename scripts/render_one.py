import bpy,json,sys,time
from pathlib import Path
from mathutils import Vector
args=sys.argv[sys.argv.index('--')+1:]
t=json.loads(Path(args[0]).read_text(encoding='utf-8'))[int(args[1])]
bpy.ops.wm.open_mainfile(filepath=t['blend'])
s=bpy.data.scenes[t['scene']];bpy.context.window.scene=s;cam=bpy.data.objects[t['camera']];s.camera=cam
cam.data.type='PERSP' if t['perspective'] else 'ORTHO';cam.data.ortho_scale=t['ortho_scale']
cam.location=cam.location.normalized()*(t['distance'] if t['perspective'] else t['radius']*5)
for ls in s.view_layers[0].freestyle_settings.linesets:ls.show_render=t['hidden'] if ls.name.startswith(('03_','04_')) else True
path=Path(t['output']);temp=path.with_name(path.stem+'.rendering.png');s.render.filepath=str(temp)
print('RENDER_START',t['model'],t['variant'],flush=True)
start=time.time();bpy.ops.render.render(write_still=True);temp.replace(path)
print('RENDER_COMPLETE',str(path),round(time.time()-start,1),flush=True)
