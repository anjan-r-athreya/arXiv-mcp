"""FastMCP server instance and tool registration."""

from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    name="arxiv-library",
)

# Tool modules will be imported here as they are created.
# Each module registers tools via @mcp.tool() decorators on this instance.
# Example (uncomment as modules are added):
# import arxiv_library_mcp.tools.import_tools  # noqa: F401
# import arxiv_library_mcp.tools.search_tools  # noqa: F401
# import arxiv_library_mcp.tools.library_tools  # noqa: F401
# import arxiv_library_mcp.tools.export_tools  # noqa: F401
