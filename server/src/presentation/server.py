from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

import structlog
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.server.stdio import stdio_server
from mcp.types import (
    CallToolResult,
    Prompt,
    PromptArgument,
    PromptMessage,
    Resource,
    ResourceTemplate,
    TextContent,
    Tool,
)
from pydantic import AnyUrl

from src.domain.exceptions import NanocadError
from src.presentation.context import get_factory, get_repository
from src.presentation.tool_defs import TOOL_DEFS
from src.presentation.tool_validation import ToolValidationError, validate_tool_input

if TYPE_CHECKING:
    from collections.abc import Callable

# -- Logging Setup -------------------------------------------------------------


def setup_logging(*, debug: bool = False) -> None:
    log_level = logging.DEBUG if debug else logging.INFO
    log_path = Path(__file__).resolve().parent.parent.parent / "logs" / "ncad-mcp-python.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(str(log_path), encoding="utf-8"),
            logging.StreamHandler(sys.stderr),
        ],
    )
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.dev.ConsoleRenderer(colors=True),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


log = structlog.get_logger()


# -- Global State (contextvars) -------------------------------------------------

_routing_cache: object = None
_tool_cache: dict[str, list[Tool]] = {}


def _ensure_connected() -> None:
    """Ensure the CAD repository is connected for this request context.

    Uses ``contextvars`` for request-scoped state — safe for concurrent SSE.
    ``get_repository()`` lazily creates the repository on first call.
    """
    repo = get_repository()
    if not repo.is_available():
        if not repo.connect():
            log.warning(
                "nanoCAD connection failed, mode=%s",
                getattr(repo, "connection_mode", "unknown"),
            )

    # Invalidate caches on reconnection
    global _routing_cache
    _routing_cache = None
    _tool_cache.clear()


# -- Tool Definitions ----------------------------------------------------------

# Mode priority for capability filtering (higher = more capable)
_MODE_ORDER: Final[dict[str, int]] = {
    "offline": 0,
    "com": 1,
    "full": 2,
}


def _get_tools(mode: str = "full") -> list[Tool]:
    """Return MCP tool definitions filtered by connection mode (cached).

    Each tool definition has a ``requires_mode`` field:
      ``None`` / missing — always available (no CAD needed)
      ``"com"`` — requires at least COM bridge
      ``"full"`` — requires .NET engine (HTTP bridge)
    """
    if mode in _tool_cache:
        return _tool_cache[mode]
    required = _MODE_ORDER.get(mode, 0)
    tools = [
        Tool(
            name=td["name"],
            description=td["description"],
            inputSchema={
                "type": "object",
                "properties": td["properties"],
                "required": td["required"],
            },
        )
        for td in TOOL_DEFS
        if _MODE_ORDER.get(td.get("requires_mode", "full"), 0) <= required
    ]
    _tool_cache[mode] = tools
    return tools


# -- Routing -------------------------------------------------------------------


