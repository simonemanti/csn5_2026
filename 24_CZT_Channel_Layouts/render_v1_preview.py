"""Render a compact animation preview; never changes the source blend.

blender -b v1_Setup_PRISM.blend --python render_v1_preview.py
The PNG sequence can be encoded with ffmpeg at 8 fps.
"""
import argparse
import sys
from pathlib import Path

import bpy

parser=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument("--width",type=int,default=840,help="Preview width")
parser.add_argument("--samples",type=int,default=8,help="Cycles samples")
parser.add_argument("--step",type=int,default=3,help="Sample one frame every N timeline frames; fps = 24/N")
parser.add_argument("--output",type=Path,default=Path(__file__).resolve().parent/".build_v1_preview",help="PNG directory")
args=parser.parse_args(sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else [])
if args.step<1 or args.width<100 or args.samples<1:
    parser.error("step and samples must be positive; width must be at least 100")
args.output.mkdir(exist_ok=True,parents=True)
scene=bpy.context.scene
ctrl=bpy.data.objects["PRISM_Controls"]
ctrl["animate"]=True
ctrl.update_tag()
scene.camera=bpy.data.objects["Camera_DETAIL"]
scene.render.resolution_x=args.width
scene.render.resolution_y=round(args.width*.75)
scene.cycles.samples=args.samples
for index,frame in enumerate(range(scene.frame_start,scene.frame_end+1,args.step)):
    scene.frame_set(frame)
    scene.render.filepath=str(args.output/f"frame_{index:04d}.png")
    bpy.ops.render.render(write_still=True)
print("PRISM_PREVIEW_COMPLETE",index+1,"frames",24/args.step,"fps",args.output)
