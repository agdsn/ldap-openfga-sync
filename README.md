# LDAP to OpenFGA Group Membership Sync

This script synchronizes group memberships from LDAP to OpenFGA using the [diffsync](https://github.com/networktocode/diffsync) library.

## Features

- Syncs group memberships from LDAP to OpenFGA
- Uses diffsync library to calculate and apply only the necessary changes
- Supports dry-run mode to preview changes before applying them
- Users are identified by a configurable LDAP attribute (default: `uid`)
- Comprehensive logging
- Runs as non-root user for enhanced security

## Requirements

- Python 3.8+
- LDAP server with group memberships
- OpenFGA instance

## Installation

1. Clone this repository:
```bash
git clone <repository-url>
cd ldap-openfga-sync
```

2. Create a virtual environment:
```bash
python3 -m venv .venv
source .venv/bin/activate  # On Linux/Mac
# or
.venv\Scripts\activate  # On Windows
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Copy the example environment file and configure it:
```bash
cp .env.example .env
# Edit .env with your configuration
```

## Configuration

Edit the `.env` file with your settings:

### LDAP Configuration

- `LDAP_SERVER`: LDAP server URL (e.g., `ldap://localhost:389` or `ldaps://ldap.example.com:636`)
- `LDAP_BIND_DN`: DN to bind with (e.g., `cn=admin,dc=example,dc=com`)
- `LDAP_BIND_PASSWORD`: Password for the bind DN
- `LDAP_GROUP_BASE_DN`: Base DN to search for groups (e.g., `ou=groups,dc=example,dc=com`)
- `LDAP_USER_BASE_DN`: Base DN where users are located (for `memberOf` queries). Only used when `LDAP_USE_MEMBEROF=true`.
- `LDAP_GROUP_FILTER`: LDAP filter to find groups when discovering all groups (default: `(objectClass=groupOfNames)`)
- `LDAP_MEMBER_ATTRIBUTE`: Attribute containing group members. Only used when `LDAP_USE_MEMBEROF=false` (default: `member`)
- `LDAP_USE_TLS`: Whether to use TLS (true/false)
- `LDAP_CA_CERT_FILE`: Path to custom CA certificate file for TLS verification (optional, for self-signed certificates)
- `LDAP_USE_MEMBEROF`: Use `memberOf` attribute for reverse lookup (default: `false`)
  - **When true**: Queries users for `memberOf` attribute. Recommended for FreeIPA/Active Directory. Supports inherited/nested groups automatically.
  - **When false**: Queries groups for `member` attribute. Works with any LDAP. Direct members only.
- `LDAP_USERNAME_ATTRIBUTE`: LDAP attribute to use as username identifier (default: `uid`). This attribute is read from LDAP users and used to identify them in OpenFGA. Common values: `uid`, `mail`

### OpenFGA Configuration

- `OPENFGA_API_URL`: OpenFGA API URL (e.g., `http://localhost:8080`)
- `OPENFGA_STORE_ID`: Your OpenFGA store ID
- `OPENFGA_API_TOKEN`: API token for authentication (optional)
- `OPENFGA_AUTHORIZATION_MODEL_ID`: Authorization model ID (optional)

### Sync Configuration

- `SYNC_GROUPS`: Comma-separated list of groups to sync (e.g., `developers,operations,managers`). If not specified or empty, all groups from LDAP will be synced.
- `SYNC_INTERVAL_SECONDS`: Sync interval in seconds (default: `21600` = 6 hours). Only used in Docker/containerized environments.
- `SYNC_DRY_RUN`: Set to `true` for dry-run mode (preview changes without applying them)

## Quick Start

1. **Validate your configuration:**
   ```bash
   python validate_config.py
   ```

2. **Test your connections:**
   ```bash
   python test_connections.py
   ```

3. **Run a dry-run sync:**
   ```bash
   SYNC_DRY_RUN=true python sync.py
   ```

4. **Run the actual sync:**
   ```bash
   python sync.py
   ```

## Deployment Options


### Docker Deployment

Deploy using Docker for simpler setups. The container runs the sync automatically every 6 hours.

#### Quick Start with Docker

```bash
# Pull the image
docker pull ghcr.io/agdsn/ldap-openfga-sync:latest

# Create configuration
cp .env.example .env
# Edit .env with your settings

# Run the container
docker run -d \
  --name ldap-openfga-sync \
  --env-file .env \
  -v $(pwd)/logs:/var/log/ldap-openfga-sync \
  ghcr.io/agdsn/ldap-openfga-sync:latest
```

## Usage

### Basic Usage

Run the sync script:

```bash
python sync.py
```

### Dry Run Mode

To preview changes without applying them:

```bash
# Set SYNC_DRY_RUN=true in .env, or:
SYNC_DRY_RUN=true python sync.py
```

### Testing Connections

Before running the sync, you can test your connections:

```bash
python test_connections.py
```

This will verify:
- LDAP connection and ability to query groups
- OpenFGA connection and ability to read tuples

## How It Works

1. **Connect to OpenFGA**: The script connects to OpenFGA 
2. **Connect to LDAP**: Connects to LDAP and queries for group memberships
3. **Filter Groups**: Only processes configured groups (or all groups if SYNC_GROUPS is empty)
4. **Extract Usernames**: Queries the configured username attribute (default: `preferredUsername`) from LDAP users
5. **Load Data**: Loads memberships from both LDAP and OpenFGA into diffsync adapters
6. **Calculate Diff**: Uses diffsync to automatically calculate the differences
7. **Apply Changes**: Uses diffsync's built-in CRUD operations (`create()` and `delete()` methods in the model) to queue changes
8. **Execute Operations**: Executes all queued operations asynchronously to update OpenFGA

The sync uses diffsync's native sync mechanism (`sync_from()`) which automatically:
- Detects new memberships that need to be created
- Identifies obsolete memberships that need to be deleted
- Invokes the model's `create()` and `delete()` methods
- Maintains consistency between LDAP (source) and OpenFGA (target)

## OpenFGA Data Model

The script expects the following OpenFGA relationship structure:

```
user:username member group:groupname
```

Where:
- User type: `user` (identified by username from LDAP, configurable via `LDAP_USERNAME_ATTRIBUTE`)
- Relation: `member`
- Object type: `group` (identified by group name)

## LDAP Requirements

- Groups must have a `cn` attribute (used as the group name)
- Groups must have a member attribute (configurable via `LDAP_MEMBER_ATTRIBUTE`, default: `member`) when using member attribute mode
- Users must have the configured username attribute (configurable via `LDAP_USERNAME_ATTRIBUTE`, default: `uid`)
  - Common attributes: `uid`, `mail`
A comprehensive test suite is included with Docker Compose environment:

```bash
# Start test environment (LDAP + OpenFGA)
./test.sh start

# Run all tests
./test.sh test

# Stop test environment
./test.sh stop
```

See [TESTING.md](TESTING.md) for detailed testing documentation.

## Development

To contribute or modify the script:

1. Install development dependencies (if any)
2. Make your changes
3. Run the test suite: `./test.sh restart test`
4. Test thoroughly in dry-run mode first
5. Submit a pull request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