# Maps tool names to factory-property + method.
# Format: tool_name -> (factory_attr, method_name)
_TOOL_HANDLER_MAP: dict[str, tuple[str, str]] = {
    # Health & System
    "health_check": ("system", "is_available"),
    "get_system_fonts": ("system", "get_fonts"),
    "get_system_info": ("system", "get_info"),
    "execute_command": ("system", "execute_command"),
    "get_system_variable": ("system", "get_variable"),
    "set_system_variable": ("system", "set_variable"),
    # 2D Primitives
    "create_line": ("entity", "create_line"),
    "create_circle": ("entity", "create_circle"),
    "create_arc": ("entity", "create_arc"),
    "create_polyline": ("entity", "create_polyline"),
    "create_rectangle": ("entity", "create_rectangle"),
    "create_text": ("entity", "create_text"),
    "create_mtext": ("entity", "create_mtext"),
    "create_point": ("entity", "create_point"),
    "create_ellipse": ("entity", "create_ellipse"),
    "create_spline": ("entity", "create_spline"),
    "create_helix": ("entity", "create_helix"),
    "create_region": ("entity", "create_region"),
    "create_boundary": ("entity", "create_boundary"),
    "delete_entity": ("entity", "delete_entity"),
    "get_entity": ("entity", "get_entity"),
    # Entity Transformations
    "move_entity": ("entity", "move_entity"),
    "copy_entity": ("entity", "copy_entity"),
    "rotate_entity": ("entity", "rotate_entity"),
    "scale_entity": ("entity", "scale_entity"),
    "mirror_entity": ("entity", "mirror_entity"),
    "stretch_entity": ("transform", "stretch_entity"),
    "explode_entity": ("transform", "explode_entity"),
    "divide_entity": ("transform", "divide_entity"),
    "measure_entity": ("transform", "measure_entity"),
    "array_3d": ("transform", "array_3d"),
    "align_3d": ("transform", "align_3d"),
    "mirror_3d": ("transform", "mirror_3d"),
    # Layers
    "create_layer": ("layer", "create_layer"),
    "get_linetypes": ("layer", "get_linetypes"),
    "get_layers": ("layer", "get_layers"),
    "set_current_layer": ("layer", "set_current_layer"),
    "set_layer_state": ("layer", "set_layer_state"),
    "delete_layer": ("layer", "delete_layer"),
    "layer_isolate": ("layer_mgmt", "layer_isolate"),
    "layer_off": ("layer_mgmt", "layer_off"),
    "layer_freeze": ("layer_mgmt", "layer_freeze"),
    "layer_on_all": ("layer_mgmt", "layer_on_all"),
    "layer_thaw_all": ("layer_mgmt", "layer_thaw_all"),
    # Blocks
    "get_blocks": ("block", "get_blocks"),
    "insert_block": ("block", "insert_block"),
    "delete_block": ("block", "delete_block"),
    "get_block_entities": ("block", "get_block_entities"),
    "create_block": ("block_mgmt", "create_block"),
    "explode_block": ("block_mgmt", "explode_block"),
    # Document
    "get_document_info": ("document", "get_info"),
    "save_document": ("document", "save"),
    "export_pdf": ("document", "export_pdf"),
    "export_dwg": ("document", "export_dwg"),
    "export_dxf": ("document", "export_dxf"),
    "zoom_extents": ("document", "zoom_extents"),
    "new_document": ("document", "new_document"),
    "create_project": ("document", "create_project"),
    "save_project": ("document", "save_project"),
    "open_document": ("document", "open_document"),
    "close_document": ("document", "close_document"),
    # Document Management
    "undo": ("doc_mgmt", "undo"),
    "redo": ("doc_mgmt", "redo"),
    "purge": ("doc_mgmt", "purge"),
    "import_step": ("doc_mgmt", "import_step"),
    "export_step": ("doc_mgmt", "export_step"),
    "export_ifc": ("document", "export_ifc"),
    # 3D Solids
    "create_box": ("solid", "create_box"),
    "create_sphere": ("solid", "create_sphere"),
    "create_cylinder": ("solid", "create_cylinder"),
    "create_cone": ("solid", "create_cone"),
    "create_torus": ("solid", "create_torus"),
    "create_wedge": ("solid", "create_wedge"),
    "create_pyramid": ("solid", "create_pyramid"),
    "boolean_union": ("solid", "boolean_union"),
    "boolean_subtract": ("solid", "boolean_subtract"),
    "boolean_intersect": ("solid", "boolean_intersect"),
    "extrude_solid": ("solid", "extrude_solid"),
    "revolve_solid": ("solid", "revolve_solid"),
    "sweep_solid": ("sweep_loft", "sweep_solid"),
    "loft_solid": ("sweep_loft", "loft_solid"),
    "fillet_edge": ("edge_op", "fillet_edge"),
    "chamfer_edge": ("edge_op", "chamfer_edge"),
    "set_3d_view": ("solid", "set_3d_view"),
    "get_solid_properties": ("solid", "get_solid_properties"),
    "move_solid": ("solid", "move_solid"),
    "rotate_solid": ("solid", "rotate_solid"),
    # Symbols
    "create_roughness": ("symbol", "create_roughness"),
    "create_old_roughness": ("symbol", "create_old_roughness"),
    "create_tolerance": ("symbol", "create_tolerance"),
    "create_datum": ("symbol", "create_datum"),
    "create_weld": ("symbol", "create_weld"),
    "create_leader": ("symbol", "create_leader"),
    "create_note_comb": ("symbol", "create_note_comb"),
    "create_dim_number": ("symbol", "create_dim_number"),
    "create_mleader": ("mleader", "create_mleader"),
    # Tables
    "create_table": ("table", "create_table"),
    "edit_table_cell": ("table", "edit_table_cell"),
    "get_table_info": ("table", "get_table_info"),
    "delete_table": ("table", "delete_table"),
    # Hatch
    "create_hatch": ("hatch", "create_hatch"),
    "create_gradient": ("hatch", "create_gradient"),
    "get_hatch_info": ("hatch", "get_hatch_info"),
    "edit_hatch": ("hatch", "edit_hatch"),
    # Dimensions
    "create_aligned_dimension": ("dimension", "create_aligned_dimension"),
    "create_rotated_dimension": ("dimension", "create_rotated_dimension"),
    "create_radial_dimension": ("dimension", "create_radial_dimension"),
    "create_diametric_dimension": ("dimension", "create_diametric_dimension"),
    "create_angular_dimension": ("dimension", "create_angular_dimension"),
    "create_ordinate_dimension": ("dimension", "create_ordinate_dimension"),
    "create_arc_length_dimension": ("dimension", "create_arc_length_dimension"),
    "create_linear_dimension": ("linear_dim", "create_linear_dimension"),
    # Measurements
    "get_distance": ("measurement", "get_distance"),
    "get_angle": ("measurement", "get_angle"),
    "get_area": ("measurement", "get_area"),
    "get_entity_info": ("measurement", "get_entity_info"),
    "get_all_entities": ("measurement", "get_all_entities"),
    "get_entity_detail": ("selection", "get_entity_detail"),
    # Trim / Extend / Offset
    "trim_entity": ("teo", "trim_entity"),
    "extend_entity": ("teo", "extend_entity"),
    "offset_entity": ("teo", "offset_entity"),
    # Primitives
    "create_polygon": ("primitive", "create_polygon"),
    "create_donut": ("primitive", "create_donut"),
    "create_xline": ("primitive", "create_xline"),
    "create_ray": ("primitive", "create_ray"),
    # Selection
    "select_entities": ("selection", "select_entities"),
    "select_by_handles": ("selection", "select_by_handles"),
    # 2D Constraints
    "constraint_parallel": ("constraint", "constraint_parallel"),
    "constraint_coincident": ("constraint", "constraint_coincident"),
    "constraint_fix": ("constraint", "constraint_fix"),
    "constraint_horizontal": ("constraint", "constraint_horizontal"),
    "constraint_vertical": ("constraint", "constraint_vertical"),
    "constraint_tangent": ("constraint", "constraint_tangent"),
    "constraint_perpendicular": ("constraint", "constraint_perpendicular"),
    "constraint_collinear": ("constraint", "constraint_collinear"),
    "constraint_concentric": ("constraint", "constraint_concentric"),
    "constraint_equal": ("constraint", "constraint_equal"),
    "constraint_symmetric": ("constraint", "constraint_symmetric"),
    "constraint_distance": ("constraint", "constraint_distance"),
    # Assembly
    "insert_part": ("assembly", "insert_part"),
    "assembly_mate": ("assembly", "assembly_mate"),
    "assembly_angle": ("assembly", "assembly_angle"),
    "assembly_tangent": ("assembly", "assembly_tangent"),
    "assembly_symmetry": ("assembly", "assembly_symmetry"),
    # STL Export
    "export_stl": ("stl", "export_stl"),
    # Sheet Metal
    "create_base_flange": ("sheet_metal", "create_base_flange"),
    "create_edge_flange": ("sheet_metal", "create_edge_flange"),
    "create_bend": ("sheet_metal", "create_bend"),
    "unfold_sheet_metal": ("sheet_metal", "unfold_sheet_metal"),
    "create_base_plate": ("sheet_metal", "create_base_plate"),
    # 3D Features
    "create_simple_hole": ("feature", "create_simple_hole"),
    "create_threaded_hole": ("feature", "create_threaded_hole"),
    "create_standard_hole": ("feature", "create_standard_hole"),
    "create_shell": ("feature", "create_shell"),
    "create_mirror_feature": ("feature", "create_mirror_feature"),
    "create_circular_pattern": ("feature", "create_circular_pattern"),
    "create_rectangular_pattern": ("feature", "create_rectangular_pattern"),
    "create_sketch": ("feature", "create_sketch"),
    "add_sketch_circle": ("feature", "add_sketch_circle"),
    "add_sketch_line": ("feature", "add_sketch_line"),
    "create_profile": ("feature", "create_profile"),
    "create_extrude_feature": ("feature", "create_extrude_feature"),
    "create_revolve_feature": ("feature", "create_revolve_feature"),
    # ── Feature Tree Management (Phase P2) ──
    "get_feature_list": ("feature", "get_feature_list"),
    "suppress_feature": ("feature", "suppress_feature"),
    "unsuppress_feature": ("feature", "unsuppress_feature"),
    "edit_feature_parameter": ("feature", "edit_feature_parameter"),
    "delete_feature": ("feature", "delete_feature"),
    # Mesh / Viewport / Render
    "create_mesh": ("entity", "create_mesh"),
    "edit_mesh": ("entity", "edit_mesh"),
    "set_viewport": ("entity", "set_viewport"),
    "render": ("entity", "render"),
    "screenshot": ("document", "screenshot"),
    # NURBS / IFC
    "create_nurb_curve": ("nurb_ifc", "create_nurb_curve"),
    "create_nurb_surface": ("nurb_ifc", "create_nurb_surface"),
    "modify_nurb": ("nurb_ifc", "modify_nurb"),
    "import_ifc": ("nurb_ifc", "import_ifc"),
    "get_ifc_entities": ("nurb_ifc", "get_ifc_entities"),
    # MultiCAD API
    "create_grid_axis": ("multicad", "create_grid_axis"),
    "create_grid_label": ("multicad", "create_grid_label"),
    "create_room": ("multicad", "create_room"),
    "get_room_properties": ("multicad", "get_room_properties"),
    "create_custom_object": ("multicad", "create_custom_object"),
    "create_parametric_object": ("multicad", "create_parametric_object"),
    "create_reactor": ("multicad", "create_reactor"),
    "create_2d_break": ("multicad", "create_2d_break"),
    "start_motion_preview": ("multicad", "start_motion_preview"),
    "stop_motion_preview": ("multicad", "stop_motion_preview"),
    "create_body_contour": ("multicad", "create_body_contour"),
    "check_3d_faces": ("multicad", "check_3d_faces"),
    # ── Parametric Design (server-side, no CAD needed) ──
    "set_parameter": ("parameter", "set_parameter"),
    "get_parameter": ("parameter", "get_parameter"),
    "list_parameters": ("parameter", "list_parameters"),
    "delete_parameter": ("parameter", "delete_parameter"),
    "clear_parameters": ("parameter", "clear_parameters"),
    "evaluate_expression": ("parameter", "evaluate_expression"),
    "resolve_value": ("parameter", "resolve_value"),
    "load_design_table": ("parameter", "load_design_table"),
    "apply_design_row": ("parameter", "apply_design_row"),
    # ── History / Model Regeneration (server-side, no CAD needed) ──
    "record_tool_call": ("history", "record_tool_call"),
    "get_history": ("history", "get_history"),
    "delete_history_entry": ("history", "delete_entry"),
    "clear_history": ("history", "clear_history"),
    # replay_history is handled separately in _build_routing()
    # ── Configuration Management (server-side, no CAD needed) ──
    "save_configuration": ("parameter", "save_configuration"),
    "load_configuration": ("parameter", "load_configuration"),
    "list_configurations": ("parameter", "list_configurations"),
    "delete_configuration": ("parameter", "delete_configuration"),
    # ── Электро (BIM Электро: щиты, группы, расчёты, БД) ──
    "electro_boards_list": ("electro", "list_boards"),
    "electro_board_groups": ("electro", "board_groups"),
    "electro_board_calc": ("electro", "board_calc"),
    "electro_db_automats": ("electro", "list_db_automats"),
    "electro_db_uzo": ("electro", "list_db_uzo"),
    "electro_group_create": ("electro", "create_group"),
    "electro_group_delete": ("electro", "delete_group"),
    "electro_node_dump": ("electro", "dump_node"),
}


