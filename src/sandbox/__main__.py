# import asyncio
import asyncio
import json
import os
import sys
from .sandbox_models import SandboxConfig, FinalAnswer
from .execute import execute
from pydantic import ValidationError
from .constants import safe_builtins
import traceback
from .constants import (
    DEFAULT_MCP_CMD_MBPP,
    DEFAULT_MCP_CMD_SWEB,
    DEFAULT_MCP_CMD
    )
from .mcp_client import MCPClient


class Sandbox:
    def __init__(self, input_data: str | None = None):
        self.output = ""
        input_data = input_data if input_data is not None else sys.stdin.read()
        try:
            inputs = json.loads(input_data)
            self.config = SandboxConfig.model_validate(inputs["config"])
            task_type = inputs["task_type"]
            self.task_type = task_type
            if self.config.mcp_command is None:
                if task_type == 'mbpp':
                    self.config.mcp_command = DEFAULT_MCP_CMD_MBPP
                elif task_type == 'swebench':
                    self.config.mcp_command = DEFAULT_MCP_CMD_SWEB
                else:
                    self.config.mcp_command = DEFAULT_MCP_CMD
            self.code = inputs["code"]
            if "eval_script" in inputs:
                self.eval_script = inputs["eval_script"]
            else:
                self.eval_script = None
            if "test_list" in inputs:
                self.test_list = inputs["test_list"]
            else:
                self.test_list = None
            self.mcp_client = MCPClient(
                task_type=task_type,
                config=self.config,
                eval_script=self.eval_script,
                test_list=self.test_list,
                code=self.code
                )
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            # TODO: self.restricted_globals defined
            self.restricted_globals = self.loop.run_until_complete(
                self.mcp_client.connect_server()
            )
            self.restricted_globals = self.loop.run_until_complete(
                self.build_globals()
            )
        except json.JSONDecodeError as e:
            print(json.dumps({
                "success": False,
                "output": "",
                "error": f"Invalid JSON input to the sandbox container: {e}"
            }))
            sys.exit(1)
        except ValidationError as e:
            print(json.dumps({
                "success": False,
                "output": "",
                "error": f"Caught ValidationError while parsing "
                         f"configuration: {e}"
            }))
            sys.exit(1)
        except KeyError as e:
            print(json.dumps({
                "success": False,
                "output": "",
                "error": f"Mandatory key not present: {e}"
            }))
            sys.exit(1)
        except Exception as e:
            print(json.dumps({
                "success": False,
                "output": "",
                "error": f"Caught unexpected Exception: {e}"
            }))
            sys.exit(1)

    def execute(self):
        try:
            result = execute(
                code=self.code,
                config=self.config,
                restricted_globals=self.restricted_globals)
            if result.output:
                # self.output += f"\nExecution ouput:\n{result.output}"
                self.output += f"{result.output}"
            if result.success and result.final_answer:
                print(json.dumps({
                    "success": True,
                    "final_answer": result.final_answer,
                    "output": f"{self.mcp_client.messages}\n{self.output}"
                }))
            elif result.success:
                print(json.dumps({
                    "success": True,
                    "output": f"{self.mcp_client.messages}\n{self.output}",
                    "error": result.error or "No error from execution"
                }))
            else:
                print(json.dumps({
                    "success": False,
                    "output": f"{self.mcp_client.messages}\n{self.output}",
                    "error": result.error or "No error from execution"
                }))
        except SystemExit as e:
            output = f"{self.mcp_client.messages}\n{self.output}"
            output += f"\nScript exited early with code {e.code}"
            print(json.dumps({
                "success": False,
                "output": output,
                "error": f"Early SystemExit with code {str(e)}"
            }))
        except KeyboardInterrupt:
            print(json.dumps({
                "success": False,
                "output": f"{self.mcp_client.messages}\n{self.output}",
                "error": "User interrupted the execution"
            }))
        except Exception as e:
            tb_str = traceback.format_exc()
            print(json.dumps({
                "success": False,
                "output": f"{self.mcp_client.messages}\n{self.output}",
                "error": f"{type(e).__name__}: {str(e)}\n{tb_str}"
            }))

    def restricted_import_factory(self):
        """Create import filter bound to config"""
        def restricted_import(name, *args, **kwargs):
            if name in self.config.authorized_imports:
                return __import__(name, *args, **kwargs)
            authorized_imports_str = ""
            for item in self.config.authorized_imports:
                authorized_imports_str += f"{item}, "
                if item.endswith('.*'):
                    prefix = item[:-2]
                    if name == prefix or name.startswith(prefix + '.'):
                        return __import__(name, *args, **kwargs)
            authorized_imports_str = authorized_imports_str[:-2]
            message = f"Import of '{name}' is not allowed.\n"
            message += f"Authorized imports: {authorized_imports_str}"
            raise ImportError(message)
        return restricted_import

    def restricted_open_factory(self):
        allowed = [
            os.path.realpath(p)
            for p in self.config.allowed_directories
        ]

        def restricted_open(path, *args, **kwargs):
            real = os.path.realpath(path)
            for root in allowed:
                if (real == root
                        or real.startswith(root + os.sep)):
                    return open(real, *args, **kwargs)
            raise PermissionError(f"Unauthorized path: {path}")

        return restricted_open

    async def build_globals(self):
        builtins = safe_builtins.copy()
        builtins["open"] = self.restricted_open_factory()
        builtins['__import__'] = self.restricted_import_factory()
        tool_wrappers = await self.mcp_client.build_tool_wrappers(
            loop=self.loop)
        restricted_globals = {
            '__builtins__': builtins,
            'final_answer': self.handle_final_answer,
            'eval_script': self.eval_script,
            **tool_wrappers
        }
        return restricted_globals

    def handle_final_answer(self, answer: str):
        raise FinalAnswer(answer)


