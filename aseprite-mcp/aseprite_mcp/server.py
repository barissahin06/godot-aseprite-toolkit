from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError


class NativeMCP(FastMCP):
    async def call_tool(self, name, arguments):
        result = await super().call_tool(name, arguments)
        content = result[0] if isinstance(result, tuple) else result
        if isinstance(content, (list, tuple)):
            for block in content:
                if getattr(block, "type", "") == "text" and (block.text.startswith(("Failed", "ERROR", "Invalid", "Script failed")) or (block.text.startswith("File ") and block.text.endswith("not found"))):
                    raise ToolError(block.text)
        return result
