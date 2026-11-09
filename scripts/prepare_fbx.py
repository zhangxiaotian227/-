import bpy,math,json,time
from pathlib import Path
from mathutils import Vector,Matrix
from bpy_extras.object_utils import world_to_camera_view
import sys
args=sys.argv[sys.argv.index('--')+1:]
if len(args)!=2:raise RuntimeError('Usage: blender -b --python 导入新FBX准备.py -- input.fbx output_folder')
SOURCE=Path(args[0]).resolve();OUT=Path(args[1]).resolve()
assert SOURCE.is_file() and SOURCE.suffix.lower()=='.fbx','Input must be an existing FBX'
OUT.mkdir(parents=True,exist_ok=True)
PREP=OUT/'工程';PREP.mkdir(exist_ok=True)
OUT.mkdir(parents=True,exist_ok=True);(OUT/'模型检查').mkdir(exist_ok=True)
variants=[('01_8K正交_实线',False,False),('02_8K常规透视_实线',True,False),('03_8K正交_结构虚线',False,True),('04_8K常规透视_结构虚线',True,True)]
directions=[(0,-1,0),(0,1,0),(-1,0,0),(1,0,0),(0,0,1),(0,0,-1)]+[(x/math.sqrt(2),y/math.sqrt(2),z) for z in (1,-1) for x,y in [(-1,-1),(1,-1),(-1,1),(1,1)]]
tasks=[];reports=[]
for idx in range(1,2):
    label=SOURCE.stem.removeprefix('导出用_');source_path=SOURCE
    print('IMPORTING',label,flush=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(source_path))
    source=bpy.context.scene;bpy.context.view_layer.update();dg=bpy.context.evaluated_depsgraph_get()
    baked=[]
    for inst in dg.object_instances:
        if inst.object.type not in {'MESH','CURVE','SURFACE','FONT'} or inst.object.original.hide_render:continue
        mesh=bpy.data.meshes.new_from_object(inst.object,preserve_all_data_layers=False,depsgraph=dg)
        if not mesh.vertices:bpy.data.meshes.remove(mesh);continue
        mesh.materials.clear();baked.append((inst.object.name,mesh,inst.matrix_world.copy()))
    assert baked,label+' has no geometry'
    s=bpy.data.scenes.new(label+'_线稿');bpy.context.window.scene=s
    for name,mesh,matrix in baked:
        o=bpy.data.objects.new(name,mesh);s.collection.objects.link(o);o.matrix_world=matrix
    for old in list(bpy.data.scenes):
        if old!=s:bpy.data.scenes.remove(old)
    linked=set(s.objects)
    for o in list(bpy.data.objects):
        if o not in linked:bpy.data.objects.remove(o,do_unlink=True)
    bpy.context.view_layer.update()
    points=[o.matrix_world@Vector(c) for o in s.objects for c in o.bound_box]
    lo=Vector([min(p[i] for p in points) for i in range(3)]);hi=Vector([max(p[i] for p in points) for i in range(3)])
    center=(lo+hi)/2;normalization=2/max(hi-lo)
    for o in s.objects:o.matrix_world=Matrix.Scale(normalization,4)@Matrix.Translation(-center)@o.matrix_world
    bpy.context.view_layer.update()
    points=[o.matrix_world@Vector(c) for o in s.objects for c in o.bound_box];radius=max(p.length for p in points)
    s.render.engine='BLENDER_EEVEE';s.render.film_transparent=True;s.render.use_freestyle=True;s.render.use_compositing=True
    s.render.resolution_x=7680;s.render.resolution_y=4320;s.render.resolution_percentage=100
    s.render.image_settings.file_format='PNG';s.render.image_settings.color_mode='RGBA'
    s.render.line_thickness_mode='ABSOLUTE';s.render.line_thickness=1;s.view_settings.view_transform='Standard'
    vl=s.view_layers[0];vl.use_freestyle=True;f=vl.freestyle_settings
    f.as_render_pass=True;f.mode='EDITOR';f.crease_angle=math.radians(145);f.use_smoothness=False
    for ls in list(f.linesets):f.linesets.remove(ls)
    for name,edges,width,alpha,hidden in [('01_轮廓',['silhouette','border','contour','external_contour'],5.4,1,None),('02_结构',['crease'],3.2,1,None),('03_近层结构',['silhouette','border','crease','contour','external_contour'],2.8,.75,(1,2,16,12)),('04_深层结构',['silhouette','border','crease','contour','external_contour'],2.2,.45,(3,8,12,16))]:
        ls=f.linesets.new(name)
        for p in ls.bl_rna.properties:
            if p.type=='BOOLEAN' and p.identifier.startswith('select_'):setattr(ls,p.identifier,False)
        ls.select_by_visibility=True;ls.select_by_edge_types=True;ls.edge_type_combination='OR';ls.edge_type_negation='INCLUSIVE'
        for e in edges:setattr(ls,'select_'+e,True)
        ls.visibility='RANGE' if hidden else 'VISIBLE'
        st=ls.linestyle;st.color=(0,0,0);st.alpha=alpha;st.thickness=width
        st.use_chaining=True;st.use_length_min=False;st.use_length_max=False;st.caps='BUTT' if hidden else 'ROUND'
        if hidden:
            ls.qi_start,ls.qi_end,st.dash1,st.gap1=hidden;st.use_dashed_line=True
            st.dash2=st.dash3=st.gap2=st.gap3=0
    tree=bpy.data.node_groups.new(label+'_纯线稿合成','CompositorNodeTree');s.compositing_node_group=tree
    tree.interface.new_socket(name='Image',in_out='OUTPUT',socket_type='NodeSocketColor')
    rl=tree.nodes.new('CompositorNodeRLayers');rl.scene=s;rl.layer=vl.name;nodeout=tree.nodes.new('NodeGroupOutput')
    bpy.context.view_layer.update();rl.update();tree.links.new(rl.outputs['Freestyle'],nodeout.inputs[0])
    cams=[]
    for i,d in enumerate(directions):
        data=bpy.data.cameras.new(label+f'_{i+1:02d}');cam=bpy.data.objects.new(label+f'_{i+1:02d}',data);s.collection.objects.link(cam)
        cam.location=Vector(d).normalized()*radius*5;cam.rotation_euler=(-cam.location).to_track_quat('-Z','Y').to_euler()
        data.type='ORTHO';data.ortho_scale=radius*4;data.clip_start=.001;data.clip_end=radius*100
        data.lens=50;data.sensor_width=36;data.sensor_fit='HORIZONTAL';cams.append(cam)
    bpy.context.view_layer.update()
    worst=max(max(abs(p.x-.5)*2,abs(p.y-.5)*2) for cam in cams for v in points for p in [world_to_camera_view(s,cam,v)])
    scale=radius*4*worst/.86
    for cam in cams:cam.data.type='PERSP'
    distance=radius*5
    for _ in range(30):
        for cam,d in zip(cams,directions):cam.location=Vector(d).normalized()*distance
        bpy.context.view_layer.update()
        worst=max(max(abs(p.x-.5)*2,abs(p.y-.5)*2) for cam in cams for v in points for p in [world_to_camera_view(s,cam,v)])
        if worst<=.862:break
        distance*=max(1.01,worst/.86)
    for cam,d in zip(cams,directions):
        cam.data.type='ORTHO';cam.data.ortho_scale=scale;cam.location=Vector(d).normalized()*radius*5
    s.camera=cams[6]
    # Source-shape overview, separate from the 8K line art tests.
    s.render.engine='BLENDER_WORKBENCH';s.render.use_freestyle=False;s.render.use_compositing=False;s.render.resolution_percentage=25
    s.display.shading.light='STUDIO';s.display.shading.color_type='SINGLE';s.display.shading.single_color=(.65,.65,.65)
    s.render.filepath=str(OUT/'模型检查'/(label+'.png'));bpy.ops.render.render(write_still=True)
    s.render.engine='BLENDER_EEVEE';s.render.use_freestyle=True;s.render.use_compositing=True;s.render.resolution_percentage=100
    blend=PREP/(label+'_14相机.blend');bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    for vi,(folder,perspective,hidden) in enumerate(variants):
        (OUT/folder/label).mkdir(parents=True,exist_ok=True)
        if idx!=1 and vi!=0:continue
        path=OUT/folder/label/(label+'_07_左前_俯视45.png')
        tasks.append(dict(model=label,index=idx,variant=folder,variant_index=vi,blend=str(blend),scene=s.name,camera=cams[6].name,output=str(path),perspective=perspective,hidden=hidden,distance=distance,radius=radius,ortho_scale=scale))
    reports.append(dict(model=label,source=str(source_path),source_bytes=source_path.stat().st_size,objects=len(baked),vertices=sum(len(mesh.vertices) for _,mesh,_ in baked),source_bounds=[list(lo),list(hi)],scale=scale,perspective_distance=distance))
    (OUT/'渲染任务.json').write_text(json.dumps(tasks,ensure_ascii=False,indent=2),encoding='utf-8')
    (OUT/'模型导入检查.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2),encoding='utf-8')
    print('MODEL_READY',label,flush=True)
print('NEW_MODEL_READY',len(tasks),flush=True)