if __name__ == '__main__':
    sandbox = Sandbox()
    sandbox.execute()

# if __name__ == '__main__':
#     config = SandboxConfig()
#     conf_dict = config.model_dump()
#     code = """
# result = edit_file("/testbed/django/db/models/fields/related.py", "kwargs['to'] = self.remote_field.model.lower()", "app_label, model_name = self.remote_field.model.split('.'); kwargs['to'] = '%s.%s' % (app_label, model_name.lower())")
# print(result)
# run_tests()
# """
#     print(f"code:\n{code}")
#     eval_script = "#!/bin/bash\nset -uxo pipefail\nsource /opt/miniconda3/bin/activate\nconda activate testbed\ncd /testbed\nsed -i '/en_US.UTF-8/s/^# //g' /etc/locale.gen && locale-gen\nexport LANG=en_US.UTF-8\nexport LANGUAGE=en_US:en\nexport LC_ALL=en_US.UTF-8\ngit config --global --add safe.directory /testbed\ncd /testbed\ngit status\ngit show\ngit -c core.fileMode=false diff 09914ccf688974e068941f55412b930729bafa06\nsource /opt/miniconda3/bin/activate\nconda activate testbed\npython -m pip install -e .\ngit checkout 09914ccf688974e068941f55412b930729bafa06 tests/migrations/test_state.py\ngit apply -v - <<'EOF_114329324912'\ndiff --git a/tests/migrations/test_state.py b/tests/migrations/test_state.py\n--- a/tests/migrations/test_state.py\n+++ b/tests/migrations/test_state.py\n@@ -867,6 +867,34 @@ class Meta:\n         with self.assertRaisesMessage(ValueError, msg):\n             project_state.apps\n \n+    def test_reference_mixed_case_app_label(self):\n+        new_apps = Apps()\n+\n+        class Author(models.Model):\n+            class Meta:\n+                app_label = 'MiXedCase_migrations'\n+                apps = new_apps\n+\n+        class Book(models.Model):\n+            author = models.ForeignKey(Author, models.CASCADE)\n+\n+            class Meta:\n+                app_label = 'MiXedCase_migrations'\n+                apps = new_apps\n+\n+        class Magazine(models.Model):\n+            authors = models.ManyToManyField(Author)\n+\n+            class Meta:\n+                app_label = 'MiXedCase_migrations'\n+                apps = new_apps\n+\n+        project_state = ProjectState()\n+        project_state.add_model(ModelState.from_model(Author))\n+        project_state.add_model(ModelState.from_model(Book))\n+        project_state.add_model(ModelState.from_model(Magazine))\n+        self.assertEqual(len(project_state.apps.get_models()), 3)\n+\n     def test_real_apps(self):\n         \"\"\"\n         Including real apps can resolve dangling FK errors.\n\nEOF_114329324912\n: '>>>>> Start Test Output'\n./tests/runtests.py --verbosity 2 --settings=test_sqlite --parallel 1 migrations.test_state\n: '>>>>> End Test Output'\ngit checkout 09914ccf688974e068941f55412b930729bafa06 tests/migrations/test_state.py\n"
#     inputs = {
#         "config": conf_dict,
#         "task_type": "swebench",
#         "code": code,
#         "eval_script": eval_script
#     }
#     sandbox = Sandbox(json.dumps(inputs))
#     sandbox.execute()