def _build_routing() -> dict[str, Callable[..., Any]]:
    """Build tool_name -> handler routing from the handler map via UseCaseFactory."""
    global _routing_cache
    if _routing_cache is not None:
        return _routing_cache  # type: ignore[return-value]

    factory = get_factory()
    routing: dict[str, Callable[..., Any]] = {}
    for tool_name, (attr_name, method_name) in _TOOL_HANDLER_MAP.items():
        uc = getattr(factory, attr_name, None)
        if uc is None:
            continue
        handler = getattr(uc, method_name, None)
        if handler is not None:
            routing[tool_name] = handler

    # ── Special: replay_history needs a dispatcher to route tool names ──
    async def _replay_handler(**kwargs: Any) -> dict[str, Any]:
        history_uc = factory.history

        async def _dispatcher(tool_name: str, resolved_params: dict[str, Any]) -> Any:
            if tool_name not in _TOOL_HANDLER_MAP:
                raise ValueError(f"Unknown tool in history: {tool_name}")
            attr_name, method_name = _TOOL_HANDLER_MAP[tool_name]
            uc = getattr(factory, attr_name, None)
            if uc is None:
                raise RuntimeError(f"Use case not found: {attr_name}")
            method = getattr(uc, method_name, None)
            if method is None:
                raise RuntimeError(f"Method not found: {attr_name}.{method_name}")
            if asyncio.iscoroutinefunction(method):
                return await method(**resolved_params)
            return method(**resolved_params)

        return await history_uc.replay_history(_dispatcher)

    routing["replay_history"] = _replay_handler

    _routing_cache = routing
    return routing


