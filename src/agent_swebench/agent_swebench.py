import asyncio
# import re
import sys
# from typing import List
from agent_mbpp.agent_mbpp import MBPPAgent
# from agent_mbpp.mbpp_models import (
#     CallMetrics, MBPPTaskInput, SolutionOutput, StepMetrics)
# import requests
# import time
# import os
# from dotenv import load_dotenv
from sandbox.mcp_client import MCPClient
# from sandbox.sandbox_models import ExecutionResult, SandboxConfig
# from sandbox.spawner import Spawner
# from groq import Groq


class SWEBenchAgent(MBPPAgent):
    def __init__(
            self,
            provider_model: str,
            provider_url: str,
            max_iterations: int):
        super().__init__(provider_model, provider_url, max_iterations)

    def get_sandbox_manual(self):
        self.get_mcp_manual()

    async def get_mcp_manual(self):
        client = MCPClient("python sandbox/swebench_server.py")
        try:
            await client.connect_server()
        except Exception as e:
            print(e)
            sys.exit(1)
        await client.get_tools()
        manual = client.generate_sandbox_manual()
        print(f"Manual retrieved:\n{manual}")
        await client.cleanup()


if __name__ == '__main__':
    agent = SWEBenchAgent("", "", 2)
    asyncio.run(agent.get_mcp_manual())
