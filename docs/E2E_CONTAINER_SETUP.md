# E2E Test Container Setup

This guide explains how to configure your test container for running E2E tests with Uber-Compose.

## Prerequisites

Your test container needs Docker Compose CLI to manage services during testing.

## 1. Add Docker Compose CLI to Test Container

Add Docker Compose CLI to your test container's **Dockerfile**:

### Alpine

```dockerfile
RUN apk add docker-cli docker-cli-compose
```

### Debian/Ubuntu

```dockerfile
RUN apt install docker-ce-cli docker-compose-plugin
```

### Legacy docker-compose Binary (if needed)

```dockerfile
# For AMD64
RUN if [[ "$TARGETPLATFORM" = "linux/amd64" ]] ; then \
    curl -SL https://github.com/docker/compose/releases/download/v2.24.4/docker-compose-linux-x86_64 \
    -o /usr/local/bin/docker-compose ; fi

# For ARM64
RUN if [[ "$TARGETPLATFORM" = "linux/arm64" ]] ; then \
    curl -SL https://github.com/docker/compose/releases/download/v2.24.4/docker-compose-linux-aarch64 \
    -o /usr/local/bin/docker-compose ; fi

RUN chmod +x /usr/local/bin/docker-compose
```

## 2. Configure Test Container

Configure your test container in `docker-compose.yml`:

```yaml
services:
  e2e-tests:
    volumes:
      - .:/project
    environment:
      # Docker daemon connection
      - DOCKER_HOST=tcp://test-docker-daemon:2375     # Default: dockersock:2375
      
      # Containers that should not be stopped by Uber-Compose
      - NON_STOP_CONTAINERS=e2e-tests                  # Default: e2e,dockersock
      
      # Project root directory on host machine
      - HOST_PROJECT_ROOT_DIRECTORY=${PWD}             # For project root or test directory
      
      # Unique project name for CI isolation
      - COMPOSE_PROJECT_NAME=${COMPOSE_PROJECT_NAME}   # Setup unique name for CI runs
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DOCKER_HOST` | `tcp://dockersock:2375` | Docker daemon connection URL |
| `NON_STOP_CONTAINERS` | `e2e,dockersock` | Containers excluded from management |
| `HOST_PROJECT_ROOT_DIRECTORY` | - | Path to docker-compose files on host |
| `COMPOSE_PROJECT_NAME` | - | Unique project identifier for CI |


## Example: Complete Setup

### Dockerfile

```dockerfile
FROM python:3.10-alpine

# Install Docker CLI and Compose
RUN apk add --no-cache docker-cli docker-cli-compose

# Install test dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

WORKDIR /project
```

### docker-compose.yml

```yaml
version: "3"

services:
  dockersock:
    image: docker:dind
    privileged: true
    environment:
      - DOCKER_TLS_CERTDIR=
    ports:
      - "2375:2375"

  e2e-tests:
    build: .
    depends_on:
      - dockersock
    volumes:
      - .:/project
    environment:
      - DOCKER_HOST=tcp://dockersock:2375
      - NON_STOP_CONTAINERS=e2e-tests
      - HOST_PROJECT_ROOT_DIRECTORY=${PWD}
      - COMPOSE_PROJECT_NAME=${COMPOSE_PROJECT_NAME:-uber-compose-tests}
    command: tail -f /dev/null
```

## Troubleshooting

### Cannot connect to Docker daemon

Ensure `DOCKER_HOST` points to the correct Docker daemon and it's running:

```bash
docker-compose exec e2e-tests docker ps
```

### Test container stopped unexpectedly

Check `NON_STOP_CONTAINERS` includes your test container:

```bash
echo $NON_STOP_CONTAINERS
```

### Volume mounting issues

Verify `HOST_PROJECT_ROOT_DIRECTORY` is set correctly:

```bash
docker-compose exec e2e-tests env | grep HOST_PROJECT_ROOT_DIRECTORY
```

## Advanced Configuration

Optional environment variables for fine-tuning Uber-Compose behavior.

| Variable | Default | Purpose | Use Case |
|----------|---------|---------|----------|
| `LOG_POLICY` | `DEFAULT` | Control logging verbosity | Primary control via `--uc-v` parameter at runtime. Set to `VERBOSE` for detailed logs during debugging.  |
| `TMP_ENVS_DIRECTORY` | `/tmp/uc-envs` | Temporary environment files storage | Change if `/tmp` has limited space or specific requirements |
| `PROJECT_ROOT_DIRECTORY` | `/project` | Container project root path | Set when project mounted to non-standard location |
| `DOCKER_COMPOSE_FILES_SCAN_DEPTH` | `2` | Directory scan depth for compose files | Increase if compose files nested deeper than 2 levels |
| `DOCKER_COMPOSE_EXTRA_EXEC_PARAMS` | `-T` | Extra parameters for `docker-compose exec` | Modify to add flags like `--user` or remove `-T` for TTY |
| `CLI_COMPOSE_UTIL` | `None` | Override compose CLI path | Set when using standalone `docker-compose` binary. Primary uses `docker compose` |
| `EXEC_PIDS_CHECK_ATTEMPTS_COUNT` | `150` | Process completion check attempts during migrations | Increase for slow systems or long migration times |
| `EXEC_PIDS_CHECK_RETRY_DELAY` | `1` | Delay (seconds) between process completion checks during migrations | Increase to reduce CPU usage on slow systems |
| `IGNORE_PIDOF_UNEXISTANCE` | `True` | Ignore missing `pidof` utility | Set to `False` if strict process checking required |

**Example:**
```yaml
environment:
  # Deeper directory scanning: only project root directory
  - DOCKER_COMPOSE_FILES_SCAN_DEPTH=1  
  
  # Extended monitoring for slow systems
  - EXEC_PIDS_CHECK_ATTEMPTS_COUNT=300
  - EXEC_PIDS_CHECK_RETRY_DELAY=2
```
