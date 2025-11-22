# Project Structure

The LDAP to OpenFGA sync script is now organized into separate modules for better maintainability.

## File Organization

```
ldap-openfga-sync/
├── sync.py              # Main script - orchestrates the sync process
├── models.py            # DiffSync models (GroupMembership)
├── ldap_adapter.py      # LDAP adapter - reads memberships from LDAP
├── openfga_adapter.py   # OpenFGA adapter - reads/writes memberships in OpenFGA
├── test_connections.py  # Test script to verify LDAP and OpenFGA connectivity
├── validate_config.py   # Configuration validation script
├── requirements.txt     # Python dependencies
├── .env                 # Configuration (not in git)
├── .env.example         # Example configuration
├── .gitignore          # Git ignore patterns
├── README.md           # Main documentation
├── EXAMPLE.md          # Complete walkthrough and examples
└── OPENFGA_MODEL.md    # OpenFGA model reference
```

## Module Descriptions

### `models.py`
Defines the DiffSync data models used by both adapters. Implements CRUD operations following diffsync's pattern.

**Classes:**
- `GroupMembership`: Represents a user's membership in a group
  - Identifiers: `user_email`, `group_name`
  - Methods:
    - `create(adapter, ids, attrs)`: Creates a new membership (queues operation for OpenFGA)
    - `delete()`: Deletes a membership (queues operation for OpenFGA)

### `ldap_adapter.py`
Handles all LDAP-related operations.

**Classes:**
- `LDAPAdapter`: DiffSync adapter for LDAP
  - Connects to LDAP server
  - Queries groups and memberships
  - Extracts user emails from LDAP DNs
  - Filters groups based on OpenFGA availability

**Key Methods:**
- `connect_ldap()`: Establish LDAP connection
- `disconnect_ldap()`: Close LDAP connection
- `set_valid_groups(groups)`: Set which groups to sync
- `extract_email_from_dn(dn)`: Extract email from user DN
- `load()`: Load memberships from LDAP

### `openfga_adapter.py`
Handles all OpenFGA-related operations.

**Classes:**
- `OpenFGAAdapter`: DiffSync adapter for OpenFGA
  - Connects to OpenFGA API
  - Reads existing memberships (filters for 'member' relation only)
  - Writes new memberships
  - Deletes removed memberships
  - Supports dry-run mode
  - Queues operations during diffsync and executes them asynchronously

**Key Methods:**
- `connect_openfga()`: Establish OpenFGA connection
- `get_existing_groups()`: Query all groups in OpenFGA
- `load()`: Load memberships from OpenFGA
- `add_membership(user_email, group_name)`: Add a membership
- `remove_membership(user_email, group_name)`: Remove a membership
- `execute_pending_operations()`: Execute all queued operations from diffsync
- `close()`: Close the OpenFGA client connection and cleanup resources

### `sync.py`
Main orchestration script that coordinates the sync process.

**Functions:**
- `sync_ldap_to_openfga()`: Main async function that:
  1. Connects to both systems
  2. Loads data from both sources
  3. Uses diffsync's `sync_from()` to automatically calculate and apply changes
  4. Executes queued operations in OpenFGA
  5. Properly closes connections and cleans up resources

## Data Flow

```
┌─────────────────┐
│   LDAP Server   │
│   (Groups +     │
│    Members)     │
└────────┬────────┘
         │
         ↓ read
┌────────────────────┐
│  LDAPAdapter       │
│  - Query groups    │
│  - Extract emails  │
│  - Load to store   │
└────────┬───────────┘
         │
         ↓ load
┌────────────────────┐
│   GroupMembership  │
│   (DiffSync Model) │
│   - create()       │
│   - delete()       │
└────────┬───────────┘
         │
         ↓ sync_from()
┌────────────────────┐
│   DiffSync Engine  │
│   - Calculate Δ    │
│   - Call CRUD      │
└────────┬───────────┘
         │
         ↓ queue operations
┌────────────────────┐
│  OpenFGAAdapter    │
│  - Pending ops []  │
│  - Execute async   │
└────────┬───────────┘
         │
         ↓ write
┌────────────────────┐
│  OpenFGA Server    │
│  (Updated Members) │
└────────────────────┘
```

## Extending the Code

### Adding Support for Additional Relations

To sync other relations (e.g., `admin`, `owner`), you would:

1. Add new models in `models.py`:
```python
class GroupAdmin(DiffSyncModel):
    _modelname = "admin"
    _identifiers = ("user_email", "group_name")
    _attributes = ()
    
    user_email: str
    group_name: str
    
    @classmethod
    def create(cls, adapter, ids, attrs):
        """Create admin relationship."""
        admin = cls(**ids, **attrs)
        admin.adapter = adapter
        if hasattr(adapter, 'pending_operations'):
            adapter.pending_operations.append(('create_admin', admin.user_email, admin.group_name))
        return admin
    
    def delete(self):
        """Delete admin relationship."""
        if hasattr(self.adapter, 'pending_operations'):
            self.adapter.pending_operations.append(('delete_admin', self.user_email, self.group_name))
        return self
```

2. Register the model in both adapters:
```python
# In both LDAPAdapter and OpenFGAAdapter
admin = GroupAdmin
top_level = ["membership", "admin"]
```

3. Update `execute_pending_operations()` in `openfga_adapter.py` to handle the new operations
4. The sync logic in `sync.py` requires no changes - diffsync handles it automatically!

### Adding Custom Email Extraction

To customize how emails are extracted from LDAP DNs, modify the
`extract_email_from_dn()` method in `ldap_adapter.py`.

### Adding Logging to Files

To log to a file, update the logging configuration in `sync.py`:

```python
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/ldap-openfga-sync.log'),
        logging.StreamHandler()
    ]
)
```

## Testing

Each module can be tested independently:

```bash
# Test the models
python -c "from models import GroupMembership; m = GroupMembership(user_email='test@example.com', group_name='developers'); print(m)"

# Test LDAP connection (requires valid .env)
python -c "from ldap_adapter import LDAPAdapter; a = LDAPAdapter(); a.connect_ldap(); a.disconnect_ldap()"

# Test OpenFGA connection (requires valid .env)
python -c "import asyncio; from openfga_adapter import OpenFGAAdapter; a = OpenFGAAdapter(); asyncio.run(a.connect_openfga())"

# Full connection test
python test_connections.py
```

## Import Dependencies

```
models.py
  └─ diffsync

ldap_adapter.py
  ├─ diffsync
  ├─ ldap
  └─ models

openfga_adapter.py
  ├─ diffsync
  ├─ openfga_sdk
  └─ models

sync.py
  ├─ ldap_adapter
  └─ openfga_adapter
```

## Benefits of Modular Structure

1. **Separation of Concerns**: Each module has a clear, single responsibility
2. **Testability**: Modules can be tested independently
3. **Maintainability**: Changes to LDAP logic don't affect OpenFGA logic and vice versa
4. **Reusability**: Adapters can be reused in other projects
5. **Readability**: Smaller, focused files are easier to understand
6. **Extensibility**: Easy to add new adapters or models

