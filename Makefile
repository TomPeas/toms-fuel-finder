# Local Docker workflow for toms-fuel-finder.
#
# Override the defaults on the command line if needed, e.g.:
#   make run PORT=9000
#   make build IMAGE=toms-fuel-finder:dev

IMAGE ?= toms-fuel-finder
PORT  ?= 8000
NAME  ?= toms-fuel-finder

# Pass these through from the current shell environment (no value = use host's).
ENV_FLAGS = -e GOV_CLIENT_ID -e GOV_CLIENT_SECRET -e GOV_BASE_URL

.PHONY: build run run-bg stop logs shell

## Build the image locally
build:
	podman build -t $(IMAGE) .

## Run in the foreground (Ctrl-C to stop). Reads GOV_CLIENT_ID /
## GOV_CLIENT_SECRET / GOV_BASE_URL from your shell environment.
run:
	podman run --rm -p $(PORT):8000 $(ENV_FLAGS) --name $(NAME) $(IMAGE)

## Run detached in the background
run-bg:
	podman run --rm -d -p $(PORT):8000 $(ENV_FLAGS) --name $(NAME) $(IMAGE)

## Stop the background container
stop:
	podman stop $(NAME)

## Tail logs of the running container
logs:
	podman logs -f $(NAME)

## Open a shell inside the running container (debugging)
shell:
	podman exec -it $(NAME) /bin/bash
