"""Build a dimensionally coherent PRISM XAS scene from the legacy source blend.

The source blend already contains useful illustrative meshes, but its optical
layout is almost exactly twice the Ag K-edge / Ge(880) baseline stored under
``3_Simulations``.  This script therefore:

* appends the tube, slit, sample and CZT assets from the source blend;
* derives a general visual scale from the simulated source--crystal arm;
* places the crystal and sample at the exact simulated central-ray coordinates;
* rebuilds the crystal surface object-dependently so that 40 x 20 x 1 mm and
  R = 250 mm can be satisfied simultaneously;
* uses the local photon-budget 45-degree incidence / 45-degree take-off
  fluorescence geometry;
* keeps the legacy CZT mesh as a not-to-scale illustration, puts it on the
  opposite side of the sample beam, aims its active face at the sample and
  keeps the channel row horizontal in the optical-bench plane;
* marks the mechanical dimensions of slit, sample and CZT as illustrative;
* discovers Blender's installed ``city.exr`` and uses it both as viewport
  Studio Light and as the render World environment;
* renders transparent RGBA with no text, ready for lettering in Inkscape.

The generated scene is an explanatory rendering, not a mechanical CAD model.
All Blender coordinates are millimetres (one Blender unit is displayed as
one millimetre).

Example (Blender is installed as a Flatpak on the development machine)::

    flatpak run org.blender.Blender --background \
      --python 11_SETUP_XAS/s1_Setup_PRISM.py

Optional script arguments must follow Blender's ``--`` separator::

    ... --python 11_SETUP_XAS/s1_Setup_PRISM.py -- \
      --output 11_SETUP_XAS/v2_Setup_PRISM.blend \
      --preview 11_SETUP_XAS/v2_Setup_PRISM.png
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Iterable, Sequence

import bpy
from mathutils import Matrix, Vector


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent

SOURCE_BLEND_CANDIDATES = (
    SCRIPT_DIR / "v1_Setup_XAS.blend",
    SCRIPT_DIR / "v1.1_Setup_PRISM.blend",
)
DEFAULT_SOURCE_BLEND = next(
    (path for path in SOURCE_BLEND_CANDIDATES if path.is_file()),
    SOURCE_BLEND_CANDIDATES[0],
)
DEFAULT_GEOMETRY_SUMMARY = (
    PROJECT_DIR / "3_Simulations" / "results" / "wp1" / "wp1_summary.json"
)
DEFAULT_FLUORESCENCE_BASELINE = (
    PROJECT_DIR / "15_Photon_Budget" / "config" / "baseline.json"
)
DEFAULT_OUTPUT_BLEND = SCRIPT_DIR / "v2_Setup_PRISM.blend"
DEFAULT_PREVIEW = SCRIPT_DIR / "v2_Setup_PRISM.png"

SOURCE_OBJECT_NAMES = (
    "X-ray tube",
    "Slit_1_XES",
    "Slit_2_XES",
    "Crystal",
    "Sample",
    "Cube",
    "Plane",
)

MM_PER_M = 1000.0
CRYSTAL_SEGMENTS = 64
BEAM_RADIUS_MM = 1.35
TUBE_Y_OFFSET_MM = -12.3
ARROWHEAD_SCALE = 2.0
SAMPLE_DISPLAY_DIMENSIONS_MM = (25.0, 1.0, 25.0)
# The reused detector asset is a 120 mm-long illustrative array.  Showing it
# at the 30 mm physical reference distance would overlap the sample holder, so
# its displayed active-face centre is deliberately moved farther away.
CZT_DISPLAY_DISTANCE_MM = 90.0


def parse_arguments() -> argparse.Namespace:
    """Parse only the arguments after Blender's ``--`` separator."""

    script_args = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=DEFAULT_SOURCE_BLEND,
        help="Blend file containing the reusable illustrative objects.",
    )
    parser.add_argument(
        "--geometry-summary",
        type=Path,
        default=DEFAULT_GEOMETRY_SUMMARY,
        help="WP1 JSON summary defining the Ag K-edge / Ge(880) geometry.",
    )
    parser.add_argument(
        "--fluorescence-baseline",
        type=Path,
        default=DEFAULT_FLUORESCENCE_BASELINE,
        help=(
            "Photon-budget JSON defining sample incidence, detector take-off "
            "and the reference CZT active volume."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_BLEND,
        help="Generated Blender scene.",
    )
    parser.add_argument(
        "--preview",
        type=Path,
        default=DEFAULT_PREVIEW,
        help="Rendered PNG preview.",
    )
    parser.add_argument(
        "--no-render",
        action="store_true",
        help="Save the blend without rendering the PNG preview.",
    )
    return parser.parse_args(script_args)


def require_file(path: Path, label: str) -> Path:
    path = path.expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"{label} not found: {path}")
    return path


def read_wp1_geometry(path: Path) -> dict[str, float | str]:
    """Read and validate the resolved WP1 geometry used by this scene."""

    with path.open(encoding="utf-8") as stream:
        summary = json.load(stream)

    resolved = summary.get("resolved_geometry") or summary.get("geometry")
    crystal = summary.get("geometry_config", {}).get("crystal", {})
    source = summary.get("source_config", {})
    if not isinstance(resolved, dict) or not isinstance(crystal, dict):
        raise ValueError(f"Malformed WP1 geometry summary: {path}")

    required_resolved = (
        "source_to_crystal_m",
        "configured_crystal_to_sample_m",
        "corrected_bragg_angle_deg",
        "central_deflection_angle_deg",
        "weighted_sagittal_focus_distance_m",
    )
    required_crystal = (
        "radius_m",
        "width_sagittal_m",
        "length_tangential_m",
        "thickness_m",
    )
    missing = [key for key in required_resolved if key not in resolved]
    missing += [f"crystal.{key}" for key in required_crystal if key not in crystal]
    if missing:
        raise ValueError(f"Missing WP1 geometry values: {', '.join(missing)}")

    data: dict[str, float | str] = {
        "crystal_label": str(resolved.get("crystal_label", "Ge(880)")),
        "energy_keV": float(source.get("energy_keV", 25.52)),
        "source_to_crystal_mm": MM_PER_M
        * float(resolved["source_to_crystal_m"]),
        "crystal_to_sample_mm": MM_PER_M
        * float(resolved["configured_crystal_to_sample_m"]),
        "focus_distance_mm": MM_PER_M
        * float(resolved["weighted_sagittal_focus_distance_m"]),
        "bragg_angle_deg": float(resolved["corrected_bragg_angle_deg"]),
        "deflection_angle_deg": float(resolved["central_deflection_angle_deg"]),
        "crystal_radius_mm": MM_PER_M * float(crystal["radius_m"]),
        "crystal_width_mm": MM_PER_M * float(crystal["width_sagittal_m"]),
        "crystal_length_mm": MM_PER_M
        * float(crystal["length_tangential_m"]),
        "crystal_thickness_mm": MM_PER_M * float(crystal["thickness_m"]),
    }

    if not str(data["crystal_label"]).replace(" ", "").lower().startswith("ge(880)"):
        raise ValueError(
            "This scene builder expects the Ag K-edge Ge(880) WP1 baseline; "
            f"found {data['crystal_label']!r}"
        )
    for key, value in data.items():
        if key.endswith("_mm") and float(value) <= 0.0:
            raise ValueError(f"{key} must be positive, found {value}")
    return data


