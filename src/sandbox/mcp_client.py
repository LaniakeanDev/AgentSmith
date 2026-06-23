# BS

import subprocess
import json


class MCPClient:
    def __init__(self, command):
        self.proc = subprocess.Popen(
            command,
            shell=True,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True
        )
        self.next_id = 1

    def request(self, method, params=None):
        req = {
            "jsonrpc": "2.0",
            "id": self.next_id,
            "method": method
        }

        if params:
            req["params"] = params

        self.next_id += 1

        self.proc.stdin.write(
            json.dumps(req) + "\n"
        )
        self.proc.stdin.flush()

        return json.loads(
            self.proc.stdout.readline()
        )

    def list_tools(self):
        return self.request(
            "tools/list"
        )["result"]["tools"]

    def call_tool(
        self,
        name,
        arguments
    ):
        return self.request(
            "tools/call",
            {
                "name": name,
                "arguments": arguments
            }
        )["result"]
