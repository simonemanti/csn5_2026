#!/bin/sh
voxes_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec blender "$voxes_dir/v1_VOXES.blend" --python "$voxes_dir/voxes_panel.py"