def read_fluorescence_baseline(path: Path) -> dict[str, float]:
    """Read the reference Ag-foil and CZT fluorescence geometry."""

    with path.open(encoding="utf-8") as stream:
        config = json.load(stream)
    sample = config.get("sample", {})
    detector = config.get("detector", {})
    required_sample = (
        "thickness_um",
        "incident_angle_to_normal_deg",
        "detector_takeoff_angle_to_normal_deg",
    )
    required_detector = (
        "thickness_mm",
        "active_width_mm",
        "active_height_mm",
        "distance_mm",
    )
    missing = [f"sample.{key}" for key in required_sample if key not in sample]
    missing += [
        f"detector.{key}" for key in required_detector if key not in detector
    ]
    if missing:
        raise ValueError(
            f"Missing fluorescence-baseline values: {', '.join(missing)}"
        )

    data = {
        "sample_thickness_um": float(sample["thickness_um"]),
        "incident_angle_to_normal_deg": float(
            sample["incident_angle_to_normal_deg"]
        ),
        "detector_takeoff_angle_to_normal_deg": float(
            sample["detector_takeoff_angle_to_normal_deg"]
        ),
        "detector_thickness_mm": float(detector["thickness_mm"]),
        "detector_active_width_mm": float(detector["active_width_mm"]),
        "detector_active_height_mm": float(detector["active_height_mm"]),
        "detector_distance_mm": float(detector["distance_mm"]),
    }
    if any(value <= 0.0 for value in data.values()):
        raise ValueError("Fluorescence-baseline dimensions and angles must be positive")
    total_angle = (
        data["incident_angle_to_normal_deg"]
        + data["detector_takeoff_angle_to_normal_deg"]
    )
    if total_angle >= 180.0:
        raise ValueError("Incidence plus detector take-off must be below 180 degrees")
    return data


def reset_blender_file() -> bpy.types.Scene:
    """Reset the in-memory file so the output contains no source-scene debris."""

    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.name = "PRISM_Setup"
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0e-3
    scene.unit_settings.length_unit = "MILLIMETERS"
    return scene


def append_source_objects(
    source_blend: Path, collection: bpy.types.Collection
) -> dict[str, bpy.types.Object]:
    """Append the selected reusable objects and return them by source name."""

    with bpy.data.libraries.load(str(source_blend), link=False) as (
        data_from,
        data_to,
    ):
        absent = [name for name in SOURCE_OBJECT_NAMES if name not in data_from.objects]
        if absent:
            raise KeyError(
                f"Objects missing from {source_blend}: {', '.join(absent)}"
            )
        data_to.objects = list(SOURCE_OBJECT_NAMES)

    appended: dict[str, bpy.types.Object] = {}
    for source_name, obj in zip(SOURCE_OBJECT_NAMES, data_to.objects, strict=True):
        if obj is None:
            raise RuntimeError(f"Could not append source object {source_name!r}")
        collection.objects.link(obj)
        obj["source_object_name"] = source_name
        appended[source_name] = obj
    return appended


def set_principled_input(
    node: bpy.types.ShaderNodeBsdfPrincipled, names: Sequence[str], value: Any
) -> None:
    for name in names:
        socket = node.inputs.get(name)
        if socket is not None:
            socket.default_value = value
            return


def make_material(
    name: str,
    color: Sequence[float],
    *,
    metallic: float = 0.0,
    roughness: float = 0.45,
    emission_strength: float = 0.0,
) -> bpy.types.Material:
    """Create a Blender 3.x--5.x compatible Principled material."""

    material = bpy.data.materials.new(name)
    material.use_nodes = True
    material.diffuse_color = (*color[:3], color[3] if len(color) > 3 else 1.0)
    nodes = material.node_tree.nodes
    principled = next(
        (node for node in nodes if node.type == "BSDF_PRINCIPLED"), None
    )
    if principled is None:
        principled = nodes.new("ShaderNodeBsdfPrincipled")
    rgba = (*color[:3], color[3] if len(color) > 3 else 1.0)
    set_principled_input(principled, ("Base Color",), rgba)
    set_principled_input(principled, ("Metallic",), metallic)
    set_principled_input(principled, ("Roughness",), roughness)
    if emission_strength > 0.0:
        set_principled_input(
            principled, ("Emission Color", "Emission"), rgba
        )
        set_principled_input(
            principled, ("Emission Strength",), emission_strength
        )
    return material