def _format_result(result: Any) -> str:
    """Format a tool result for user display.

    Handles common return types (dict, list, str, None) and formats them
    as readable text with English labels.
    """
    if result is None:
        return "nil (no result)"
    if isinstance(result, dict):
        # If error field present, show it
        if result.get("success") is False:
            err = result.get("error") or "unknown error"
            return f"ERROR: {err}"
        if result.get("success") is True:
            # Strip success=True for cleaner output
            d = {k: v for k, v in result.items() if k != "success"}
            if not d:
                return "OK"
            parts = [f"{_label(k)}: {v}" for k, v in d.items()]
            return "\n".join(parts)
        # General dict
        parts = [f"{_label(k)}: {v}" for k, v in result.items()]
        return "\n".join(parts)
    if isinstance(result, list):
        if not result:
            return "(empty)"
        lines = [f"  {i + 1}. {v}" for i, v in enumerate(result)]
        return "\n".join(lines)
    return str(result)


def _label(key: str) -> str:
    """Map JSON keys to human-readable English labels for user-facing output."""
    labels: dict[str, str] = {
        "handle": "Handle",
        "new_handle": "New Handle",
        "source_handle": "Source Handle",
        "target_handle": "Target Handle",
        "name": "Name",
        "version": "Version",
        "path": "Path",
        "is_saved": "Saved",
        "entities_count": "Entities",
        "layers_count": "Layers",
        "blocks_count": "Blocks",
        "active_documents": "Active documents",
        "success": "Success",
        "error": "Error",
        "error_message": "Error",
        "output": "Result",
        "command": "Command",
        "is_on": "On",
        "is_frozen": "Frozen",
        "is_locked": "Locked",
        "color": "Color",
        "value": "Value",
        "type": "Type",
        "layer": "Layer",
        "angle": "Angle",
        "radius": "Radius",
        "diameter": "Diameter",
        "height": "Height",
        "width": "Width",
        "length": "Length",
        "thickness": "Thickness",
        "delta": "Delta",
        "dx": "DX",
        "dy": "DY",
        "dz": "DZ",
        "cx": "Center X",
        "cy": "Center Y",
        "cz": "Center Z",
        "center_x": "Center X",
        "center_y": "Center Y",
        "center_z": "Center Z",
        "axis_x": "Axis X",
        "axis_y": "Axis Y",
        "axis_z": "Axis Z",
        "insertion": "Insertion Point",
        "block_name": "Block Name",
        "scale": "Scale",
        "rotation": "Rotation",
        "count": "Count",
        "direction": "Direction",
        "fit_points_count": "Fit Points",
        "vertices_count": "Vertices",
        "segments": "Segments",
        "distance": "Distance",
        "area": "Area",
        "pattern": "Pattern",
        "item_type": "Entity Type",
        "render_mode": "Render Mode",
    }
    return labels.get(key, key.capitalize())


