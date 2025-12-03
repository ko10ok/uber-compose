# X-Migration

Mechanism for executing initialization and migration commands during service startup.

## Core Concepts

**x-migration** — section in `docker-compose.yml` for automatic command execution at specific stages of service lifecycle.

### Execution Stages

- **before_all** — runs before any services start
- **before_start** — runs before specific service starts
- **after_start** — runs immediately after service starts
- **after_healthy** — runs after service becomes healthy
- **after_all** — runs after all environment services are started

## Syntax

### Basic Format

```yaml
services:
  app:
    image: myapp:latest
    x-migration:
      - before_all: echo "Before all services"
      - before_start: echo "Before app starts"
      - after_start: echo "After app started"
      - after_healthy: echo "App is healthy"
      - after_all: echo "All services ready"
```

### Execute in Another Service

```yaml
services:
  app:
    image: myapp:latest
    
  db:
    image: postgres:14
    x-migration:
      # Execute in app before db starts
      - before_start: [[python manage.py check], app]
      # Execute in app after db starts
      - after_start: [[python manage.py migrate], app]
```

## Usage Examples

### 1. Simple Database Migration

```yaml
services:
  db:
    image: postgres:14
    x-migration:
      - after_start: psql -c "CREATE DATABASE testdb;"
      - after_all: psql -c "GRANT ALL ON DATABASE testdb TO user;"
```

### 2. Command Sequence

```yaml
services:
  app:
    image: myapp:latest
    x-migration:
      - after_start: python manage.py migrate
      - after_start: python manage.py createsuperuser --noinput
      - after_start: python manage.py loaddata fixtures.json
```

Commands execute **sequentially** — next command starts after previous completes.

### 3. Migration with Dependencies

```yaml
services:
  db:
    image: postgres:14
    x-migration:
      - after_start: psql -c "CREATE DATABASE app;"
  
  app:
    image: myapp:latest
    depends_on:
      db:
        condition: service_healthy
    x-migration:
      - after_start: python manage.py migrate
      - after_all: python manage.py seed_data
```

Migrations respect **depends_on** — execute after dependent services start.

### 4. Cross-Service Migrations

```yaml
services:
  app:
    image: myapp:latest
  
  db:
    image: postgres:14
    x-migration:
      # Execute migration in app after db starts
      - after_start: [[python manage.py migrate], app]
```

### 5. Multiple Service Initialization

```yaml
services:
  cache:
    image: redis:7
    x-migration:
      - after_start: redis-cli SET init "done"
  
  queue:
    image: rabbitmq:3
    x-migration:
      - after_start: rabbitmqctl add_user app password
      - after_start: rabbitmqctl set_permissions app ".*" ".*" ".*"
  
  app:
    image: myapp:latest
    depends_on:
      - cache
      - queue
    x-migration:
      - after_start: python manage.py migrate
      - after_all: python manage.py warmup_cache
```

### 6. Full Lifecycle with before_start

```yaml
services:
  db:
    image: postgres:14
    x-migration:
      - before_all: echo "Preparing environment"
      - after_start: psql -c "CREATE DATABASE app;"
  
  app:
    image: myapp:latest
    depends_on:
      db:
        condition: service_healthy
    x-migration:
      # Check before start in db
      - before_start: [[psql -c "SELECT 1;"], db]
      # Migration after start
      - after_start: python manage.py migrate
      # Finalization after all services
      - after_all: python manage.py seed_data
```

## Features

✅ **Sequential execution** — commands for one service execute in order  
✅ **Dependency-aware** — respects `depends_on` between services  
✅ **Cross-service execution** — can run commands on other containers  
✅ **Test integration** — automatically applied with `UberCompose().up()`

### Stage Execution Order

1. **before_all** — once before all services
2. For each dependency tier:
   - **before_start** — before service launch
   - Service startup (docker compose up)
   - **after_start** — immediately after start
   - Wait for healthy state (if configured)
   - **after_healthy** — after becoming healthy
3. **after_all** — once after all services

## Errors

### Wrong Key

❌ `x-migrate` or `x-migrations`  
✅ `x-migration`

### Unknown Stage

```yaml
x-migration:
  - unknown_stage: echo "test"  # ❌ Unsupported stage
```

Use only: `before_all`, `before_start`, `after_start`, `after_healthy`, `after_all`
