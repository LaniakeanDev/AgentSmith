

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
