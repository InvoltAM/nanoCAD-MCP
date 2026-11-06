"""Declarative definitions for all 207 MCP tools.

Each tool is defined as a dict with name, description, properties, and required fields.
Handlers are bound at runtime by _bind_handlers() after use case initialization.
"""

from __future__ import annotations

from typing import Any

# Type aliases for brevity — used inline in ~200+ property schemas
S: str = "string"
N: str = "number"
B: str = "boolean"
I: str = "integer"
OBJ: str = "object"
S2: dict[str, str] = {"type": S}

# ── Mode classification for capability discovery ──────────────
# Tools work in different connection modes:
#   requires_mode=None  — always available, no CAD needed
#   requires_mode="com" — works with basic COM bridge
#   requires_mode="full" — requires .NET engine (HTTP bridge, default)
_OFFLINE_TOOLS: set[str] = {
    "health_check",
    "get_system_info",
    # Parametric design tools (server-side only, no CAD needed)
    "set_parameter",
    "get_parameter",
    "list_parameters",
    "delete_parameter",
    "evaluate_expression",
    "resolve_value",
    "load_design_table",
    "apply_design_row",
    # History / model regeneration (server-side, no CAD needed)
    "record_tool_call",
    "get_history",
    "delete_history_entry",
    "clear_history",
    "replay_history",
    # Configuration management (server-side, no CAD needed)
    "save_configuration",
    "load_configuration",
    "list_configurations",
    "delete_configuration",
}

_COM_TOOLS: set[str] = {
    # Entity creation (COM fallback in CadRepository)
    "create_line",
    "create_circle",
    "create_arc",
    "create_polyline",
    "create_text",
    "create_point",
    "create_rectangle",
    # Entity manipulation
    "delete_entity",
    "get_entity",
    # Layer
    "get_layers",
    "create_layer",
    "set_current_layer",
    # Document
    "get_document_info",
    "save_document",
    "export_pdf",
    "zoom_extents",
    # System
    "get_system_variable",
    "set_system_variable",
}