# -- Server --------------------------------------------------------------------


def create_server() -> Server:
    server = Server("ncad-mcp-server")

    @server.list_tools()
    async def handle_list_tools() -> list[Tool]:
        try:
            _ensure_connected()
        except Exception:
            log.debug("list_tools: connection attempt failed, falling back to offline")
        try:
            repo = get_repository()
            mode = repo.connection_mode
        except Exception:
            mode = "offline"
        return _get_tools(mode)

    @server.list_prompts()
    async def handle_list_prompts() -> list[Prompt]:
        return [
            Prompt(
                name="create-part",
                description="Step-by-step workflow for creating a standard engineering part",
                arguments=[
                    PromptArgument(
                        name="part_type",
                        description="Type of part to create: flange, shaft, bracket, or hub",
                        required=True,
                    ),
                ],
            ),
            Prompt(
                name="parametric-design",
                description="Set up parametric design with named parameters and formulas",
                arguments=[
                    PromptArgument(
                        name="parameter_count",
                        description="Number of parameters to configure",
                        required=False,
                    ),
                ],
            ),
        ]

    @server.get_prompt()
    async def handle_get_prompt(
        name: str, arguments: dict[str, str] | None
    ) -> list[PromptMessage] | None:
        if name == "create-part":
            part_type = (arguments or {}).get("part_type", "flange")
            return [
                PromptMessage(
                    role="user",
                    content=TextContent(
                        type="text",
                        text=f"Create a {part_type} part. "
                        "Ask the user for dimensions and create the geometry using MCP tools.",
                    ),
                ),
            ]
        if name == "parametric-design":
            return [
                PromptMessage(
                    role="user",
                    content=TextContent(
                        type="text",
                        text="Set up parametric design. "
                        "Ask the user for parameter names and initial values.",
                    ),
                ),
            ]
        return None

    @server.list_resources()
    async def handle_list_resources() -> list[Resource]:
        return [
            Resource(
                name="document",
                uri=AnyUrl("nanocad://document"),
                description="Active document metadata (name, path, entity count)",
                mimeType="application/json",
            ),
            Resource(
                name="layers",
                uri=AnyUrl("nanocad://layers"),
                description="List of all layers in the drawing",
                mimeType="application/json",
            ),
            Resource(
                name="system",
                uri=AnyUrl("nanocad://system"),
                description="nanoCAD version and system info",
                mimeType="application/json",
            ),
            Resource(
                name="parameters",
                uri=AnyUrl("nanocad://parameters"),
                description="Parametric design parameters with values and formulas",
                mimeType="application/json",
            ),
        ]

    @server.list_resource_templates()
    async def handle_list_resource_templates() -> list[ResourceTemplate]:
        return [
            ResourceTemplate(
                name="entities",
                uriTemplate="nanocad://entities/{type}",
                description="CAD entities filtered by type (line, circle, arc, etc.)",
                mimeType="application/json",
            ),
        ]

    @server.read_resource()
    async def handle_read_resource(uri: str) -> str:
        import json as _json

        _ensure_connected()
        repo = get_repository()

        if uri == "nanocad://document":
            return _json.dumps(
                repo.get_document_info().model_dump(), default=str
            )
        if uri == "nanocad://layers":
            return _json.dumps(
                [l.model_dump() for l in repo.get_layers()], default=str
            )
        if uri == "nanocad://system":
            return _json.dumps(
                repo.get_system_info().model_dump(), default=str
            )
        if uri == "nanocad://parameters":
            from src.domain.parameter_registry import get_parameter_registry

            reg = get_parameter_registry()
            return _json.dumps(reg.list_all_with_meta(), default=str)

        if uri.startswith("nanocad://entities/"):
            entity_type = uri.rsplit("/", maxsplit=1)[-1]
            entities = repo.get_entities_by_type(entity_type)
            return _json.dumps(
                [e.model_dump() for e in entities], default=str
            )

        raise ValueError(f"Unknown resource URI: {uri}")

    @server.call_tool()
    async def handle_call_tool(
        name: str,
        arguments: dict[str, Any] | None,
    ) -> list[TextContent] | CallToolResult:
        args = arguments or {}
        log.info("Tool call", tool=name, args=args)

        try:
            _ensure_connected()
        except Exception:
            log.exception("Failed to connect to CAD")
            from src.presentation.context import reset as _reset_context

            _reset_context()
            return CallToolResult(
                content=[
                    TextContent(
                        type="text",
                        text=(
                            "ERROR: Failed to connect to nanoCAD.\n"
                            "Please check:\n"
                            "  1. Is nanoCAD running?\n"
                            "  2. Is the .NET plugin (CadEngine.Plugin) loaded?\n"
                            "  3. Is port 5080 available?\n"
                            "Run health_check for diagnostics."
                        ),
                    )
                ],
                isError=True,
            )

        # Capability discovery at list_tools() level handles tool filtering.
        # If a tool is called but CAD is unavailable, the use case or repository
        # will raise NanocadError (caught below).
        routing = _build_routing()
        handler = routing.get(name)
        if handler is None:
            log.warning("Unknown tool called", tool=name)
            return CallToolResult(
                content=[TextContent(type="text", text=f"UNKNOWN TOOL: {name}")],
                isError=True,
            )

        try:
            validate_tool_input(name, args)
        except ToolValidationError as e:
            return CallToolResult(
                content=[TextContent(type="text", text=f"VALIDATION ERROR: {e}")],
                isError=True,
            )

        try:
            if asyncio.iscoroutinefunction(handler):
                result = await handler(**args)
            else:
                result = handler(**args)
            log.info("Tool result", tool=name, result=result)
            return [TextContent(type="text", text=_format_result(result))]
        except NanocadError as e:
            msg = f"nanoCAD ERROR: {e}"
            log.warning("Tool error (nanoCAD)", tool=name, error=msg)
            return CallToolResult(
                content=[TextContent(type="text", text=msg)],
                isError=True,
            )
        except NotImplementedError as e:
            msg = f"NOT IMPLEMENTED: {e}. Requires .NET engine in nanoCAD."
            log.warning("Tool not implemented", tool=name, error=msg)
            return CallToolResult(
                content=[TextContent(type="text", text=msg)],
                isError=True,
            )
        except Exception as e:
            log.exception("Tool error", tool=name)
            return CallToolResult(
                content=[TextContent(type="text", text=f"ERROR: {e}")],
                isError=True,
            )

    return server


