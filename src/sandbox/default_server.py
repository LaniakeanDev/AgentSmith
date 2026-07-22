import os

from mcp.server.fastmcp import FastMCP

transport = os.environ.get('transport')

mcp_url = "http://127.0.0.1:4242"

if transport == 'http':
    mcp_url = os.environ.get('mcp_url')


if mcp_url.startswith('http://'):
    mcp_url = mcp_url[7:]
elif mcp_url.startswith('https://'):
    mcp_url = mcp_url[8:]

split_url = mcp_url.split(':')
port_str = split_url.pop()
try:
    port = int(port_str)
except ValueError:
    split_url = mcp_url.split(':')
    port = 4242

host = split_url[0]

# Create an MCP server
mcp = FastMCP(
    "AgentSmith",
    json_response=True,
    # host="127.0.0.1",
    host=host,
    port=port,
)


if __name__ == "__main__":
    if transport == 'stdio':
        mcp.run(transport="stdio")
    else:
        mcp.run(transport="streamable-http")
