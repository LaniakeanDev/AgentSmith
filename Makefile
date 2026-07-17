
socket:
	systemctl --user start podman.socket && \
	podman system service --time=0


SANDBOX_TEMPLATE ?= 

sandbox:
	uv run sandbox $(SANDBOX_TEMPLATE)


run-mbpp:
	uv run python -m agent_mbpp --task-file cache/mbpp_task.json \
--output cache/mbpp_solution.json \
--model-name "model/name" --provider-url "https://provider.api/v1"


# runs in a subshell
dump-swe:
	(cd moulinette && uv run moulinette_eval dump swebench --output ../cache/swebench_task.json)

dump-swe-task-%:
	(cd moulinette && uv run moulinette_eval dump swebench --task-id $* --output ../cache/swebench_task.json)

run-swe:
	uv run python -m agent_swebench --task-file cache/swebench_task.json \
--output cache/swebench_solution.json \
--model-name "model/name" --provider-url "https://provider.api/v1"

install_docker_sandbox:
	cd src/sandbox && \
	uv lock && \
	cd ../.. && \
	docker build -t sandbox-image src/sandbox

# install_docker_sandbox_mbpp:
# 	cd src/sandbox && \
# 	uv lock && \
# 	cd ../../.. && \
# 	docker build -t sandbox_mbpp-image src/sandbox
