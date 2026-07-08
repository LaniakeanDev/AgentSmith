




## MBPP Moulinette

[terminal 1 (moulinette venv activated)]
```bash
systemctl --user start podman.socket
podman system service --time=0
```

[terminal 2 (moulinette venv activated)]
```bash
podman pull python:3.11-slim
export DOCKER_HOST=unix://$XDG_RUNTIME_DIR/podman/podman.sock
uv run moulinette_eval validate mbpp ../cache/mbpp_task.json ../cache/mbpp_solution.json
```

## SWEBench Moulinette

```bash
docker pull image_name
```