# All 207 tool definitions in order
TOOL_DEFS: list[dict[str, Any]] = [
    # ── Health & System ───────────────────────────────────────
    {
        "name": "health_check",
        "description": "Check if nanoCAD is available",
        "properties": {},
        "required": [],
    },
    {
        "name": "get_system_info",
        "description": "Get nanoCAD version and system info",
        "properties": {},
        "required": [],
    },
    {
        "name": "get_system_fonts",
        "description": "Get all available fonts in the system",
        "properties": {},
        "required": [],
    },
    # ── 2D Primitives ─────────────────────────────────────────
    {
        "name": "create_line",
        "description": "Create a line segment from (x1,y1) to (x2,y2)",
        "properties": {
            "x1": {"type": N},
            "y1": {"type": N},
            "x2": {"type": N},
            "y2": {"type": N},
            "layer": S2,
        },
        "required": ["x1", "y1", "x2", "y2"],
    },
    {
        "name": "create_circle",
        "description": "Create a circle by center (cx,cy) and radius",
        "properties": {
            "cx": {"type": N},
            "cy": {"type": N},
            "radius": {"type": N},
            "layer": S2,
        },
        "required": ["cx", "cy", "radius"],
    },
    {
        "name": "create_arc",
        "description": "Create an arc (angles in degrees)",
        "properties": {
            "cx": {"type": N},
            "cy": {"type": N},
            "radius": {"type": N},
            "start_angle": {"type": N},
            "end_angle": {"type": N},
            "layer": S2,
        },
        "required": ["cx", "cy", "radius", "start_angle", "end_angle"],
    },
    {
        "name": "create_polyline",
        "description": "Create a polyline from vertices",
        "properties": {
            "vertices": {
                "type": "array",
                "items": {"type": "array", "items": {"type": N}, "minItems": 2, "maxItems": 2},
            },
            "closed": {"type": B},
            "layer": S2,
        },
        "required": ["vertices"],
    },
    {
        "name": "create_rectangle",
        "description": "Create a rectangle from corner point with width and height",
        "properties": {
            "x1": {"type": N},
            "y1": {"type": N},
            "x2": {"type": N},
            "y2": {"type": N},
            "layer": S2,
        },
        "required": ["x1", "y1", "x2", "y2"],
    },
    {
        "name": "create_text",
        "description": "Create single-line text at (x,y) with height and content",
        "properties": {
            "x": {"type": N},
            "y": {"type": N},
            "content": {"type": S},
            "height": {"type": N},
            "rotation": {"type": N},
            "layer": S2,
        },
        "required": ["x", "y", "content", "height"],
    },
    {
        "name": "create_mtext",
        "description": "Create multi-line text (requires .NET engine)",
        "properties": {
            "x1": {"type": N},
            "y1": {"type": N},
            "x2": {"type": N},
            "y2": {"type": N},
            "content": {"type": S},
            "height": {"type": N},
            "layer": S2,
        },
        "required": ["x1", "y1", "x2", "y2", "content", "height"],
    },
    {
        "name": "create_point",
        "description": "Create a point entity at (x,y) coordinates",
        "properties": {"x": {"type": N}, "y": {"type": N}, "layer": S2},
        "required": ["x", "y"],
    },
    {
        "name": "create_ellipse",
        "description": "Create an ellipse (requires .NET engine)",
        "properties": {
            "cx": {"type": N},
            "cy": {"type": N},
            "major_axis_x": {"type": N},
            "major_axis_y": {"type": N},
            "radius_ratio": {"type": N},
            "layer": S2,
        },
        "required": ["cx", "cy", "major_axis_x", "major_axis_y"],
    },
    {
        "name": "create_spline",
        "description": "Create a spline (requires .NET engine)",
        "properties": {
            "fit_points": {
                "type": "array",
                "items": {"type": "array", "items": {"type": N}, "minItems": 2, "maxItems": 2},
            },
            "degree": {"type": I},
            "closed": {"type": B},
            "layer": S2,
        },
        "required": ["fit_points"],
    },
    {
        "name": "delete_entity",
        "description": "Delete an entity by handle",
        "properties": {"handle": {"type": S}},
        "required": ["handle"],
    },
    # ── Entity Transformations ────────────────────────────────
    {
        "name": "move_entity",
        "description": "Move entity by delta (requires .NET engine)",
        "properties": {"handle": {"type": S}, "dx": {"type": N}, "dy": {"type": N}},
        "required": ["handle", "dx", "dy"],
    },
    {
        "name": "copy_entity",
        "description": "Copy entity (requires .NET engine)",
        "properties": {"handle": {"type": S}},
        "required": ["handle"],
    },
    {
        "name": "rotate_entity",
        "description": "Rotate entity (requires .NET engine)",
        "properties": {"handle": {"type": S}, "angle": {"type": N}},
        "required": ["handle", "angle"],
    },
    {
        "name": "scale_entity",
        "description": "Scale entity (requires .NET engine)",
        "properties": {
            "handle": {"type": S},
            "factor": {"type": N},
            "cx": {"type": N},
            "cy": {"type": N},
        },
        "required": ["handle", "factor"],
    },
    {
        "name": "mirror_entity",
        "description": "Mirror entity across line (requires .NET engine)",
        "properties": {
            "handle": {"type": S},
            "p1_x": {"type": N},
            "p1_y": {"type": N},
            "p2_x": {"type": N},
            "p2_y": {"type": N},
        },
        "required": ["handle", "p1_x", "p1_y", "p2_x", "p2_y"],
    },
    {
        "name": "stretch_entity",
        "description": "Stretch entity by delta (requires .NET engine)",
        "properties": {"handle": {"type": S}, "dx": {"type": N}, "dy": {"type": N}},
        "required": ["handle", "dx", "dy"],
    },
    {
        "name": "explode_entity",
        "description": "Explode entity into components (requires .NET engine)",
        "properties": {"handle": {"type": S}},
        "required": ["handle"],
    },
    {
        "name": "divide_entity",
        "description": "Divide entity into segments (requires .NET engine)",
        "properties": {"handle": {"type": S}, "segments": {"type": I}},
        "required": ["handle", "segments"],
    },
    {
        "name": "measure_entity",
        "description": "Place points along entity at intervals (requires .NET engine)",
        "properties": {"handle": {"type": S}, "distance": {"type": N}},
        "required": ["handle", "distance"],
    },
    {
        "name": "array_3d",
        "description": "Create 3D array of entity (requires .NET engine)",
        "properties": {
            "handle": {"type": S},
            "count_x": {"type": I},
            "count_y": {"type": I},
            "count_z": {"type": I},
            "spacing_x": {"type": N},
            "spacing_y": {"type": N},
            "spacing_z": {"type": N},
        },
        "required": ["handle", "count_x"],
    },
    {
        "name": "align_3d",
        "description": "Align entity from one coordinate system to another (requires .NET engine)",
        "properties": {
            "handle": {"type": S},
            "src_p1_x": {"type": N},
            "src_p1_y": {"type": N},
            "src_p1_z": {"type": N},
            "src_p2_x": {"type": N},
            "src_p2_y": {"type": N},
            "src_p2_z": {"type": N},
            "src_p3_x": {"type": N},
            "src_p3_y": {"type": N},
            "src_p3_z": {"type": N},
            "dst_p1_x": {"type": N},
            "dst_p1_y": {"type": N},
            "dst_p1_z": {"type": N},
            "dst_p2_x": {"type": N},
            "dst_p2_y": {"type": N},
            "dst_p2_z": {"type": N},
            "dst_p3_x": {"type": N},
            "dst_p3_y": {"type": N},
            "dst_p3_z": {"type": N},
        },
        "required": [
            "handle",
            "src_p1_x",
            "src_p1_y",
            "src_p1_z",
            "dst_p1_x",
            "dst_p1_y",
            "dst_p1_z",
        ],
    },
    {
        "name": "mirror_3d",
        "description": "Mirror entity across 3D plane (requires .NET engine)",
        "properties": {
            "handle": {"type": S},
            "p1_x": {"type": N},
            "p1_y": {"type": N},
            "p1_z": {"type": N},
            "p2_x": {"type": N},
            "p2_y": {"type": N},
            "p2_z": {"type": N},
            "p3_x": {"type": N},
            "p3_y": {"type": N},
            "p3_z": {"type": N},
        },
        "required": [
            "handle",
            "p1_x",
            "p1_y",
            "p1_z",
            "p2_x",
            "p2_y",
            "p2_z",
            "p3_x",
            "p3_y",
            "p3_z",
        ],
    },
    # ── Layers ────────────────────────────────────────────────
    {
        "name": "get_linetypes",
        "description": "Get all linetypes in the drawing",
        "properties": {},
        "required": [],
    },
    {
        "name": "create_layer",
        "description": "Create a new layer with specified name",
        "properties": {"name": {"type": S}},
        "required": ["name"],
    },
    {
        "name": "get_layers",
        "description": "Get list of all layers in the drawing",
        "properties": {},
        "required": [],
    },
    {
        "name": "set_current_layer",
        "description": "Set the current active layer by name",
        "properties": {"name": {"type": S}},
        "required": ["name"],
    },
    {
        "name": "set_layer_state",
        "description": "Change layer state (requires .NET engine)",
        "properties": {
            "name": {"type": S},
            "on": {"type": B},
            "frozen": {"type": B},
            "locked": {"type": B},
        },
        "required": ["name"],
    },
    {
        "name": "delete_layer",
        "description": "Delete a layer (requires .NET engine)",
        "properties": {"name": {"type": S}},
        "required": ["name"],
    },
    {
        "name": "layer_isolate",
        "description": "Isolate a layer - turn off all others (requires .NET engine)",
        "properties": {"name": S2},
        "required": ["name"],
    },
    {
        "name": "layer_off",
        "description": "Turn off a layer (requires .NET engine)",
        "properties": {"name": S2},
        "required": ["name"],
    },
    {
        "name": "layer_freeze",
        "description": "Freeze a layer (requires .NET engine)",
        "properties": {"name": S2},
        "required": ["name"],
    },
    {
        "name": "layer_on_all",
        "description": "Turn on all layers (requires .NET engine)",
        "properties": {},
        "required": [],
    },
    {
        "name": "layer_thaw_all",
        "description": "Thaw (unfreeze) all layers (requires .NET engine)",
        "properties": {},
        "required": [],
    },
    # ── Blocks ────────────────────────────────────────────────
    {
        "name": "get_blocks",
        "description": "Get all blocks (requires .NET engine)",
        "properties": {},
        "required": [],
    },
    {
        "name": "insert_block",
        "description": "Insert a block reference (requires .NET engine)",
        "properties": {
            "name": {"type": S},
            "x": {"type": N},
            "y": {"type": N},
            "scale": {"type": N},
            "rotation": {"type": N},
        },
        "required": ["name", "x", "y"],
    },
    {
        "name": "create_block",
        "description": "Create a block from entities (requires .NET engine)",
        "properties": {
            "name": {"type": S},
            "handles": {"type": "array", "items": {"type": S}},
            "base_x": {"type": N},
            "base_y": {"type": N},
        },
        "required": ["name", "handles"],
    },
    {
        "name": "explode_block",
        "description": "Explode a block definition into model space (requires .NET engine)",
        "properties": {"name": {"type": S}},
        "required": ["name"],
    },
    {
        "name": "delete_block",
        "description": "Delete a block definition (requires .NET engine)",
        "properties": {"name": S2},
        "required": ["name"],
    },
    {
        "name": "get_block_entities",
        "description": "Get all entities within a block definition (requires .NET engine)",
        "properties": {"name": S2},
        "required": ["name"],
    },
    # ── Document ──────────────────────────────────────────────
    {
        "name": "get_document_info",
        "description": "Get current document info",
        "properties": {},
        "required": [],
    },
    {
        "name": "save_document",
        "description": "Save current document to disk (optionally to new path)",
        "properties": {"path": {"type": S}},
        "required": [],
    },
    {
        "name": "export_pdf",
        "description": "Export current document to PDF file at specified path",
        "properties": {"path": {"type": S}},
        "required": ["path"],
    },
    {
        "name": "export_dwg",
        "description": "Export as DWG (requires .NET engine)",
        "properties": {"path": {"type": S}},
        "required": ["path"],
    },
    {
        "name": "export_dxf",
        "description": "Export as DXF (requires .NET engine)",
        "properties": {"path": {"type": S}},
        "required": ["path"],
    },
    {
        "name": "export_step",
        "description": "Export to STEP file (requires .NET engine)",
        "properties": {"path": {"type": S}},
        "required": ["path"],
    },
    {
        "name": "import_step",
        "description": "Import STEP file (requires .NET engine)",
        "properties": {"path": {"type": S}},
        "required": ["path"],
    },
    {
        "name": "export_stl",
        "description": "Export current document or selection to STL (requires .NET engine)",
        "properties": {"path": S2, "binary": {"type": B}},
        "required": ["path"],
    },
    {
        "name": "new_document",
        "description": "Create a new empty document (requires .NET engine)",
        "properties": {"template": S2},
        "required": [],
    },
    {
        "name": "create_project",
        "description": (
            "Create a new DWG project file with the given filename in the given "
            "directory. Directory is created if missing. .dwg extension is added "
            "automatically. Optionally use a .dwt template. Returns the full file path."
        ),
        "properties": {
            "filename": S2,
            "directory": S2,
            "template": S2,
        },
        "required": ["filename", "directory"],
    },
    {
        "name": "save_project",
        "description": (
            "Save the current drawing to a specific filename in a specific "
            "directory (overwrites if file exists). Directory is created if "
            "missing. .dwg extension is added automatically."
        ),
        "properties": {
            "filename": S2,
            "directory": S2,
        },
        "required": ["filename", "directory"],
    },
    {
        "name": "open_document",
        "description": "Open an existing DWG document (requires .NET engine)",
        "properties": {"path": S2},
        "required": ["path"],
    },
    {
        "name": "close_document",
        "description": "Close the current document (requires .NET engine)",
        "properties": {},
        "required": [],
    },
    {
        "name": "zoom_extents",
        "description": "Zoom the view to show all drawing entities",
        "properties": {},
        "required": [],
    },
    {
        "name": "undo",
        "description": "Undo last operation (requires .NET engine)",
        "properties": {},
        "required": [],
    },
    {
        "name": "redo",
        "description": "Redo last undone operation (requires .NET engine)",
        "properties": {},
        "required": [],
    },
    {
        "name": "purge",
        "description": "Purge unused named objects (requires .NET engine)",
        "properties": {},
        "required": [],
    },
    # ── System ────────────────────────────────────────────────
    {
        "name": "execute_command",
        "description": "Execute a raw CAD command (requires .NET engine)",
        "properties": {"command": {"type": S}},
        "required": ["command"],
    },
    {
        "name": "get_system_variable",
        "description": "Get value of a CAD system variable by name",
        "properties": {"name": {"type": S}},
        "required": ["name"],
    },
    {
        "name": "set_system_variable",
        "description": "Set a CAD system variable to specified value",
        "properties": {"name": {"type": S}, "value": {"type": S}},
        "required": ["name", "value"],
    },
    # ── 3D Solids ─────────────────────────────────────────────
    {
        "name": "create_box",
        "description": "Create a 3D box by corner point and dimensions (width,depth,height)",
        "properties": {"x": {"type": N}, "y": {"type": N}, "z": {"type": N}},
        "required": ["x", "y", "z"],
    },
    {
        "name": "create_sphere",
        "description": "Create a 3D sphere by center point and radius",
        "properties": {"radius": {"type": N}},
        "required": ["radius"],
    },
    {
        "name": "create_cylinder",
        "description": "Create a 3D cylinder by center point, radius, and height",
        "properties": {"radius": {"type": N}, "height": {"type": N}},
        "required": ["radius", "height"],
    },
    {
        "name": "create_cone",
        "description": "Create a 3D cone by center point, base radius, and height",
        "properties": {"radius_bottom": {"type": N}, "height": {"type": N}},
        "required": ["radius_bottom", "height"],
    },
    {
        "name": "create_torus",
        "description": "Create a 3D torus by center point, major and minor radii",
        "properties": {"major_radius": {"type": N}, "minor_radius": {"type": N}},
        "required": ["major_radius", "minor_radius"],
    },
    {
        "name": "create_wedge",
        "description": "Create a 3D wedge by corner point and dimensions (width,depth,height)",
        "properties": {"x": {"type": N}, "y": {"type": N}, "z": {"type": N}},
        "required": ["x", "y", "z"],
    },
    {
        "name": "create_pyramid",
        "description": "Create a 3D pyramid by base center, base radius, and height",
        "properties": {"height": {"type": N}, "sides": {"type": I}, "radius": {"type": N}},
        "required": ["height", "sides", "radius"],
    },
    # ── Boolean Operations ────────────────────────────────────
    {
        "name": "boolean_union",
        "description": "Boolean union: merge two overlapping 3D solids into one",
        "properties": {"handle1": S2, "handle2": S2},
        "required": ["handle1", "handle2"],
    },
    {
        "name": "boolean_subtract",
        "description": "Subtract second solid from first",
        "properties": {"handle1": S2, "handle2": S2},
        "required": ["handle1", "handle2"],
    },
    {
        "name": "boolean_intersect",
        "description": "Boolean intersection: keep only overlapping volume of two solids",
        "properties": {"handle1": S2, "handle2": S2},
        "required": ["handle1", "handle2"],
    },
    # ── 3D Operations ─────────────────────────────────────────
    {
        "name": "extrude_solid",
        "description": "Extrude a 2D profile into 3D",
        "properties": {"handle": S2, "height": {"type": N}, "taper_angle": {"type": N}},
        "required": ["handle", "height"],
    },
    {
        "name": "revolve_solid",
        "description": "Revolve a 2D profile around axis",
        "properties": {
            "handle": S2,
            "axis_x": {"type": N},
            "axis_y": {"type": N},
            "axis_z": {"type": N},
            "dir_x": {"type": N},
            "dir_y": {"type": N},
            "dir_z": {"type": N},
            "angle": {"type": N},
        },
        "required": ["handle", "axis_x", "axis_y", "axis_z", "dir_x", "dir_y", "dir_z", "angle"],
    },
    {
        "name": "sweep_solid",
        "description": "Sweep a profile along a path (requires .NET engine)",
        "properties": {"profile_handle": S2, "path_handle": S2},
        "required": ["profile_handle", "path_handle"],
    },
    {
        "name": "loft_solid",
        "description": "Loft through cross-sections (requires .NET engine)",
        "properties": {"section_handles": {"type": "array", "items": S2}},
        "required": ["section_handles"],
    },
    {
        "name": "fillet_edge",
        "description": "Fillet edges of a 3D solid (requires .NET engine)",
        "properties": {"handle": S2, "radius": {"type": N}},
        "required": ["handle"],
    },
    {
        "name": "chamfer_edge",
        "description": "Chamfer edges of a 3D solid (requires .NET engine)",
        "properties": {"handle": S2, "dist1": {"type": N}, "dist2": {"type": N}},
        "required": ["handle"],
    },
    {
        "name": "move_solid",
        "description": "Move a 3D solid by delta (requires .NET engine)",
        "properties": {"handle": S2, "dx": {"type": N}, "dy": {"type": N}, "dz": {"type": N}},
        "required": ["handle", "dx", "dy"],
    },
    {
        "name": "rotate_solid",
        "description": "Rotate a 3D solid around an axis (requires .NET engine)",
        "properties": {
            "handle": S2,
            "angle": {"type": N},
            "center_x": {"type": N},
            "center_y": {"type": N},
            "center_z": {"type": N},
            "axis_x": {"type": N},
            "axis_y": {"type": N},
            "axis_z": {"type": N},
        },
        "required": [
            "handle",
            "angle",
            "center_x",
            "center_y",
            "center_z",
            "axis_x",
            "axis_y",
            "axis_z",
        ],
    },
    {
        "name": "set_3d_view",
        "description": "Set 3D viewport direction (top,front,right,isometric,etc.)",
        "properties": {"direction": S2, "render_mode": S2},
        "required": ["direction"],
    },
    {
        "name": "get_solid_properties",
        "description": "Get volume, surface area, and bounding box of a 3D solid",
        "properties": {"handle": S2},
        "required": ["handle"],
    },
    # ── Symbols (MultiCAD) ───────────────────────────────────
    {
        "name": "create_roughness",
        "description": "Create roughness symbol (GOST)",
        "properties": {"value": S2, "angle": S2, "allowance": S2, "type": {"type": I}},
        "required": [],
    },
    {
        "name": "create_old_roughness",
        "description": "Create old-style roughness symbol",
        "properties": {
            "value": S2,
            "angle": S2,
            "method": S2,
            "companion_mirror": {"type": B},
            "surf_pos": S2,
        },
        "required": [],
    },
    {
        "name": "create_tolerance",
        "description": "Create geometric tolerance frame",
        "properties": {
            "type1": S2,
            "value1": S2,
            "letters1": S2,
            "type2": S2,
            "value2": S2,
            "letters2": S2,
            "text": S2,
        },
        "required": [],
    },
    {
        "name": "create_datum",
        "description": "Create datum identifier symbol",
        "properties": {"letter": S2},
        "required": [],
    },
    {
        "name": "create_weld",
        "description": "Create ISO welding symbol at (x,y) with type and size",
        "properties": {
            "swap_sides": {"type": B},
            "right_orientation": {"type": B},
            "length_above": S2,
            "length_below": S2,
        },
        "required": [],
    },
    {
        "name": "create_leader",
        "description": "Create leader/callout with text",
        "properties": {
            "arrow_x": S2,
            "arrow_y": S2,
            "bend_x": S2,
            "bend_y": S2,
            "shelf_x": S2,
            "shelf_y": S2,
            "text": S2,
            "text_below": S2,
        },
        "required": ["arrow_x", "arrow_y", "bend_x", "bend_y", "shelf_x", "shelf_y", "text"],
    },
    {
        "name": "create_note_comb",
        "description": "Create comb/ribbed callout",
        "properties": {"angle": S2, "text_size": S2, "first_line": S2, "second_line": S2},
        "required": [],
    },
    {
        "name": "create_dim_number",
        "description": "Create surface designation marker",
        "properties": {
            "x": S2,
            "y": S2,
            "arrow_x": S2,
            "arrow_y": S2,
            "text": S2,
            "index": {"type": I},
            "autonum": {"type": B},
        },
        "required": ["x", "y", "arrow_x", "arrow_y"],
    },
    {
        "name": "create_mleader",
        "description": "Create a multileader with arrow, leader, and text (requires .NET engine)",
        "properties": {
            "arrow_x": {"type": N},
            "arrow_y": {"type": N},
            "leader_x": {"type": N},
            "leader_y": {"type": N},
            "text": S2,
            "text_height": {"type": N},
            "layer": S2,
        },
        "required": ["arrow_x", "arrow_y", "leader_x", "leader_y", "text"],
    },
    # ── Tables ────────────────────────────────────────────────
    {
        "name": "create_table",
        "description": "Create a table at insertion point with specified rows and columns",
        "properties": {
            "rows": {"type": I},
            "columns": {"type": I},
            "row_height": S2,
            "column_width": S2,
            "cells": {
                "type": "array",
                "items": {
                    "type": OBJ,
                    "properties": {
                        "row_index": {"type": I},
                        "column_index": {"type": I},
                        "value": S2,
                    },
                },
            },
        },
        "required": [],
    },
    {
        "name": "edit_table_cell",
        "description": "Edit a table cell value (requires .NET engine)",
        "properties": {
            "handle": S2,
            "row_index": {"type": I},
            "column_index": {"type": I},
            "value": S2,
        },
        "required": ["handle", "row_index", "column_index", "value"],
    },
    {
        "name": "get_table_info",
        "description": "Get table info including rows, columns, cell values (requires .NET engine)",
        "properties": {
            "handle": S2,
        },
        "required": ["handle"],
    },
    {
        "name": "delete_table",
        "description": "Delete a table from the drawing (requires .NET engine)",
        "properties": {
            "handle": S2,
        },
        "required": ["handle"],
    },
    # ── Hatch ─────────────────────────────────────────────────
    {
        "name": "create_hatch",
        "description": "Create hatch pattern fill in a closed boundary",
        "properties": {
            "pattern": S2,
            "scale": S2,
            "boundary_handles": {"type": "array", "items": S2},
            "boundary_points": {
                "type": "array",
                "items": {"type": OBJ, "properties": {"x": S2, "y": S2}},
            },
        },
        "required": [],
    },
    {
        "name": "get_hatch_info",
        "description": "Get pattern name, scale, and angle of an existing hatch",
        "properties": {"handle": S2},
        "required": ["handle"],
    },
    {
        "name": "edit_hatch",
        "description": "Modify pattern, scale, or angle of an existing hatch",
        "properties": {"handle": S2, "pattern": S2, "scale": S2},
        "required": ["handle"],
    },
    # ── Dimensions ────────────────────────────────────────────
    {
        "name": "create_aligned_dimension",
        "description": "Create an aligned dimension between two points",
        "properties": {
            "x1": S2,
            "y1": S2,
            "x2": S2,
            "y2": S2,
            "dim_x": S2,
            "dim_y": S2,
            "layer": S2,
        },
        "required": ["x1", "y1", "x2", "y2", "dim_x", "dim_y"],
    },
    {
        "name": "create_rotated_dimension",
        "description": "Create a rotated dimension at specified angle",
        "properties": {
            "x1": S2,
            "y1": S2,
            "x2": S2,
            "y2": S2,
            "dim_x": S2,
            "dim_y": S2,
            "rotation": S2,
            "layer": S2,
        },
        "required": ["x1", "y1", "x2", "y2", "dim_x", "dim_y", "rotation"],
    },
    {
        "name": "create_radial_dimension",
        "description": "Create a radial dimension for a circle or arc",
        "properties": {"center_x": S2, "center_y": S2, "arc_x": S2, "arc_y": S2, "layer": S2},
        "required": ["center_x", "center_y", "arc_x", "arc_y"],
    },
    {
        "name": "create_diametric_dimension",
        "description": "Create diametric dimension",
        "properties": {"center_x": S2, "center_y": S2, "arc_x": S2, "arc_y": S2, "layer": S2},
        "required": ["center_x", "center_y", "arc_x", "arc_y"],
    },
    {
        "name": "create_angular_dimension",
        "description": "Create an angular dimension between two lines",
        "properties": {
            "center_x": S2,
            "center_y": S2,
            "p1_x": S2,
            "p1_y": S2,
            "p2_x": S2,
            "p2_y": S2,
            "layer": S2,
        },
        "required": ["center_x", "center_y", "p1_x", "p1_y", "p2_x", "p2_y"],
    },
    {
        "name": "create_ordinate_dimension",
        "description": "Create ordinate dimension",
        "properties": {
            "use_x_axis": {"type": B},
            "defining_x": S2,
            "defining_y": S2,
            "leader_x": S2,
            "leader_y": S2,
        },
        "required": ["use_x_axis", "defining_x", "defining_y", "leader_x", "leader_y"],
    },
    {
        "name": "create_linear_dimension",
        "description": "Create linear (horizontal or vertical) dimension (requires .NET engine)",
        "properties": {
            "x1": {"type": N},
            "y1": {"type": N},
            "x2": {"type": N},
            "y2": {"type": N},
            "dim_x": {"type": N},
            "dim_y": {"type": N},
            "direction": S2,
            "layer": S2,
        },
        "required": ["x1", "y1", "x2", "y2", "dim_x", "dim_y"],
    },
    # ── Measurements ──────────────────────────────────────────
    {
        "name": "get_distance",
        "description": "Measure distance between two points",
        "properties": {
            "x1": {"type": N},
            "y1": {"type": N},
            "z1": {"type": N},
            "x2": {"type": N},
            "y2": {"type": N},
            "z2": {"type": N},
        },
        "required": ["x1", "y1", "x2", "y2"],
    },
    {
        "name": "get_angle",
        "description": "Measure angle between two lines defined by three points",
        "properties": {
            "x1": {"type": N},
            "y1": {"type": N},
            "z1": {"type": N},
            "x2": {"type": N},
            "y2": {"type": N},
            "z2": {"type": N},
            "x3": {"type": N},
            "y3": {"type": N},
            "z3": {"type": N},
        },
        "required": ["x1", "y1", "x2", "y2", "x3", "y3"],
    },
    {
        "name": "get_area",
        "description": "Get area of a closed entity",
        "properties": {"handle": S2},
        "required": ["handle"],
    },
    {
        "name": "get_entity_info",
        "description": "Get detailed entity information",
        "properties": {"handle": S2},
        "required": ["handle"],
    },
    {
        "name": "get_all_entities",
        "description": "List all entities in model space",
        "properties": {},
        "required": [],
    },
    {
        "name": "get_entity",
        "description": "Get detailed information about a specific entity by handle",
        "properties": {"handle": S2},
        "required": ["handle"],
    },
    {
        "name": "get_entity_detail",
        "description": (
            "Get detailed entity info: geometry, area, length, radius, etc. (requires .NET engine)"
        ),
        "properties": {"handle": S2},
        "required": ["handle"],
    },
    # ── Trim / Extend / Offset ────────────────────────────────
    {
        "name": "trim_entity",
        "description": "Trim a curve at a cut point (requires .NET engine)",
        "properties": {
            "handle": S2,
            "cut_x": {"type": N},
            "cut_y": {"type": N},
            "keep_start": {"type": B},
        },
        "required": ["handle", "cut_x", "cut_y"],
    },
    {
        "name": "extend_entity",
        "description": "Extend a curve to a target point (requires .NET engine)",
        "properties": {"handle": S2, "end_x": {"type": N}, "end_y": {"type": N}},
        "required": ["handle", "end_x", "end_y"],
    },
    {
        "name": "offset_entity",
        "description": "Create offset curve(s) from a curve entity (requires .NET engine)",
        "properties": {"handle": S2, "distance": {"type": N}},
        "required": ["handle", "distance"],
    },
    # ── Primitives (additional) ───────────────────────────────
    {
        "name": "create_polygon",
        "description": "Create a polygon (requires .NET engine)",
        "properties": {
            "center_x": {"type": N},
            "center_y": {"type": N},
            "radius": {"type": N},
            "sides": {"type": I},
            "inscribed": {"type": B},
            "layer": S2,
        },
        "required": ["center_x", "center_y", "radius", "sides"],
    },
    {
        "name": "create_donut",
        "description": "Create a donut (requires .NET engine)",
        "properties": {
            "center_x": {"type": N},
            "center_y": {"type": N},
            "inner_radius": {"type": N},
            "outer_radius": {"type": N},
            "layer": S2,
        },
        "required": ["center_x", "center_y", "inner_radius", "outer_radius"],
    },
    {
        "name": "create_xline",
        "description": "Create an infinite construction line (requires .NET engine)",
        "properties": {
            "p1_x": {"type": N},
            "p1_y": {"type": N},
            "p2_x": {"type": N},
            "p2_y": {"type": N},
            "layer": S2,
        },
        "required": ["p1_x", "p1_y", "p2_x", "p2_y"],
    },
    {
        "name": "create_ray",
        "description": "Create a semi-infinite ray (requires .NET engine)",
        "properties": {
            "p1_x": {"type": N},
            "p1_y": {"type": N},
            "p2_x": {"type": N},
            "p2_y": {"type": N},
            "layer": S2,
        },
        "required": ["p1_x", "p1_y", "p2_x", "p2_y"],
    },
    # ── Selection ─────────────────────────────────────────────
    {
        "name": "select_entities",
        "description": "Select entities by type/layer/color filter (requires .NET engine)",
        "properties": {
            "entity_type": S2,
            "layer": S2,
            "color": {"type": N},
            "max_count": {"type": N},
        },
        "required": [],
    },
    {
        "name": "select_by_handles",
        "description": "Get details for a list of entity handles (requires .NET engine)",
        "properties": {"handles": {"type": "array", "items": {"type": S}}},
        "required": ["handles"],
    },
    # ── 2D Constraints ────────────────────────────────────────
    {
        "name": "constraint_parallel",
        "description": "Make two lines parallel (requires .NET engine)",
        "properties": {"handle1": S2, "handle2": S2},
        "required": ["handle1", "handle2"],
    },
    {
        "name": "constraint_coincident",
        "description": "Make two points coincident (requires .NET engine)",
        "properties": {"handle1": S2, "handle2": S2},
        "required": ["handle1", "handle2"],
    },
    {
        "name": "constraint_fix",
        "description": "Fix an entity in place (requires .NET engine)",
        "properties": {"handle": S2},
        "required": ["handle"],
    },
    {
        "name": "constraint_horizontal",
        "description": "Make a line horizontal (requires .NET engine)",
        "properties": {"handle": S2},
        "required": ["handle"],
    },
    {
        "name": "constraint_vertical",
        "description": "Make a line vertical (requires .NET engine)",
        "properties": {"handle": S2},
        "required": ["handle"],
    },
    {
        "name": "constraint_tangent",
        "description": "Make a line tangent to a circle/arc (requires .NET engine)",
        "properties": {"handle_line": S2, "handle_curve": S2},
        "required": ["handle_line", "handle_curve"],
    },
    {
        "name": "constraint_perpendicular",
        "description": "Make two lines perpendicular (requires .NET engine)",
        "properties": {"handle1": S2, "handle2": S2},
        "required": ["handle1", "handle2"],
    },
    {
        "name": "constraint_collinear",
        "description": "Make two lines collinear (requires .NET engine)",
        "properties": {"handle1": S2, "handle2": S2},
        "required": ["handle1", "handle2"],
    },
    {
        "name": "constraint_concentric",
        "description": "Make two circles/arcs concentric (requires .NET engine)",
        "properties": {"handle1": S2, "handle2": S2},
        "required": ["handle1", "handle2"],
    },
    {
        "name": "constraint_equal",
        "description": "Make two entities equal in length/radius (requires .NET engine)",
        "properties": {"handle1": S2, "handle2": S2},
        "required": ["handle1", "handle2"],
    },
    {
        "name": "constraint_symmetric",
        "description": "Make two entities symmetric about a line (requires .NET engine)",
        "properties": {"handle1": S2, "handle2": S2, "plane_handle": S2},
        "required": ["handle1", "handle2", "plane_handle"],
    },
    {
        "name": "constraint_distance",
        "description": "Set fixed distance between two entities (requires .NET engine)",
        "properties": {"handle1": S2, "handle2": S2, "distance": {"type": N}},
        "required": ["handle1", "handle2", "distance"],
    },
    # ── Assembly ──────────────────────────────────────────────
    {
        "name": "insert_part",
        "description": "Insert a part into the assembly (requires .NET engine)",
        "properties": {"block_name": S2, "x": {"type": N}, "y": {"type": N}, "z": {"type": N}},
        "required": ["block_name"],
    },
    {
        "name": "assembly_mate",
        "description": "Create mate constraint between two parts (requires .NET engine)",
        "properties": {"handle1": S2, "handle2": S2},
        "required": ["handle1", "handle2"],
    },
    {
        "name": "assembly_angle",
        "description": "Create angle constraint between two parts (requires .NET engine)",
        "properties": {"handle1": S2, "handle2": S2, "angle": {"type": N}},
        "required": ["handle1", "handle2", "angle"],
    },
    {
        "name": "assembly_tangent",
        "description": "Create tangent constraint between two parts (requires .NET engine)",
        "properties": {"handle1": S2, "handle2": S2},
        "required": ["handle1", "handle2"],
    },
    {
        "name": "assembly_symmetry",
        "description": "Create symmetry constraint (requires .NET engine)",
        "properties": {"handle1": S2, "handle2": S2, "plane_handle": S2},
        "required": ["handle1", "handle2", "plane_handle"],
    },
    # ── Sheet Metal ───────────────────────────────────────────
    {
        "name": "create_base_flange",
        "description": (
            "Create a base flange: rectangular plate extruded by thickness (requires .NET engine)"
        ),
        "properties": {
            "x": {"type": N},
            "y": {"type": N},
            "width": {"type": N},
            "length": {"type": N},
            "thickness": {"type": N},
        },
        "required": ["width", "length", "thickness"],
    },
    {
        "name": "create_edge_flange",
        "description": "Add an edge flange with bend radius (requires .NET engine)",
        "properties": {"base_handle": S2, "bend_radius": {"type": N}},
        "required": ["base_handle"],
    },
    {
        "name": "create_bend",
        "description": "Add a bend (fillet) to a solid edge (requires .NET engine)",
        "properties": {"handle": S2, "bend_radius": {"type": N}},
        "required": ["handle"],
    },
    {
        "name": "unfold_sheet_metal",
        "description": "Unfold 3D sheet metal to 2D flat pattern (requires .NET engine)",
        "properties": {"handle": S2, "x": {"type": N}, "y": {"type": N}},
        "required": ["handle"],
    },
    {
        "name": "create_base_plate",
        "description": "Create a base plate: simple rectangular extrusion (requires .NET engine)",
        "properties": {
            "x": {"type": N},
            "y": {"type": N},
            "width": {"type": N},
            "length": {"type": N},
            "thickness": {"type": N},
        },
        "required": ["width", "length", "thickness"],
    },
    # ── 3D Features ───────────────────────────────────────────
    {
        "name": "create_simple_hole",
        "description": "Create a simple hole in a 3D solid (requires .NET engine)",
        "properties": {
            "solid_handle": {"type": S},
            "diameter": {"type": N},
            "depth": {"type": N},
        },
        "required": ["solid_handle", "diameter", "depth"],
    },
    {
        "name": "create_threaded_hole",
        "description": "Create a threaded hole in a 3D solid (requires .NET engine)",
        "properties": {
            "solid_handle": {"type": S},
            "diameter": {"type": N},
            "depth": {"type": N},
        },
        "required": ["solid_handle", "diameter", "depth"],
    },
    {
        "name": "create_standard_hole",
        "description": "Create a standard hole (ISO/DIN) in a 3D solid (requires .NET engine)",
        "properties": {
            "solid_handle": {"type": S},
            "diameter": {"type": N},
            "depth": {"type": N},
            "standard": {"type": S},
        },
        "required": ["solid_handle", "diameter", "depth"],
    },
    {
        "name": "create_shell",
        "description": "Shell a 3D solid (hollow out with thickness) (requires .NET engine)",
        "properties": {
            "solid_handle": {"type": S},
            "thickness": {"type": N},
            "outward": {"type": B},
        },
        "required": ["solid_handle", "thickness"],
    },
    {
        "name": "create_mirror_feature",
        "description": "Mirror features of a 3D solid across a plane (requires .NET engine)",
        "properties": {
            "solid_handle": {"type": S},
            "plane_handle": {"type": S},
        },
        "required": ["solid_handle", "plane_handle"],
    },
    {
        "name": "create_circular_pattern",
        "description": "Create circular pattern of a feature (requires .NET engine)",
        "properties": {
            "solid_handle": {"type": S},
            "feature_handle": {"type": S},
            "count": {"type": I},
            "angle": {"type": N},
        },
        "required": ["solid_handle", "feature_handle", "count", "angle"],
    },
    {
        "name": "create_rectangular_pattern",
        "description": "Create rectangular pattern of a feature (requires .NET engine)",
        "properties": {
            "solid_handle": {"type": S},
            "feature_handle": {"type": S},
            "count_x": {"type": I},
            "spacing_x": {"type": N},
            "count_y": {"type": I},
            "spacing_y": {"type": N},
        },
        "required": [
            "solid_handle",
            "feature_handle",
            "count_x",
            "spacing_x",
            "count_y",
            "spacing_y",
        ],
    },
    {
        "name": "create_sketch",
        "description": "Create a planar sketch on a 3D solid (requires .NET engine)",
        "properties": {
            "solid_handle": {"type": S},
        },
        "required": ["solid_handle"],
    },
    {
        "name": "add_sketch_circle",
        "description": "Add a circle to a sketch (requires .NET engine)",
        "properties": {
            "sketch_handle": {"type": S},
            "cx": {"type": N},
            "cy": {"type": N},
            "cz": {"type": N},
            "radius": {"type": N},
        },
        "required": ["sketch_handle", "cx", "cy", "cz", "radius"],
    },
    {
        "name": "add_sketch_line",
        "description": "Add a line to a sketch (requires .NET engine)",
        "properties": {
            "sketch_handle": {"type": S},
            "x1": {"type": N},
            "y1": {"type": N},
            "z1": {"type": N},
            "x2": {"type": N},
            "y2": {"type": N},
            "z2": {"type": N},
        },
        "required": ["sketch_handle", "x1", "y1", "z1", "x2", "y2", "z2"],
    },
    {
        "name": "create_profile",
        "description": "Create a profile from a sketch (requires .NET engine)",
        "properties": {
            "sketch_handle": {"type": S},
        },
        "required": ["sketch_handle"],
    },
    {
        "name": "create_extrude_feature",
        "description": "Extrude a profile into a 3D feature (requires .NET engine)",
        "properties": {
            "solid_handle": {"type": S},
            "profile_handle": {"type": S},
            "height": {"type": N},
            "taper_angle": {"type": N},
            "direction": {"type": B},
        },
        "required": ["solid_handle", "profile_handle", "height"],
    },
    {
        "name": "create_revolve_feature",
        "description": "Revolve a profile around an axis (requires .NET engine)",
        "properties": {
            "solid_handle": {"type": S},
            "profile_handle": {"type": S},
            "axis_x": {"type": N},
            "axis_y": {"type": N},
            "axis_z": {"type": N},
            "dir_x": {"type": N},
            "dir_y": {"type": N},
            "dir_z": {"type": N},
            "angle": {"type": N},
        },
        "required": [
            "solid_handle",
            "profile_handle",
            "axis_x",
            "axis_y",
            "axis_z",
            "dir_x",
            "dir_y",
            "dir_z",
            "angle",
        ],
    },
    # ── Feature Tree Management (Phase P2) ────────────────
    {
        "name": "get_feature_list",
        "description": "Get list of parametric features on a 3D solid (requires .NET engine)",
        "properties": {"solid_handle": {"type": S}},
        "required": ["solid_handle"],
    },
    {
        "name": "suppress_feature",
        "description": "Suppress (disable) a parametric feature by handle (requires .NET engine)",
        "properties": {"feature_handle": {"type": S}},
        "required": ["feature_handle"],
    },
    {
        "name": "unsuppress_feature",
        "description": "Unsuppress (resume) a suppressed parametric feature (requires .NET engine)",
        "properties": {"feature_handle": {"type": S}},
        "required": ["feature_handle"],
    },
    {
        "name": "edit_feature_parameter",
        "description": "Edit a parameter of a parametric feature (requires .NET engine)",
        "properties": {
            "feature_handle": {"type": S},
            "param_name": {"type": S},
            "value": {"type": N},
        },
        "required": ["feature_handle", "param_name", "value"],
    },
    {
        "name": "delete_feature",
        "description": "Delete a parametric feature from the solid (requires .NET engine)",
        "properties": {"feature_handle": {"type": S}},
        "required": ["feature_handle"],
    },
    # ── Helix ──────────────────────────────────────────────
    {
        "name": "create_helix",
        "description": "Create a helix/spiral (requires .NET engine)",
        "properties": {
            "center_x": {"type": N},
            "center_y": {"type": N},
            "center_z": {"type": N},
            "start_radius": {"type": N},
            "end_radius": {"type": N},
            "height": {"type": N},
            "turns": {"type": N},
            "layer": S2,
        },
        "required": [],
    },
    # ── Region ─────────────────────────────────────────────
    {
        "name": "create_region",
        "description": "Create a region from closed curves (requires .NET engine)",
        "properties": {
            "curve_handles": {"type": "array", "items": S2},
        },
        "required": ["curve_handles"],
    },
    # ── Boundary ───────────────────────────────────────────
    {
        "name": "create_boundary",
        "description": "Create a boundary polyline around a point (requires .NET engine)",
        "properties": {
            "point_x": {"type": N},
            "point_y": {"type": N},
            "layer": S2,
        },
        "required": ["point_x", "point_y"],
    },
    # ── Gradient ───────────────────────────────────────────
    {
        "name": "create_gradient",
        "description": "Create gradient fill (requires .NET engine)",
        "properties": {
            "color1": S2,
            "color2": S2,
            "scale": {"type": N},
            "gradient_type": S2,
            "boundary_handles": {"type": "array", "items": S2},
            "point_xs": {"type": "array", "items": {"type": N}},
            "point_ys": {"type": "array", "items": {"type": N}},
        },
        "required": [],
    },
    # ── Arc Length Dimension ───────────────────────────────
    {
        "name": "create_arc_length_dimension",
        "description": "Create arc length dimension (requires .NET engine)",
        "properties": {
            "center_x": {"type": N},
            "center_y": {"type": N},
            "radius": {"type": N},
            "start_angle": {"type": N},
            "end_angle": {"type": N},
            "dim_x": {"type": N},
            "dim_y": {"type": N},
        },
        "required": [],
    },
    # ── Export IFC ─────────────────────────────────────────
    {
        "name": "export_ifc",
        "description": "Export to IFC file (requires .NET engine)",
        "properties": {"path": S2},
        "required": ["path"],
    },
    # ── Mesh ────────────────────────────────────────────────
    {
        "name": "create_mesh",
        "description": "Create a 3D mesh (SubDMesh) from vertices+faces (req .NET engine)",
        "properties": {
            "vertices": {"type": "array", "items": {"type": "array", "items": {"type": N}}},
            "face_indices": {"type": "array", "items": {"type": "integer"}},
            "smooth_level": {"type": "integer"},
            "layer": S2,
        },
        "required": ["vertices", "face_indices"],
    },
    {
        "name": "edit_mesh",
        "description": "Edit mesh vertices or subdivide (requires .NET engine)",
        "properties": {
            "handle": S2,
            "vertices": {"type": "array", "items": {"type": "array", "items": {"type": N}}},
            "subdivide": {"type": "integer"},
        },
        "required": ["handle"],
    },
    # ── Viewport ────────────────────────────────────────────
    {
        "name": "set_viewport",
        "description": "Set viewport configuration (requires .NET engine)",
        "properties": {
            "name": S2,
            "vp_type": S2,
        },
        "required": [],
    },
    # ── Render ──────────────────────────────────────────────
    {
        "name": "render",
        "description": "Render the current scene (requires .NET engine)",
        "properties": {"output_file": S2},
        "required": [],
    },
    # ── Screenshot ──────────────────────────────────────────
    {
        "name": "screenshot",
        "description": "Save EMF screenshot of current viewport to file",
        "properties": {
            "path": S2,
            "width": {"type": I, "description": "Image width in pixels", "default": 1920},
            "height": {"type": I, "description": "Image height in pixels", "default": 1080},
        },
        "required": ["path"],
    },
    # ── NURBS / IFC ──────────────────────────────────────────
    {
        "name": "create_nurb_curve",
        "description": "Create NURBS curve by degree, control points, and knots (requires .NET engine)",
        "properties": {
            "degree": {"type": I},
            "periodic": {"type": B},
            "control_points": {
                "type": "array",
                "items": {"type": "array", "items": {"type": N}},
            },
            "knots": {"type": "array", "items": {"type": N}},
            "weights": {"type": "array", "items": {"type": N}},
            "layer": S2,
        },
        "required": ["control_points", "knots"],
    },
    {
        "name": "create_nurb_surface",
        "description": "Create NURBS surface by degree U/V and control points (requires .NET engine)",
        "properties": {
            "degree_u": {"type": I},
            "degree_v": {"type": I},
            "rational": {"type": B},
            "control_points": {
                "type": "array",
                "items": {"type": "array", "items": {"type": N}},
            },
            "u_knots": {"type": "array", "items": {"type": N}},
            "v_knots": {"type": "array", "items": {"type": N}},
            "weights": {"type": "array", "items": {"type": N}},
            "num_control_u": {"type": I},
            "num_control_v": {"type": I},
            "layer": S2,
        },
        "required": ["control_points", "u_knots", "v_knots", "num_control_u", "num_control_v"],
    },
    {
        "name": "modify_nurb",
        "description": "Modify NURBS curve/surface control points and knots (requires .NET engine)",
        "properties": {
            "handle": S2,
            "control_points": {
                "type": "array",
                "items": {"type": "array", "items": {"type": N}},
            },
            "knots": {"type": "array", "items": {"type": N}},
        },
        "required": ["handle"],
    },
    {
        "name": "import_ifc",
        "description": "Import IFC file at specified path (requires .NET engine)",
        "properties": {"path": S2},
        "required": ["path"],
    },
    {
        "name": "get_ifc_entities",
        "description": "Get IFC entities from the current drawing (requires .NET engine)",
        "properties": {},
        "required": [],
    },
    # ── MultiCAD API ──────────────────────────────────────────
    {
        "name": "create_grid_axis",
        "description": "Create a grid axis system (requires .NET engine)",
        "properties": {
            "type": S2,
            "origin_x": {"type": N},
            "origin_y": {"type": N},
            "spacings_x": {"type": "array", "items": {"type": N}},
            "spacings_y": {"type": "array", "items": {"type": N}},
            "naming_x": S2,
            "naming_y": S2,
        },
        "required": [],
    },
    {
        "name": "create_grid_label",
        "description": "Create a grid axis label (requires .NET engine)",
        "properties": {
            "grid_handle": S2,
            "label": S2,
            "axis_index": {"type": I},
            "direction": S2,
        },
        "required": ["grid_handle", "label"],
    },
    {
        "name": "create_room",
        "description": "Create a room space (requires .NET engine)",
        "properties": {
            "x": {"type": N},
            "y": {"type": N},
            "width": {"type": N},
            "height": {"type": N},
            "name": S2,
        },
        "required": [],
    },
    {
        "name": "get_room_properties",
        "description": "Get room properties by handle (requires .NET engine)",
        "properties": {"handle": S2},
        "required": ["handle"],
    },
    {
        "name": "create_custom_object",
        "description": "Create a custom object by class name and properties (requires .NET engine)",
        "properties": {
            "class_name": S2,
            "properties": {"type": OBJ},
        },
        "required": ["class_name"],
    },
    {
        "name": "create_parametric_object",
        "description": "Create a parametric object (requires .NET engine)",
        "properties": {
            "type": S2,
            "parameters": {"type": OBJ},
        },
        "required": ["type"],
    },
    {
        "name": "create_reactor",
        "description": "Create a reactor on an entity (requires .NET engine)",
        "properties": {
            "entity_handle": S2,
            "event_type": S2,
        },
        "required": ["entity_handle"],
    },
    {
        "name": "create_2d_break",
        "description": "Create a 2D break in a view (requires .NET engine)",
        "properties": {
            "view_handle": S2,
            "x1": {"type": N},
            "y1": {"type": N},
            "x2": {"type": N},
            "y2": {"type": N},
        },
        "required": ["view_handle"],
    },
    {
        "name": "start_motion_preview",
        "description": "Start motion preview for an entity (requires .NET engine)",
        "properties": {"handle": S2},
        "required": ["handle"],
    },
    {
        "name": "stop_motion_preview",
        "description": "Stop motion preview (requires .NET engine)",
        "properties": {},
        "required": [],
    },
    {
        "name": "create_body_contour",
        "description": "Create a body contour from a 3D solid (requires .NET engine)",
        "properties": {"solid_handle": S2},
        "required": ["solid_handle"],
    },
    {
        "name": "check_3d_faces",
        "description": "Check 3D faces of a solid (requires .NET engine)",
        "properties": {"handle": S2},
        "required": ["handle"],
    },
    # ── Parametric Design Tools (server-side, no CAD needed) ──
    {
        "name": "set_parameter",
        "description": "Set a named parameter for parametric design (value, formula like =Width*2, or reference like *Thickness)",
        "properties": {
            "name": S2,
            "value": {"type": "string"},
            "description": S2,
        },
        "required": ["name", "value"],
    },
    {
        "name": "get_parameter",
        "description": "Get a named parameter's value and metadata",
        "properties": {"name": S2},
        "required": ["name"],
    },
    {
        "name": "list_parameters",
        "description": "List all named parameters with their resolved values and formulas",
        "properties": {},
        "required": [],
    },
    {
        "name": "delete_parameter",
        "description": "Delete a named parameter from parametric design registry",
        "properties": {"name": S2},
        "required": ["name"],
    },
    {
        "name": "evaluate_expression",
        "description": "Evaluate a mathematical expression against current parameters (e.g. Width*2+10)",
        "properties": {"expression": S2},
        "required": ["expression"],
    },
    {
        "name": "resolve_value",
        "description": "Resolve a value (literal, *reference, or =formula) against current parameters",
        "properties": {"raw": {"type": "string"}},
        "required": ["raw"],
    },
    {
        "name": "load_design_table",
        "description": "Load a design table from CSV data (first row = parameter names, subsequent rows = configurations)",
        "properties": {"csv_data": S2},
        "required": ["csv_data"],
    },
    {
        "name": "apply_design_row",
        "description": "Apply a design table row as parameter values",
        "properties": {
            "row_index": {"type": N},
            "rows_json": {"type": "array", "items": {"type": "object"}},
        },
        "required": ["row_index", "rows_json"],
    },
    # ── History / Model Regeneration (server-side, no CAD needed) ──
    {
        "name": "record_tool_call",
        "description": "Record a tool call for later parametric replay",
        "properties": {
            "tool_name": S2,
            "params": {"type": "object"},
            "description": S2,
        },
        "required": ["tool_name"],
    },
    {
        "name": "get_history",
        "description": "Get recorded tool call history",
        "properties": {},
        "required": [],
    },
    {
        "name": "delete_history_entry",
        "description": "Delete a single history entry by ID",
        "properties": {"entry_id": S2},
        "required": ["entry_id"],
    },
    {
        "name": "clear_history",
        "description": "Clear all recorded tool call history",
        "properties": {},
        "required": [],
    },
    {
        "name": "replay_history",
        "description": "Replay all recorded tool calls with re-resolved parameter values",
        "properties": {},
        "required": [],
    },
    # ── Configuration Management (multi-variant design tables) ──
    {
        "name": "save_configuration",
        "description": "Save all current parameter values as a named configuration (variant)",
        "properties": {"name": S2},
        "required": ["name"],
    },
    {
        "name": "load_configuration",
        "description": "Restore a named configuration as current parameter values (replaces all)",
        "properties": {"name": S2},
        "required": ["name"],
    },
    {
        "name": "list_configurations",
        "description": "List all saved configurations with their parameter values",
        "properties": {},
        "required": [],
    },
    {
        "name": "delete_configuration",
        "description": "Delete a named configuration",
        "properties": {"name": S2},
        "required": ["name"],
    },
    # ── Электро (BIM Электро: щиты, группы, расчёты, БД оборудования) ──
    {
        "name": "electro_boards_list",
        "description": "List electrical boards (щиты) in the current nanoCAD BIM Электро project: title, ac_id, fider counts. Use ac_id for other electro_* tools",
        "properties": {},
        "required": [],
    },
    {
        "name": "electro_board_calc",
        "description": "Power calculation of a board via the native Электро pipeline: per-fider consumers (Pnom, cos phi), Pcalc/Icalc/DeltaU, short-circuit currents, supply chain, board totals",
        "properties": {
            "board_ac_id": {"type": S, "description": "Board ac_id from electro_boards_list, e.g. '1692637570:61477-0'"},
        },
        "required": ["board_ac_id"],
    },
    {
        "name": "electro_db_automats",
        "description": "Search circuit breakers (автоматы) in the equipment DB. Filters: query (name/series substring), poles ('1P'/'2P'/'3P'/'4P'/'1P+N'), characteristic ('B'/'C'/'D'/'K'/'Z'), current (trip rating A), limit (default 50). Returns db_id for electro_group_create",
        "properties": {
            "query": S2,
            "poles": S2,
            "characteristic": S2,
            "current": {"type": N},
            "limit": {"type": I},
        },
        "required": [],
    },
    {
        "name": "electro_db_uzo",
        "description": "Search RCDs (УЗО) in the equipment DB. Filters: query (name substring), poles ('2P'/'4P'), current (nominal A), leakage_ma (30/100/300), limit (default 50). Returns db_id for electro_group_create",
        "properties": {
            "query": S2,
            "poles": S2,
            "current": {"type": N},
            "leakage_ma": {"type": N},
            "limit": {"type": I},
        },
        "required": [],
    },
    {
        "name": "electro_group_create",
        "description": "Create a new outgoing group (фидер) on a board with apparatus from the equipment DB. automat_db_id / uzo_db_id are db_id values from electro_db_automats / electro_db_uzo; 0 = skip. Saves the model",
        "properties": {
            "board_ac_id": {"type": S, "description": "Board ac_id from electro_boards_list"},
            "name": {"type": S, "description": "Group name, e.g. 'гр 7'"},
            "automat_db_id": {"type": I, "description": "db_id of circuit breaker, 0 = none"},
            "uzo_db_id": {"type": I, "description": "db_id of RCD, 0 = none"},
        },
        "required": ["board_ac_id", "name"],
    },
    {
        "name": "electro_node_dump",
        "description": "Dump all properties of a CAE model node by ac_id (diagnostics: boards, fiders, consumers)",
        "properties": {
            "ac_id": {"type": S},
        },
        "required": ["ac_id"],
    },
]

# Verify count
assert len(TOOL_DEFS) == 213, f"Expected 213 tools, got {len(TOOL_DEFS)}"

# ── Assign requires_mode to each tool definition ──────────────
for td in TOOL_DEFS:
    name: str = td["name"]
    if name in _OFFLINE_TOOLS:
        td["requires_mode"] = None
    elif name in _COM_TOOLS:
        td["requires_mode"] = "com"
    else:
        td["requires_mode"] = "full"
