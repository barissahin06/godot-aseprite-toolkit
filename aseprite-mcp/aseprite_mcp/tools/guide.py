from .. import mcp

@mcp.tool()
async def animation_workflow_guide(use_case: str = "character") -> str:
    """Return a concise English guide for optimized animation workflows."""
    use_case = (use_case or "character").strip().lower()
    header = "Animation Workflow Guide"
    if use_case == "character":
        bullets = [
            "Checkpoint the editable source. Block readable silhouettes before material finish; duplicate with copy_frame/copy_cel without replacing accepted poses.",
            "For walking, draw contact/down/passing/up poses on both legs. Declare heel/toe ground contacts and inspect them against moving ground; a changing bounding box does not prove foot sliding.",
            "Propagate only genuinely static layers; body, knees and clothing must follow weight transfer rather than remain fixed through the clip.",
            "Use strong drawn key poses; interpolate rigid parts and draw alternate cels where pixels deform.",
            "Keep the weapon handle attached to the hand and the blade length fixed. Use a continuous hand/blade arc, not a jump between ready and wind-up.",
            "Let hair, scarf and accessories trail the main action on separate layers; avoid flipping secondary motion abruptly at phase boundaries.",
            "Keep layers deterministic: set_layer_visibility/opacity + *_at drawing tools.",
            "Finalize with set_tag for loop ranges and export_sprite for preview.",
            "Run audit_animation to inspect coverage/overlaps, review at native size and normal speed, then choose scoped corrections.",
            "With the Godot bridge, use review_asset at fps=50 for short poses. Scrub matching before/after samples and check native contact/chain_ready markers, unchanged runs and uncaptured frame keys; these are diagnostics, not art approval.",
            "Retime only selected frame_duration entries with batch_edit_sprite, rebuild, and revalidate contact/recovery markers. For native rig motion use edit_animation; preserve unrelated tracks and source pixels.",
        ]
    elif use_case == "environment":
        bullets = [
            "Build the base scene once and copy with copy_sprite for variants.",
            "Use propagate_cels for static layers (sky, mountains, ground).",
            "Animate only the moving layers (clouds, birds, water) with tween/offset.",
            "Use apply_gradient_rect and palette tools for consistent color mood.",
            "Copy reusable assets across scenes with copy_layers_between_sprites.",
            "Tag loops and export GIFs to validate pacing.",
            "Run audit_animation or animation_sanitize to validate layer coverage and overlaps.",
        ]
    else:
        bullets = [
            "Create the base on frame 1, then duplicate cels/frames for consistency.",
            "Animate by moving cels, not redrawing each frame.",
            "Use layer-targeted tools (*_at) to avoid active-cel drift.",
            "Propagate static layers across the frame range.",
            "Use tags for loop ranges and export previews early.",
            "Run audit_animation or animation_sanitize to validate layer coverage and overlaps.",
        ]

    lines = [header, f"Use case: {use_case}"]
    lines.extend([f"- {b}" for b in bullets])
    return "\n".join(lines)
