from mcp.server.fastmcp import FastMCP

from secure_agent.mcp.tools.calculator import calculate
from secure_agent.mcp.tools.products import get_product


server = FastMCP("secure-agent-tools")

server.tool()(calculate)
server.tool()(get_product)


def main() -> None:
    server.run(transport="stdio")


if __name__ == "__main__":
    main()