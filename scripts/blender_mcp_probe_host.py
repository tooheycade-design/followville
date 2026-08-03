"""Temporary GUI host used by check_blender_mcp.ps1-style diagnostics.

Run only in a disposable Blender session. It starts the locally installed addon
socket and exits automatically, without opening or saving a project file.
"""

import bpy
import addon


if not hasattr(bpy.types.Scene, "blendermcp_port"):
    addon.register()

bpy.context.scene.blendermcp_port = 9876
bpy.context.scene.blendermcp_auto_start_server = False
result = bpy.ops.blendermcp.start_server()
print(f"BLENDER_MCP_PROBE_HOST_STARTED result={result}", flush=True)


def exit_probe():
    if hasattr(bpy.types, "blendermcp_server"):
        bpy.types.blendermcp_server.stop()
    bpy.ops.wm.quit_blender()
    return None


bpy.app.timers.register(exit_probe, first_interval=30.0)
