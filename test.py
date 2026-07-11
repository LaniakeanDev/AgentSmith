from typing import Dict

import os
import re
import subprocess
import asyncio
import json
import sys
from typing import Optional
from src.agent_swebench.agent_swebench import SWEBenchAgent
import fire
from sandbox.sandbox_models import SandboxConfig
from src.agent_swebench.swebench_models import SWEBenchTaskInput


def launch(task_file):
    config = SandboxConfig()
    with open(task_file, 'r') as f:
        task_data = json.load(f)
    task = SWEBenchTaskInput.model_validate(task_data)
    agent = SWEBenchAgent(
        provider_model="",
        provider_url="provider_url",
        max_iterations=2,
        config=config,
        task=task)
    agent.build_image()
    agent.start_container()
    print("Executing in sandbox...")
    agent.sandbox_exec("print(run_tests())")
    print("Execution finished. Stopping container...")
    agent.stop_container()


launch("cache/swebench_task.json")