# -- Entry Point ---------------------------------------------------------------


def create_sse_app(
    mcp_server: Server,
    *,
    mount_path: str = "",
    message_path: str = "/messages/",
) -> Any:
    """Create a Starlette ASGI app for SSE transport."""
    from starlette.applications import Starlette
    from starlette.routing import Mount, Route

    full_message_path = mount_path.rstrip("/") + message_path
    sse = SseServerTransport(full_message_path)

    class _SseAsgiApp:
        """ASGI-приложение для SSE-потока (Starlette 1.x требует ASGI на Route)."""

        def __init__(self, server: Server, transport: SseServerTransport) -> None:
            self._server = server
            self._transport = transport

        async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
            if scope["type"] != "http":
                return
            try:
                async with self._transport.connect_sse(scope, receive, send) as streams:
                    await self._server.run(
                        streams[0],
                        streams[1],
                        self._server.create_initialization_options(),
                    )
            except Exception as e:
                log.exception("SSE handler error", error=str(e))

    routes: list[Route | Mount] = []
    if mount_path:
        routes.append(
            Mount(
                mount_path,
                routes=[
                    Route("/", _SseAsgiApp(mcp_server, sse), methods=["GET"]),
                    Mount(message_path.rstrip("/"), app=sse.handle_post_message),
                ],
            )
        )
    else:
        routes.append(Route("/", _SseAsgiApp(mcp_server, sse), methods=["GET"]))
        routes.append(Mount(message_path.rstrip("/"), app=sse.handle_post_message))

    return Starlette(routes=routes)


