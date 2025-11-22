# Sample OpenFGA Authorization Model

This is a sample authorization model that supports the group membership relationships
that this sync script manages.

## Model Definition (JSON)

```json
{
  "schema_version": "1.1",
  "type_definitions": [
    {
      "type": "user",
      "relations": {},
      "metadata": {
        "relations": {}
      }
    },
    {
      "type": "group",
      "relations": {
        "member": {
          "this": {}
        },
        "admin": {
          "this": {}
        }
      },
      "metadata": {
        "relations": {
          "member": {
            "directly_related_user_types": [
              {
                "type": "user"
              }
            ]
          },
          "admin": {
            "directly_related_user_types": [
              {
                "type": "user"
              }
            ]
          }
        }
      }
    }
  ]
}
```

## Model Definition (DSL)

```
model
  schema 1.1

type user

type group
  relations
    define member: [user]
    define admin: [user]
```

## Creating the Model

To create this model in OpenFGA:

### Using the CLI:

```bash
# Save the DSL to a file
cat > model.fga << 'EOF'
model
  schema 1.1

type user

type group
  relations
    define member: [user]
    define admin: [user]
EOF

# Create or update the model
fga model write --file model.fga
```

### Using the API:

```bash
curl -X POST http://localhost:8080/stores/{store-id}/authorization-models \
  -H "Content-Type: application/json" \
  -d '{
    "schema_version": "1.1",
    "type_definitions": [
      {
        "type": "user",
        "relations": {}
      },
      {
        "type": "group",
        "relations": {
          "member": {"this": {}},
          "admin": {"this": {}}
        }
      }
    ]
  }'
```

## Creating Groups

Before syncing memberships, you need to create the groups in OpenFGA. This script
only syncs memberships for groups that already exist.

### Using the CLI:

```bash
# Create a group by writing a tuple that references it
fga tuple write user:admin@example.com admin group:developers
```

This creates an `admin` relationship, which implicitly creates the group object.

### Using the API:

```bash
curl -X POST http://localhost:8080/stores/{store-id}/write \
  -H "Content-Type: application/json" \
  -d '{
    "writes": {
      "tuple_keys": [
        {
          "user": "user:admin@example.com",
          "relation": "admin",
          "object": "group:developers"
        }
      ]
    }
  }'
```

## Example Relationships

After running the sync, you'll have relationships like:

```
user:john@example.com member group:developers
user:jane@example.com member group:developers
user:bob@example.com member group:operations
```

These can be queried with:

```bash
# Check if a user is a member of a group
fga tuple check user:john@example.com member group:developers

# List all members of a group
fga tuple read --relation member --object group:developers

# List all groups a user is a member of
fga tuple read --user user:john@example.com --relation member
```

