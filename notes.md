how can I set up communication between client and server?


Since the server is external and the container has network access, the simplest setup is:

**For stdio**: the host process that launches the Docker container spawns the MCP server, then passes its address/socket to the container. But this is complex.

**For HTTP**: the MCP server runs on the host, and the client inside the container reaches it via `host.docker.internal` (on Docker Desktop) or the host's gateway IP (on Linux, typically `172.17.0.1`):

```python
async def connect_to_http_server(self, server_url: str):
    from mcp.client.streamable_http import streamablehttp_client
    
    http_transport = await self.exit_stack.enter_async_context(
        streamablehttp_client(server_url)
    )
    self.session = await self.exit_stack.enter_async_context(
        ClientSession(*http_transport)
    )
    await self.session.initialize()
```

Then when launching the container, you pass the server URL as an argument:
```bash
docker run ... sandbox-image uv run python -m sandbox --mcp-server http://host.docker.internal:8000
```

The host starts the MCP server before launching the container:
```bash
# On host
python mcp_tools_swebench.py &  # starts HTTP server on port 8000
# Then launch container with --mcp-server http://host.docker.internal:8000
```

This matches the spec's CLI exactly:
```bash
uv run sandbox --mcp-server <URL>
```


---------------------
---------------------
---------------------
---------------------
---------------------
---------------------
---------------------
---------------------
---------------------
---------------------
---------------------
---------------------
---------------------
---------------------
---------------------
---------------------
---------------------
---------------------
---------------------
---------------------
---------------------





For stdio with an external server, the communication goes through the Docker container's own stdin/stdout pipes. The host process:

1. Spawns the MCP server as a subprocess
2. Launches the Docker container
3. Relays bytes between the two

Here's how it works:

```
Host:
MCP Server (subprocess) <--pipes--> Relay <--docker stdin/stdout--> Container (MCP client)
```

Concretely on the host side:

```python
import subprocess
import threading

def relay(src, dst):
    while True:
        data = src.read(4096)
        if not data:
            break
        dst.write(data)
        dst.flush()

# Start MCP server
mcp_server = subprocess.Popen(
    ["python", "mcp_tools_mbpp.py"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
)

# Start sandbox container
container = subprocess.Popen(
    ["docker", "run", "--rm", "-i", "sandbox-image", 
     "uv", "run", "python", "-m", "sandbox", "--mcp-stdio"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
)

# Relay between the two
t1 = threading.Thread(target=relay, args=(mcp_server.stdout, container.stdin))
t2 = threading.Thread(target=relay, args=(container.stdout, mcp_server.stdin))
t1.start()
t2.start()
t1.join()
t2.join()
```

Inside the container, your MCP client then connects to its own stdin/stdout as if it were talking directly to the server:

```python
from mcp.client.stdio import stdio_client
from mcp import ClientSession, StdioServerParameters
import sys

async def connect_stdio(self):
    # Instead of spawning a subprocess, read/write container's own stdin/stdout
    server_params = StdioServerParameters(
        command="cat",  # dummy — we'll override transport
        args=[],
    )
    # Use sys.stdin.buffer / sys.stdout.buffer as the transport
    from mcp.client.stdio import StdioTransport
    transport = StdioTransport(
        read_stream=sys.stdin.buffer,
        write_stream=sys.stdout.buffer,
    )
    self.session = await self.exit_stack.enter_async_context(
        ClientSession(transport.read, transport.write)
    )
    await self.session.initialize()
```

The key insight is that with `-i` (interactive) Docker flag, the container's stdin/stdout are pipes the host controls — so the host can relay them to the MCP server's stdin/stdout, making the container's MCP client believe it's talking directly to the server via stdio, even though the server is outside.