async def run_sse(port: int = 8081, host: str = "0.0.0.0") -> None:
    """Run MCP server with SSE transport."""
    import uvicorn

    debug = "NANOCAD_MCP_DEBUG" in os.environ
    setup_logging(debug=debug)
    log.info("Starting nanoCAD MCP SSE Server", host=host, port=port)
    server = create_server()
    app = create_sse_app(server)
    config = uvicorn.Config(app, host=host, port=port, log_level="debug" if debug else "info")
    srv = uvicorn.Server(config)
    await srv.serve()


async def run_stdio() -> None:
    """Run MCP server with stdio transport."""
    debug = "NANOCAD_MCP_DEBUG" in os.environ
    setup_logging(debug=debug)
    log.info("Starting nanoCAD MCP Stdio Server", debug=debug)
    server = create_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def main() -> None:
    parser = argparse.ArgumentParser(description="nanoCAD MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default="stdio",
        help="Transport protocol (default: stdio)",
    )
    parser.add_argument("--port", type=int, default=8081, help="SSE port (default: 8081)")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="SSE host (default: 0.0.0.0)")
    args = parser.parse_args()

    if args.transport == "sse":
        asyncio.run(run_sse(port=args.port, host=args.host))
    else:
        asyncio.run(run_stdio())


if __name__ == "__main__":
    main()
