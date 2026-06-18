

install_docker_sandbox:
	cd src/sandbox && \
	uv lock && \
	cd ../.. && \
	docker build -t sandbox-image src/sandbox