def replace_crystal_mesh(
    crystal: bpy.types.Object,
    *,
    radius_mm: float,
    width_sagittal_mm: float,
    length_tangential_mm: float,
    thickness_mm: float,
    segments: int = CRYSTAL_SEGMENTS,
) -> float:
    """Replace the distorted source mesh with a constant-thickness R-radius ribbon.

    Local axes are chosen to match the source asset:

    * local X: tangential cylinder axis (physical length);
    * local Y: surface normal / sag;
    * local Z: sagittal curved chord (physical width).

    The return value is the surface sagitta at either sagittal edge.
    """

    half_width = 0.5 * width_sagittal_mm
    half_length = 0.5 * length_tangential_mm
    if radius_mm <= half_width:
        raise ValueError("Crystal radius must exceed half of the sagittal width")

    sagittal = [
        -half_width + width_sagittal_mm * index / segments
        for index in range(segments + 1)
    ]
    sag = [
        radius_mm - math.sqrt(radius_mm * radius_mm - coordinate * coordinate)
        for coordinate in sagittal
    ]

    # Vertices are ordered by surface (optical/rear), tangential edge,
    # sagittal sample.  The source lies on the local -Y side, so the solid
    # extends towards +Y and the nominal reflection point stays at local Y=0.
    vertices: list[tuple[float, float, float]] = []
    for back_surface in (False, True):
        normal_offset = thickness_mm if back_surface else 0.0
        for tangential in (-half_length, half_length):
            for sagittal_coordinate, surface_sag in zip(
                sagittal, sag, strict=True
            ):
                vertices.append(
                    (
                        tangential,
                        surface_sag + normal_offset,
                        sagittal_coordinate,
                    )
                )

    row = segments + 1

    def vertex_index(surface: int, tangential_edge: int, index: int) -> int:
        return surface * 2 * row + tangential_edge * row + index

    faces: list[tuple[int, int, int, int]] = []
    for index in range(segments):
        # Front and back optical faces.
        faces.append(
            (
                vertex_index(0, 0, index),
                vertex_index(0, 1, index),
                vertex_index(0, 1, index + 1),
                vertex_index(0, 0, index + 1),
            )
        )
        faces.append(
            (
                vertex_index(1, 0, index + 1),
                vertex_index(1, 1, index + 1),
                vertex_index(1, 1, index),
                vertex_index(1, 0, index),
            )
        )
        # Tangential end faces.
        faces.append(
            (
                vertex_index(0, 0, index + 1),
                vertex_index(1, 0, index + 1),
                vertex_index(1, 0, index),
                vertex_index(0, 0, index),
            )
        )
        faces.append(
            (
                vertex_index(0, 1, index),
                vertex_index(1, 1, index),
                vertex_index(1, 1, index + 1),
                vertex_index(0, 1, index + 1),
            )
        )

    # The two sagittal caps require opposite winding.
    faces.append(
        (
            vertex_index(0, 0, 0),
            vertex_index(1, 0, 0),
            vertex_index(1, 1, 0),
            vertex_index(0, 1, 0),
        )
    )
    faces.append(
        (
            vertex_index(0, 1, segments),
            vertex_index(1, 1, segments),
            vertex_index(1, 0, segments),
            vertex_index(0, 0, segments),
        )
    )

    old_mesh = crystal.data
    old_materials = [slot.material for slot in crystal.material_slots if slot.material]
    mesh = bpy.data.meshes.new("Ge_880_crystal_mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.validate(clean_customdata=True)
    mesh.update(calc_edges=True)
    for material in old_materials:
        mesh.materials.append(material)
    crystal.data = mesh
    crystal.scale = (1.0, 1.0, 1.0)
    if old_mesh.users == 0:
        bpy.data.meshes.remove(old_mesh)

    # Smooth only the two curved surfaces.  Flat walls and caps must not
    # contribute to their normals, otherwise the thin ribbon acquires a false
    # pillow-like highlight under city.exr.
    curved_face_count = 4 * segments
    for polygon in mesh.polygons:
        polygon.use_smooth = (
            polygon.index < curved_face_count
            and polygon.index % 4 in (0, 1)
        )

    # Mark every smooth/flat transition as sharp.  This is explicit and
    # stable across Blender's 3.x and 5.x normal-handling changes.
    edge_smoothing: dict[tuple[int, int], set[bool]] = {}
    for polygon in mesh.polygons:
        for edge_key in polygon.edge_keys:
            key = tuple(sorted(edge_key))
            edge_smoothing.setdefault(key, set()).add(polygon.use_smooth)
    edges_by_key = {
        tuple(sorted(tuple(edge.vertices))): edge for edge in mesh.edges
    }
    for edge_key, smoothing in edge_smoothing.items():
        if len(smoothing) > 1:
            edges_by_key[edge_key].use_edge_sharp = True
    return sag[-1]


def make_curve_object(
    name: str,
    points: Iterable[Vector | Sequence[float]],
    material: bpy.types.Material,
    collection: bpy.types.Collection,
    *,
    bevel_depth_mm: float,
) -> bpy.types.Object:
    curve = bpy.data.curves.new(name=f"{name}_curve", type="CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = 2
    curve.bevel_depth = bevel_depth_mm
    curve.bevel_resolution = 4
    spline = curve.splines.new("POLY")
    coordinates = [Vector(point) for point in points]
    spline.points.add(len(coordinates) - 1)
    for spline_point, coordinate in zip(
        spline.points, coordinates, strict=True
    ):
        spline_point.co = (*coordinate, 1.0)
    curve.materials.append(material)
    obj = bpy.data.objects.new(name, curve)
    collection.objects.link(obj)
    return obj


def add_arrowhead(
    name: str,
    start: Vector,
    end: Vector,
    material: bpy.types.Material,
    collection: bpy.types.Collection,
    *,
    fraction: float = 0.5,
) -> bpy.types.Object:
    direction = (end - start).normalized()
    location = start.lerp(end, fraction)
    bpy.ops.mesh.primitive_cone_add(
        vertices=32,
        radius1=4.8,
        radius2=0.0,
        depth=13.0,
        location=location,
    )
    arrow = bpy.context.object
    arrow.name = name
    arrow.rotation_mode = "QUATERNION"
    arrow.rotation_quaternion = Vector((0.0, 0.0, 1.0)).rotation_difference(
        direction
    )
    arrow.scale = (ARROWHEAD_SCALE,) * 3
    arrow["beam_fraction"] = fraction
    arrow["display_scale"] = ARROWHEAD_SCALE
    arrow.data.materials.append(material)
    for owner in list(arrow.users_collection):
        owner.objects.unlink(arrow)
    collection.objects.link(arrow)
    return arrow


def look_at(camera: bpy.types.Object, target: Vector) -> None:
    direction = target - camera.location
    camera.rotation_mode = "QUATERNION"
    camera.rotation_quaternion = direction.to_track_quat("-Z", "Y")


def rotate_in_xy(vector: Vector, angle_rad: float) -> Vector:
    cosine = math.cos(angle_rad)
    sine = math.sin(angle_rad)
    return Vector(
        (
            cosine * vector.x - sine * vector.y,
            sine * vector.x + cosine * vector.y,
            vector.z,
        )
    )


def czt_active_face_centre_local(detector: bpy.types.Object) -> Vector:
    """Return the area-weighted centre of the legacy CZT tiles' +Z faces."""

    active_faces = [
        polygon
        for polygon in detector.data.polygons
        if polygon.material_index == 0 and polygon.normal.z > 0.9
    ]
    if not active_faces:
        raise ValueError("Could not identify the legacy CZT active faces")
    total_area = sum(float(polygon.area) for polygon in active_faces)
    return sum(
        (polygon.center * float(polygon.area) for polygon in active_faces),
        Vector(),
    ) / total_area


def aim_czt_at_sample(
    detector: bpy.types.Object,
    active_centre_world: Vector,
    sample_position: Vector,
    long_axis_world: Vector,
) -> Vector:
    """Aim local +Z at the sample and keep the long channel row horizontal."""

    face_normal = (sample_position - active_centre_world).normalized()
    local_x_world = (
        long_axis_world
        - face_normal * long_axis_world.dot(face_normal)
    ).normalized()
    local_y_world = face_normal.cross(local_x_world).normalized()
    basis = Matrix(
        (
            (local_x_world.x, local_y_world.x, face_normal.x),
            (local_x_world.y, local_y_world.y, face_normal.y),
            (local_x_world.z, local_y_world.z, face_normal.z),
        )
    )
    detector.rotation_mode = "QUATERNION"
    detector.rotation_quaternion = basis.to_quaternion()

    active_centre_local = czt_active_face_centre_local(detector)
    scaled_centre_local = Vector(
        (
            active_centre_local.x * detector.scale.x,
            active_centre_local.y * detector.scale.y,
            active_centre_local.z * detector.scale.z,
        )
    )
    detector.location = (
        active_centre_world
        - detector.rotation_quaternion @ scaled_centre_local
    )
    bpy.context.view_layer.update()
    return detector.matrix_world @ active_centre_local


def create_camera(
    scene: bpy.types.Scene, collection: bpy.types.Collection, target: Vector
) -> bpy.types.Object:
    camera_data = bpy.data.cameras.new("PRISM_Camera")
    camera = bpy.data.objects.new("PRISM_Camera", camera_data)
    collection.objects.link(camera)
    camera_data.type = "ORTHO"
    camera_data.lens = 55.0
    camera_data.clip_start = 0.1
    camera_data.clip_end = 3000.0
    camera.location = target + Vector((-50.0, -1080.0, 610.0))
    look_at(camera, target)
    scene.camera = camera
    return camera


def frame_camera(
    scene: bpy.types.Scene,
    camera: bpy.types.Object,
    objects: Iterable[bpy.types.Object],
    *,
    margin: float = 1.85,
) -> None:
    """Fit an orthographic camera to the supplied object bounding boxes."""

    bpy.context.view_layer.update()
    inverse = camera.matrix_world.inverted()
    points: list[Vector] = []
    for obj in objects:
        if obj.type not in {"MESH", "CURVE", "FONT", "SURFACE", "META"}:
            continue
        for corner in obj.bound_box:
            points.append(inverse @ (obj.matrix_world @ Vector(corner)))
    if not points:
        return
    minimum_x = min(point.x for point in points)
    maximum_x = max(point.x for point in points)
    minimum_y = min(point.y for point in points)
    maximum_y = max(point.y for point in points)
    width = maximum_x - minimum_x
    height = maximum_y - minimum_y
    aspect = scene.render.resolution_x / scene.render.resolution_y
    camera.data.ortho_scale = margin * max(height, width / aspect)

    # ``ortho_scale`` fits the span but does not centre an asymmetric layout.
    # Translate the camera in its own image plane so tube, sample and off-axis
    # CZT receive equal margins.
    image_centre = Vector(
        (0.5 * (minimum_x + maximum_x), 0.5 * (minimum_y + maximum_y), 0.0)
    )
    camera.location += camera.matrix_world.to_quaternion() @ image_centre
    bpy.context.view_layer.update()


def find_city_exr() -> Path:
    """Find ``city.exr`` in the running Blender installation."""

    candidates: list[Path] = []
    try:
        datafiles = bpy.utils.system_resource(
            "DATAFILES", path="studiolights/world"
        )
        if datafiles:
            candidates.append(Path(datafiles) / "city.exr")
    except (AttributeError, TypeError):
        pass

    for studio_light in bpy.context.preferences.studio_lights:
        if (
            studio_light.type == "WORLD"
            and studio_light.name.casefold() == "city.exr"
        ):
            candidates.append(Path(studio_light.path))

    for root_name in ("LOCAL", "SYSTEM"):
        try:
            root = bpy.utils.resource_path(root_name)
        except (AttributeError, TypeError):
            root = ""
        if root:
            candidates.append(
                Path(root) / "datafiles" / "studiolights" / "world" / "city.exr"
            )

    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    checked = "\n  ".join(str(path) for path in candidates) or "(no candidates)"
    raise FileNotFoundError(
        "Blender's city.exr Studio Light was not found. Checked:\n  " + checked
    )


def configure_city_studio_light(
    scene: bpy.types.Scene, city_exr: Path
) -> bpy.types.World:
    """Configure city.exr for both saved viewport shading and final render."""

    world = bpy.data.worlds.new("PRISM_city_studio_world")
    world.use_nodes = True
    nodes = world.node_tree.nodes
    nodes.clear()

    coordinates = nodes.new("ShaderNodeTexCoord")
    coordinates.name = "World coordinates"
    mapping = nodes.new("ShaderNodeMapping")
    mapping.name = "Rotate city.exr"
    environment = nodes.new("ShaderNodeTexEnvironment")
    environment.name = "city.exr Studio Light"
    city_image = bpy.data.images.load(str(city_exr), check_existing=True)
    # Preserve the installation lookup in scene metadata, but pack the pixels
    # so the generated blend remains renderable outside the Flatpak sandbox.
    city_image.pack()
    environment.image = city_image
    background = nodes.new("ShaderNodeBackground")
    background.name = "Studio background"
    background.inputs["Strength"].default_value = 0.72
    camera_background = nodes.new("ShaderNodeBackground")
    camera_background.name = "Neutral camera background"
    camera_background.inputs["Color"].default_value = (0.92, 0.94, 0.97, 1.0)
    camera_background.inputs["Strength"].default_value = 0.8
    light_path = nodes.new("ShaderNodeLightPath")
    mix_backgrounds = nodes.new("ShaderNodeMixShader")
    mix_backgrounds.name = "City lighting with neutral camera background"
    output = nodes.new("ShaderNodeOutputWorld")

    # Rotate the panorama so its broad soft source illuminates the optical arm.
    rotation_socket = mapping.inputs.get("Rotation")
    if rotation_socket is not None:
        rotation_socket.default_value[2] = math.radians(105.0)

    links = world.node_tree.links
    links.new(coordinates.outputs["Generated"], mapping.inputs["Vector"])
    links.new(mapping.outputs["Vector"], environment.inputs["Vector"])
    links.new(environment.outputs["Color"], background.inputs["Color"])
    links.new(light_path.outputs["Is Camera Ray"], mix_backgrounds.inputs[0])
    links.new(background.outputs["Background"], mix_backgrounds.inputs[1])
    links.new(
        camera_background.outputs["Background"], mix_backgrounds.inputs[2]
    )
    links.new(mix_backgrounds.outputs["Shader"], output.inputs["Surface"])
    scene.world = world

    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type != "VIEW_3D":
                continue
            shading = area.spaces.active.shading
            shading.type = "MATERIAL"
            shading.light = "STUDIO"
            shading.studio_light = "city.exr"
            shading.use_scene_world = False
            if hasattr(shading, "studiolight_intensity"):
                shading.studiolight_intensity = 0.8
    return world


def configure_render(scene: bpy.types.Scene, preview_path: Path) -> None:
    for engine in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
        try:
            scene.render.engine = engine
            break
        except TypeError:
            continue
    scene.render.resolution_x = 2000
    scene.render.resolution_y = 1200
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = True
    scene.render.filepath = str(preview_path)
    scene.render.use_file_extension = True
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "Medium High Contrast"
    scene.view_settings.exposure = 0.0
    scene.view_settings.gamma = 1.0


def build_scene(
    source_blend: Path,
    geometry_summary: Path,
    fluorescence_baseline_path: Path,
    preview_path: Path,
) -> tuple[
    bpy.types.Scene,
    dict[str, float | str],
    dict[str, float],
]:
    geometry = read_wp1_geometry(geometry_summary)
    fluorescence = read_fluorescence_baseline(fluorescence_baseline_path)
    scene = reset_blender_file()

    assets = bpy.data.collections.new("PRISM_Assets")
    guides = bpy.data.collections.new("PRISM_Guides")
    view = bpy.data.collections.new("PRISM_View")
    scene.collection.children.link(assets)
    scene.collection.children.link(guides)
    scene.collection.children.link(view)

    objects = append_source_objects(source_blend, assets)
    tube = objects["X-ray tube"]
    slit_1 = objects["Slit_1_XES"]
    slit_2 = objects["Slit_2_XES"]
    crystal = objects["Crystal"]
    sample = objects["Sample"]
    detector = objects["Cube"]
    source_path = objects["Plane"]

    # The old layout uses the tube and crystal origins as its source arm.
    old_source = tube.location.copy()
    old_crystal_distance = (crystal.location - old_source).length
    target_arm = float(geometry["source_to_crystal_mm"])
    general_scale = target_arm / old_crystal_distance

    # General visual scaling preserves the recognisable proportions of the
    # mechanical assets.  Their physical sizes are not specified by WP1.
    for obj in (tube, slit_1, slit_2, sample, detector, source_path):
        obj.location = (obj.location - old_source) * general_scale
        obj.scale = obj.scale * general_scale
        obj["prism_scale_strategy"] = "general visual scale"
        obj["prism_general_scale"] = general_scale
        obj["dimensional_status"] = (
            "Illustrative: WP1 does not specify this component's mechanical size."
        )

    p_mm = float(geometry["source_to_crystal_mm"])
    q_mm = float(geometry["crystal_to_sample_mm"])
    theta_deg = float(geometry["bragg_angle_deg"])
    deflection_rad = math.radians(float(geometry["deflection_angle_deg"]))

    source_position = Vector((0.0, 0.0, 0.0))
    crystal_position = Vector((p_mm, 0.0, 0.0))
    outgoing_direction = Vector(
        (math.cos(deflection_rad), -math.sin(deflection_rad), 0.0)
    )
    sample_position = crystal_position + q_mm * outgoing_direction
    focus_position = crystal_position + float(
        geometry["focus_distance_mm"]
    ) * outgoing_direction

    tube.location = source_position + Vector((0.0, TUBE_Y_OFFSET_MM, 0.0))
    tube["beam_alignment_y_offset_mm"] = TUBE_Y_OFFSET_MM
    crystal.location = crystal_position
    sample.location = sample_position
    sample_local_extents = Vector(
        (
            max(corner[0] for corner in sample.bound_box)
            - min(corner[0] for corner in sample.bound_box),
            max(corner[1] for corner in sample.bound_box)
            - min(corner[1] for corner in sample.bound_box),
            max(corner[2] for corner in sample.bound_box)
            - min(corner[2] for corner in sample.bound_box),
        )
    )
    if any(extent <= 0.0 for extent in sample_local_extents):
        raise ValueError("Sample mesh has a zero local dimension")
    sample.scale = tuple(
        target / extent
        for target, extent in zip(
            SAMPLE_DISPLAY_DIMENSIONS_MM,
            sample_local_extents,
            strict=True,
        )
    )
    bpy.context.view_layer.update()

    # A single global scaling cannot enforce chord, tangential length,
    # thickness and bend radius simultaneously.  Rebuild only this object,
    # retaining its source material and object identity.
    crystal_sagitta = replace_crystal_mesh(
        crystal,
        radius_mm=float(geometry["crystal_radius_mm"]),
        width_sagittal_mm=float(geometry["crystal_width_mm"]),
        length_tangential_mm=float(geometry["crystal_length_mm"]),
        thickness_mm=float(geometry["crystal_thickness_mm"]),
    )
    germanium_surface = make_material(
        "Ge_880_optical_surface",
        (0.20, 0.25, 0.29, 1.0),
        metallic=0.58,
        roughness=0.22,
    )
    germanium_edges = make_material(
        "Ge_880_edges",
        (0.055, 0.075, 0.095, 1.0),
        metallic=0.38,
        roughness=0.34,
    )
    crystal.data.materials.clear()
    crystal.data.materials.append(germanium_surface)
    crystal.data.materials.append(germanium_edges)
    curved_face_count = 4 * CRYSTAL_SEGMENTS
    for polygon in crystal.data.polygons:
        polygon.material_index = (
            0
            if polygon.index < curved_face_count
            and polygon.index % 4 in (0, 1)
            else 1
        )
    crystal.rotation_mode = "XYZ"
    crystal.rotation_euler = (0.0, 0.0, math.radians(-theta_deg))
    crystal.name = "Ge_880_crystal"
    crystal.data.name = "Ge_880_crystal_mesh"
    crystal["prism_scale_strategy"] = "object-dependent physical reconstruction"
    crystal["material"] = str(geometry["crystal_label"])
    crystal["width_sagittal_mm"] = float(geometry["crystal_width_mm"])
    crystal["length_tangential_mm"] = float(geometry["crystal_length_mm"])
    crystal["thickness_mm"] = float(geometry["crystal_thickness_mm"])
    crystal["bend_radius_mm"] = float(geometry["crystal_radius_mm"])
    crystal["edge_sagitta_mm"] = crystal_sagitta
    crystal["dimensional_status"] = "Physical WP1 baseline"
    crystal["optical_surface"] = "local -Y side, facing the source"

    # The SHADOW4 sample plane is a scoring plane, not the physical foil
    # orientation.  Use the photon-budget incidence and take-off angles for
    # the fluorescence geometry.  The CZT is placed on the camera-facing side
    # of the beam so that its active channels remain visible.
    incidence_rad = math.radians(
        fluorescence["incident_angle_to_normal_deg"]
    )
    takeoff_rad = math.radians(
        fluorescence["detector_takeoff_angle_to_normal_deg"]
    )
    direction_to_crystal = -outgoing_direction
    sample_normal = rotate_in_xy(
        direction_to_crystal,
        -incidence_rad,
    ).normalized()
    detector_direction = rotate_in_xy(
        direction_to_crystal,
        -(incidence_rad + takeoff_rad),
    ).normalized()

    sample.rotation_mode = "XYZ"
    sample.rotation_euler = (
        0.0,
        0.0,
        math.atan2(sample_normal.y, sample_normal.x) - 0.5 * math.pi,
    )
    sample.name = "Ag_sample"
    sample["physical_reference_thickness_um"] = fluorescence[
        "sample_thickness_um"
    ]
    sample["incident_angle_to_normal_deg"] = fluorescence[
        "incident_angle_to_normal_deg"
    ]
    sample["detector_takeoff_angle_to_normal_deg"] = fluorescence[
        "detector_takeoff_angle_to_normal_deg"
    ]
    sample["dimensional_status"] = (
        "Displayed as 25 x 1 x 25 mm; physical foil reference remains 20 um."
    )
    sample["display_dimensions_mm"] = SAMPLE_DISPLAY_DIMENSIONS_MM

    slit_1.name = "Slit_1_XAS"
    slit_2.name = "Slit_2_XAS"
    detector.name = "CZT_detector"
    requested_detector_position = (
        sample_position + CZT_DISPLAY_DISTANCE_MM * detector_direction
    )
    detector_position = aim_czt_at_sample(
        detector,
        requested_detector_position,
        sample_position,
        outgoing_direction,
    )
    detector["role"] = "Off-axis multichannel CZT fluorescence detector"
    detector["not_to_scale"] = True
    detector["dimensional_status"] = (
        "Legacy housing/linear-array illustration; NOT TO SCALE."
    )
    detector["physical_reference_active_width_mm"] = fluorescence[
        "detector_active_width_mm"
    ]
    detector["physical_reference_active_height_mm"] = fluorescence[
        "detector_active_height_mm"
    ]
    detector["physical_reference_thickness_mm"] = fluorescence[
        "detector_thickness_mm"
    ]
    detector["physical_reference_sample_distance_mm"] = fluorescence[
        "detector_distance_mm"
    ]
    detector["display_sample_to_active_face_centre_mm"] = CZT_DISPLAY_DISTANCE_MM
    detector["active_face"] = "local +Z, aimed at the sample"
    detector["channel_row_orientation"] = (
        "local +X, horizontal in the optical-bench XY plane"
    )
    detector["display_side"] = (
        "opposite side of the sample beam, with active channels camera-visible"
    )

    # The original edge-only Plane is kept as a hidden geometry reference so
    # the generated blend still contains every source asset.
    source_path.name = "Source_optical_path_reference"
    source_path.hide_render = True
    source_path.hide_viewport = True

    beam_material = make_material(
        "Incident_X_ray",
        (1.0, 0.20, 0.025, 1.0),
        roughness=0.28,
        emission_strength=2.0,
    )
    fluorescence_material = make_material(
        "Ag_fluorescence",
        (0.05, 0.42, 1.0, 1.0),
        roughness=0.32,
        emission_strength=1.5,
    )
    focus_material = make_material(
        "Weighted_focus",
        (1.0, 0.72, 0.08, 1.0),
        roughness=0.35,
        emission_strength=1.2,
    )
    incident_path = make_curve_object(
        "Incident_beam",
        (source_position, crystal_position),
        beam_material,
        guides,
        bevel_depth_mm=BEAM_RADIUS_MM,
    )
    diffracted_path = make_curve_object(
        "Diffracted_beam",
        (crystal_position, sample_position),
        beam_material,
        guides,
        bevel_depth_mm=BEAM_RADIUS_MM,
    )
    add_arrowhead(
        "Incident_beam_direction",
        source_position,
        crystal_position,
        beam_material,
        guides,
    )
    add_arrowhead(
        "Diffracted_beam_direction",
        crystal_position,
        sample_position,
        beam_material,
        guides,
    )

    # The weighted focus is 10.06 mm before the nominal sample plane.  A small
    # marker records it without changing the nominal q used by the simulation.
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=32,
        ring_count=16,
        radius=3.2,
        location=focus_position,
    )
    focus_marker = bpy.context.object
    focus_marker.name = "Weighted_sagittal_focus"
    focus_marker.data.materials.append(focus_material)
    for owner in list(focus_marker.users_collection):
        owner.objects.unlink(focus_marker)
    guides.objects.link(focus_marker)

    fluorescence_path = make_curve_object(
        "Fluorescence_to_CZT",
        (sample_position, detector_position),
        fluorescence_material,
        guides,
        bevel_depth_mm=0.85,
    )
    add_arrowhead(
        "Fluorescence_direction",
        sample_position,
        detector_position,
        fluorescence_material,
        guides,
    )

    # The final lettering is added in Inkscape, so the Blender scene deliberately
    # contains no text objects.
    layout_centre = 0.5 * (source_position + sample_position)
    layout_centre.y -= 30.0
    camera = create_camera(scene, view, layout_centre)

    configure_city_studio_light(scene, find_city_exr())
    configure_render(scene, preview_path)
    frame_objects = [
        tube,
        slit_1,
        slit_2,
        crystal,
        sample,
        detector,
        incident_path,
        diffracted_path,
        fluorescence_path,
        focus_marker,
    ]
    frame_camera(scene, camera, frame_objects)

    scene["project"] = "PRISM"
    scene["geometry_source"] = str(geometry_summary)
    scene["fluorescence_geometry_source"] = str(
        fluorescence_baseline_path
    )
    scene["asset_source"] = str(source_blend)
    scene["energy_keV"] = float(geometry["energy_keV"])
    scene["crystal"] = str(geometry["crystal_label"])
    scene["source_to_crystal_mm"] = p_mm
    scene["crystal_to_sample_mm"] = q_mm
    scene["weighted_focus_distance_mm"] = float(geometry["focus_distance_mm"])
    scene["bragg_angle_deg"] = theta_deg
    scene["central_deflection_angle_deg"] = float(
        geometry["deflection_angle_deg"]
    )
    scene["sample_incident_angle_to_normal_deg"] = fluorescence[
        "incident_angle_to_normal_deg"
    ]
    scene["detector_takeoff_angle_to_normal_deg"] = fluorescence[
        "detector_takeoff_angle_to_normal_deg"
    ]
    scene["physical_reference_sample_to_czt_mm"] = fluorescence[
        "detector_distance_mm"
    ]
    scene["display_sample_to_czt_active_centre_mm"] = CZT_DISPLAY_DISTANCE_MM
    scene["background"] = "transparent RGBA"
    scene["annotations"] = "none; add final lettering externally in Inkscape"
    scene["tube_y_offset_mm"] = TUBE_Y_OFFSET_MM
    scene["arrowhead_beam_fraction"] = 0.5
    scene["arrowhead_display_scale"] = ARROWHEAD_SCALE
    scene["sample_display_dimensions_mm"] = SAMPLE_DISPLAY_DIMENSIONS_MM
    scene["camera_clip_end_mm"] = camera.data.clip_end
    scene["general_visual_scale"] = general_scale
    scene["scaling_strategy"] = (
        "Global scale derived from source-crystal arm; exact object-dependent "
        "reconstruction for Ge(880). Sample holder and legacy CZT housing "
        "remain illustrative/not to scale."
    )
    scene["studio_light"] = str(find_city_exr())

    # Fail loudly if a later edit breaks the central geometry.
    source_crystal_distance = (crystal_position - source_position).length
    crystal_sample_distance = (sample.location - crystal.location).length
    # Object transforms are stored as 32-bit floats by Blender, so sub-micron
    # agreement is the meaningful tolerance for this millimetre-scale scene.
    if not math.isclose(source_crystal_distance, p_mm, abs_tol=1.0e-3):
        raise AssertionError("Source-crystal distance does not match WP1")
    if not math.isclose(crystal_sample_distance, q_mm, abs_tol=1.0e-3):
        raise AssertionError("Crystal-sample distance does not match WP1")
    if not math.isclose(tube.location.y, TUBE_Y_OFFSET_MM, abs_tol=1.0e-5):
        raise AssertionError("Tube Y offset does not match the beam alignment")
    for actual, expected in zip(
        sample.dimensions,
        SAMPLE_DISPLAY_DIMENSIONS_MM,
        strict=True,
    ):
        if not math.isclose(actual, expected, abs_tol=1.0e-4):
            raise AssertionError("Sample display dimensions are inconsistent")
    if not math.isclose(camera.data.clip_end, 3000.0, abs_tol=1.0e-5):
        raise AssertionError("Camera clip end is not 3000 mm")
    arrow_specs = (
        ("Incident_beam_direction", source_position, crystal_position),
        ("Diffracted_beam_direction", crystal_position, sample_position),
        ("Fluorescence_direction", sample_position, detector_position),
    )
    for arrow_name, start, end in arrow_specs:
        arrow = bpy.data.objects[arrow_name]
        if (arrow.location - start.lerp(end, 0.5)).length > 1.0e-4:
            raise AssertionError(f"{arrow_name} is not at the beam midpoint")
        if any(
            not math.isclose(value, ARROWHEAD_SCALE, abs_tol=1.0e-5)
            for value in arrow.scale
        ):
            raise AssertionError(f"{arrow_name} is not scaled x2")

    actual_detector_direction = (detector_position - sample_position).normalized()
    actual_detector_distance = (detector_position - sample_position).length
    detector_face_normal = (
        detector.matrix_world.to_3x3() @ Vector((0.0, 0.0, 1.0))
    ).normalized()
    detector_channel_axis = (
        detector.matrix_world.to_3x3() @ Vector((1.0, 0.0, 0.0))
    ).normalized()

    def angle_degrees(first: Vector, second: Vector) -> float:
        cosine = max(-1.0, min(1.0, first.normalized().dot(second.normalized())))
        return math.degrees(math.acos(cosine))

    actual_incidence = angle_degrees(direction_to_crystal, sample_normal)
    actual_takeoff = angle_degrees(actual_detector_direction, sample_normal)
    if not math.isclose(
        actual_incidence,
        fluorescence["incident_angle_to_normal_deg"],
        abs_tol=1.0e-4,
    ):
        raise AssertionError("Sample incidence angle does not match baseline")
    if not math.isclose(
        actual_takeoff,
        fluorescence["detector_takeoff_angle_to_normal_deg"],
        abs_tol=1.0e-4,
    ):
        raise AssertionError("Detector take-off angle does not match baseline")
    if not math.isclose(
        actual_detector_distance,
        CZT_DISPLAY_DISTANCE_MM,
        abs_tol=1.0e-3,
    ):
        raise AssertionError("Displayed sample-CZT distance is inconsistent")
    if angle_degrees(detector_face_normal, -actual_detector_direction) > 1.0e-3:
        raise AssertionError("CZT active face is not aimed at the sample")
    if abs(detector_channel_axis.z) > 1.0e-4:
        raise AssertionError("CZT channel row is not horizontal in the bench plane")
    detector_to_camera = (camera.location - detector_position).normalized()
    if detector_face_normal.dot(detector_to_camera) <= 0.0:
        raise AssertionError("The camera cannot see the CZT active face")
    if not scene.render.film_transparent:
        raise AssertionError("The output background is not transparent")
    if any(obj.type == "FONT" for obj in scene.objects):
        raise AssertionError("The scene must not contain text objects")

    return scene, geometry, fluorescence


def print_report(
    scene: bpy.types.Scene,
    geometry: dict[str, float | str],
    fluorescence: dict[str, float],
    output_path: Path,
    preview_path: Path | None,
) -> None:
    report = {
        "output_blend": str(output_path),
        "preview_png": str(preview_path) if preview_path else None,
        "blender_version": bpy.app.version_string,
        "studio_light": scene["studio_light"],
        "transparent_background": bool(scene.render.film_transparent),
        "text_object_count": sum(
            obj.type == "FONT" for obj in scene.objects
        ),
        "tube_y_offset_mm": scene["tube_y_offset_mm"],
        "arrowheads": {
            "beam_fraction": scene["arrowhead_beam_fraction"],
            "display_scale": scene["arrowhead_display_scale"],
        },
        "camera_clip_end_mm": scene["camera_clip_end_mm"],
        "sample_display_dimensions_mm": list(
            scene["sample_display_dimensions_mm"]
        ),
        "general_visual_scale": scene["general_visual_scale"],
        "source_to_crystal_mm": geometry["source_to_crystal_mm"],
        "crystal_to_sample_mm": geometry["crystal_to_sample_mm"],
        "weighted_focus_distance_mm": geometry["focus_distance_mm"],
        "bragg_angle_deg": geometry["bragg_angle_deg"],
        "central_deflection_angle_deg": geometry["deflection_angle_deg"],
        "fluorescence_geometry": {
            "sample_thickness_um": fluorescence["sample_thickness_um"],
            "incident_angle_to_normal_deg": fluorescence[
                "incident_angle_to_normal_deg"
            ],
            "detector_takeoff_angle_to_normal_deg": fluorescence[
                "detector_takeoff_angle_to_normal_deg"
            ],
            "detector_reference_active_mm": [
                fluorescence["detector_active_width_mm"],
                fluorescence["detector_active_height_mm"],
                fluorescence["detector_thickness_mm"],
            ],
            "physical_reference_sample_to_czt_mm": fluorescence[
                "detector_distance_mm"
            ],
            "display_sample_to_czt_active_centre_mm": CZT_DISPLAY_DISTANCE_MM,
            "legacy_czt_asset_not_to_scale": True,
            "display_side": "opposite side of the sample beam",
            "channel_row": "horizontal in the optical-bench plane",
        },
        "crystal": {
            "label": geometry["crystal_label"],
            "width_sagittal_mm": geometry["crystal_width_mm"],
            "length_tangential_mm": geometry["crystal_length_mm"],
            "thickness_mm": geometry["crystal_thickness_mm"],
            "radius_mm": geometry["crystal_radius_mm"],
        },
    }
    print("PRISM_SETUP_REPORT")
    print(json.dumps(report, indent=2, sort_keys=True))


def main() -> None:
    args = parse_arguments()
    source_blend = require_file(args.source, "Source blend")
    geometry_summary = require_file(args.geometry_summary, "WP1 geometry summary")
    fluorescence_baseline_path = require_file(
        args.fluorescence_baseline,
        "Fluorescence baseline",
    )
    output_path = args.output.expanduser().resolve()
    preview_path = args.preview.expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    preview_path.parent.mkdir(parents=True, exist_ok=True)

    scene, geometry, fluorescence = build_scene(
        source_blend=source_blend,
        geometry_summary=geometry_summary,
        fluorescence_baseline_path=fluorescence_baseline_path,
        preview_path=preview_path,
    )
    rendered_preview: Path | None = None
    if not args.no_render:
        bpy.context.window.scene = scene
        bpy.ops.render.render(write_still=True)
        rendered_preview = preview_path

    # This script owns its generated target, so avoid producing a .blend1 on
    # every reproducible rebuild.
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(output_path))

    print_report(
        scene,
        geometry,
        fluorescence,
        output_path,
        rendered_preview,
    )


if __name__ == "__main__":
    main()
