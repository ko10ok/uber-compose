# Release Tags

## Versioning

**Library version** is stored in `uber_compose/version` file

Uses [PEP 440](https://peps.python.org/pep-0440/) with short notation: `a`, `b`, `rc`

## Creating Tags

```bash
# Stable release
make tag                      # v2.0.0

# Pre-release versions
make tag-alpha               # v2.0.0a1, v2.0.0a2, ...
make tag-beta                # v2.0.0b1, v2.0.0b2, ...
make tag-rc                  # v2.0.0rc1, v2.0.0rc2, ...

# Show current version tags
make show-tags

# Publish tags (triggers CI/CD)
make push-tags
```

## Examples

### Typical Workflow

```bash
# 1. Create beta version
make tag-beta && make push-tags      # v2.0.0b1

# 2. After fixes - next beta
make tag-beta && make push-tags      # v2.0.0b2

# 3. Release candidate
make tag-rc && make push-tags        # v2.0.0rc1

# 4. Stable release
make tag && make push-tags           # v2.0.0
```

### View Tags

```bash
$ make show-tags
Tags for version 2.0.0:
v2.0.0a1
v2.0.0b1
v2.0.0b2
v2.0.0rc1
v2.0.0
```

## Installing Versions

```bash
# Specific version
pip install uber-compose==2.0.0b1

# Latest pre-release
pip install --pre uber-compose

# Latest stable
pip install uber-compose
```

## Tag Format

| Type | Format | PyPI | Description |
|------|--------|------|-------------|
| Alpha | `v2.0.0a1` | `2.0.0a1` | Early testing |
| Beta | `v2.0.0b1` | `2.0.0b1` | Stabilization |
| RC | `v2.0.0rc1` | `2.0.0rc1` | Release candidate |
| Stable | `v2.0.0` | `2.0.0` | Final release |

**PyPI sorting:** `2.0.0a1` < `2.0.0b1` < `2.0.0rc1` < `2.0.0`

## Important

- ✅ Commands auto-increment version numbers (a1→a2→a3)
- ✅ Tags are created locally until `make push-tags`
- ⚠️ Published PyPI versions cannot be changed
