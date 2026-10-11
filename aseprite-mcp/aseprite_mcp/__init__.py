"""Aseprite MCP - Model Context Protocol implementation for Aseprite."""

def __getattr__(name):
    # CLI asset builders reuse stdlib runtime helpers without installing the MCP environment.
    if name != "mcp":
        raise AttributeError(name)
    from .server import NativeMCP
    server = NativeMCP("aseprite", instructions="Inspect before editing. Use native Aseprite sources and strong drawn key poses; combine rigid-bone interpolation with alternate cels where pixels deform. Preserve unrelated layers, frames and linked cels. Use bounded native execution, checkpoint edits, build and review at game size and normal speed before accepting artwork. Lua is trusted code, not a sandbox.")
    globals()["mcp"] = server
    return server

__version__ = "0.2.0"
__author__ = "Divyansh Singh"
