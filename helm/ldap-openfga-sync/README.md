# Helm Chart for LDAP to OpenFGA Sync

This Helm chart deploys the LDAP to OpenFGA group membership synchronization service on Kubernetes.

## TL;DR

```bash
# Add the Helm repository
helm repo add ldap-openfga-sync https://agdsn.github.io/ldap-openfga-sync

# Update repositories
helm repo update

# Install the chart
helm install my-ldap-sync ldap-openfga-sync/ldap-openfga-sync \
  --set ldap.server="ldap://ldap.example.com:389" \
  --set ldap.bindDn="cn=admin,dc=example,dc=com" \
  --set ldap.bindPassword="your-password" \
  --set ldap.groupBaseDn="ou=groups,dc=example,dc=com" \
  --set openfga.apiUrl="http://openfga:8080" \
  --set openfga.storeId="your-store-id"
```

## Prerequisites

- Kubernetes 1.19+
- Helm 3.2.0+
- Access to LDAP server
- Running OpenFGA instance
- Groups already created in OpenFGA

## Installing the Chart

### From Helm Repository

```bash
helm repo add ldap-openfga-sync https://agdsn.github.io/ldap-openfga-sync
helm repo update
helm install my-ldap-sync ldap-openfga-sync/ldap-openfga-sync -f values.yaml
```

### From Source

```bash
git clone https://github.com/agdsn/ldap-openfga-sync.git
cd ldap-openfga-sync
helm install my-ldap-sync ./helm/ldap-openfga-sync -f values.yaml
```

## Uninstalling the Chart

```bash
helm uninstall my-ldap-sync
```

## Configuration

The following table lists the configurable parameters of the chart and their default values.

### Image Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `image.repository` | Image repository | `ghcr.io/agdsn/ldap-openfga-sync` |
| `image.pullPolicy` | Image pull policy | `IfNotPresent` |
| `image.tag` | Image tag | `""` (uses appVersion) |
| `imagePullSecrets` | Image pull secrets | `[]` |

### Deployment Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `replicaCount` | Number of replicas | `1` |
| `nameOverride` | Override chart name | `""` |
| `fullnameOverride` | Override full chart name | `""` |

### Service Account

| Parameter | Description | Default |
|-----------|-------------|---------|
| `serviceAccount.create` | Create service account | `true` |
| `serviceAccount.automount` | Automount service account token | `true` |
| `serviceAccount.annotations` | Service account annotations | `{}` |
| `serviceAccount.name` | Service account name | `""` |

### Security Context

| Parameter | Description | Default |
|-----------|-------------|---------|
| `podSecurityContext.runAsNonRoot` | Run as non-root user | `true` |
| `podSecurityContext.runAsUser` | User ID | `1000` |
| `podSecurityContext.fsGroup` | File system group | `1000` |
| `securityContext.allowPrivilegeEscalation` | Allow privilege escalation | `false` |
| `securityContext.readOnlyRootFilesystem` | Read-only root filesystem | `false` |

### Resources

| Parameter | Description | Default |
|-----------|-------------|---------|
| `resources.limits.cpu` | CPU limit | `500m` |
| `resources.limits.memory` | Memory limit | `256Mi` |
| `resources.requests.cpu` | CPU request | `100m` |
| `resources.requests.memory` | Memory request | `128Mi` |

### Secret Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `existingSecret` | Existing secret with sensitive values | `""` |

When using `existingSecret`, the secret must contain these keys:
- `LDAP_BIND_PASSWORD` - LDAP bind password
- `OPENFGA_STORE_ID` - OpenFGA store ID
- `OPENFGA_API_TOKEN` - OpenFGA API token (optional)

### LDAP Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `ldap.server` | LDAP server URL | `ldap://ldap.example.com:389` |
| `ldap.bindDn` | Bind DN | `cn=admin,dc=example,dc=com` |
| `ldap.bindPassword` | Bind password (used if existingSecret not set) | `""` |
| `ldap.groupBaseDn` | Group base DN | `ou=groups,dc=example,dc=com` |
| `ldap.groupFilter` | Group filter | `(objectClass=groupOfNames)` |
| `ldap.memberAttribute` | Member attribute | `member` |
| `ldap.useTls` | Use TLS | `false` |
| `ldap.caCert` | Custom CA certificate (inline PEM) | `""` |
| `ldap.existingCaCertSecret` | Existing secret with CA certificate | `""` |

### OpenFGA Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `openfga.apiUrl` | OpenFGA API URL | `http://openfga:8080` |
| `openfga.storeId` | Store ID (used if existingSecret not set) | `""` |
| `openfga.apiToken` | API token (used if existingSecret not set) | `""` |
| `openfga.authorizationModelId` | Authorization model ID | `""` |

### Sync Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `sync.dryRun` | Enable dry-run mode | `false` |
| `sync.intervalSeconds` | Sync interval in seconds | `21600` (6 hours) |
| `sync.groups` | List of groups to sync (empty = sync all) | `[]` |

### Persistence

| Parameter | Description | Default |
|-----------|-------------|---------|
| `persistence.enabled` | Enable persistence for logs | `true` |
| `persistence.storageClass` | Storage class | `""` |
| `persistence.accessMode` | Access mode | `ReadWriteOnce` |
| `persistence.size` | Volume size | `1Gi` |
| `persistence.existingClaim` | Existing PVC | `""` |

### Probes

| Parameter | Description | Default |
|-----------|-------------|---------|
| `livenessProbe.enabled` | Enable liveness probe | `true` |
| `livenessProbe.initialDelaySeconds` | Initial delay | `30` |
| `livenessProbe.periodSeconds` | Period | `3600` |
| `readinessProbe.enabled` | Enable readiness probe | `true` |
| `readinessProbe.initialDelaySeconds` | Initial delay | `10` |
| `readinessProbe.periodSeconds` | Period | `60` |

## Examples

### Basic Installation

```bash
helm install my-ldap-sync ldap-openfga-sync/ldap-openfga-sync \
  --set ldap.server="ldap://ldap.example.com:389" \
  --set ldap.bindDn="cn=admin,dc=example,dc=com" \
  --set ldap.bindPassword="secret" \
  --set ldap.groupBaseDn="ou=groups,dc=example,dc=com" \
  --set openfga.apiUrl="http://openfga:8080" \
  --set openfga.storeId="01234567890ABCDEF" \
  --set sync.groups="{developers,operations,managers}"
```

**Note**: If `sync.groups` is not specified or is empty, all groups from LDAP will be synced.

### Configuration Management

The chart uses two resources for configuration:
- **ConfigMap**: Non-sensitive configuration (LDAP server, URLs, etc.)
- **Secret**: Sensitive values (passwords, tokens, store ID)

Both are loaded using `envFrom` for clean environment variable injection.

### Using Existing Secrets

Create a secret with sensitive values:
```bash
kubectl create secret generic my-ldap-sync-secret \
  --from-literal=LDAP_BIND_PASSWORD='your-password' \
  --from-literal=OPENFGA_STORE_ID='your-store-id' \
  --from-literal=OPENFGA_API_TOKEN='your-token'
```

Install with existing secret:
```bash
helm install my-ldap-sync ldap-openfga-sync/ldap-openfga-sync \
  --set existingSecret="my-ldap-sync-secret" \
  --set ldap.server="ldap://ldap.example.com:389" \
  --set ldap.bindDn="cn=admin,dc=example,dc=com" \
  --set ldap.groupBaseDn="ou=groups,dc=example,dc=com" \
  --set openfga.apiUrl="http://openfga:8080"
```

The ConfigMap will be automatically created with the non-sensitive values from your `values.yaml`.

### Using Custom CA Certificate

For LDAP servers with self-signed certificates or internal CAs:

**Option 1: Inline Certificate**
```yaml
ldap:
  server: "ldaps://ldap.example.com:636"
  useTls: true
  caCert: |
    -----BEGIN CERTIFICATE-----
    MIIDXTCCAkWgAwIBAgIJAKZM...
    -----END CERTIFICATE-----
```

**Option 2: Existing Secret**
```bash
# Create secret with CA certificate
kubectl create secret generic ldap-ca-cert \
  --from-file=ca.crt=/path/to/ca-cert.pem
```

```yaml
ldap:
  server: "ldaps://ldap.example.com:636"
  useTls: true
  existingCaCertSecret: "ldap-ca-cert"
```

**Option 3: Command Line**
```bash
helm install my-ldap-sync ldap-openfga-sync/ldap-openfga-sync \
  --set-file ldap.caCert=/path/to/ca-cert.pem \
  --set ldap.server="ldaps://ldap.example.com:636" \
  --set ldap.useTls=true
```

### Custom Values File

Create a `values.yaml`:
```yaml
image:
  repository: ghcr.io/agdsn/ldap-openfga-sync
  tag: "1.0.0"

ldap:
  server: "ldap://ldap.example.com:389"
  bindDn: "cn=admin,dc=example,dc=com"
  bindPassword: "your-password"
  groupBaseDn: "ou=groups,dc=example,dc=com"
  useTls: true

openfga:
  apiUrl: "http://openfga:8080"
  storeId: "your-store-id"
  apiToken: "your-token"

sync:
  schedule: "0 */4 * * *"  # Every 4 hours

resources:
  limits:
    cpu: 1000m
    memory: 512Mi
  requests:
    cpu: 200m
    memory: 256Mi

persistence:
  enabled: true
  size: 5Gi
  storageClass: "fast-ssd"
```

Install:
```bash
helm install my-ldap-sync ldap-openfga-sync/ldap-openfga-sync -f values.yaml
```

### Dry-Run Mode

```bash
helm install my-ldap-sync ldap-openfga-sync/ldap-openfga-sync \
  --set sync.dryRun=true \
  -f values.yaml
```

### Custom Sync Interval

The sync interval is configurable via `sync.intervalSeconds` in seconds.

Run every 2 hours:
```bash
helm install my-ldap-sync ldap-openfga-sync/ldap-openfga-sync \
  --set sync.intervalSeconds=7200 \
  -f values.yaml
```

Common intervals:
- `21600` - Every 6 hours (default)
- `14400` - Every 4 hours
- `7200` - Every 2 hours
- `3600` - Every hour
- `1800` - Every 30 minutes
- `86400` - Daily

## Upgrading

```bash
# Update repository
helm repo update

# Upgrade release
helm upgrade my-ldap-sync ldap-openfga-sync/ldap-openfga-sync -f values.yaml

# Upgrade with new values
helm upgrade my-ldap-sync ldap-openfga-sync/ldap-openfga-sync \
  --set sync.schedule="0 */4 * * *"
```

## Monitoring

### View Logs

```bash
# Get pod name
POD=$(kubectl get pods -l app.kubernetes.io/name=ldap-openfga-sync -o jsonpath='{.items[0].metadata.name}')

# View container logs
kubectl logs $POD

# Follow logs
kubectl logs -f $POD

# View sync logs
kubectl exec $POD -- tail -f /var/log/ldap-openfga-sync/sync.log
```

### Manual Sync

```bash
POD=$(kubectl get pods -l app.kubernetes.io/name=ldap-openfga-sync -o jsonpath='{.items[0].metadata.name}')

# Run sync manually
kubectl exec $POD -- python sync.py

# Run in dry-run mode
kubectl exec $POD -e SYNC_DRY_RUN=true -- python sync.py
```

### Check Status

```bash
# Check deployment
kubectl get deployment -l app.kubernetes.io/name=ldap-openfga-sync

# Check pods
kubectl get pods -l app.kubernetes.io/name=ldap-openfga-sync

# Describe pod
kubectl describe pod $POD
```

## Development

### Lint the Chart

```bash
helm lint ./helm/ldap-openfga-sync
```

### Template the Chart

```bash
helm template my-ldap-sync ./helm/ldap-openfga-sync -f values.yaml
```

### Dry-Run Install

```bash
helm install my-ldap-sync ./helm/ldap-openfga-sync -f values.yaml --dry-run --debug
```

### Package the Chart

```bash
helm package ./helm/ldap-openfga-sync
```

## Contributing

Contributions are welcome! Please see the main [README](../README.md) for contribution guidelines.

## License

This project is licensed under the MIT License - see the [LICENSE](../LICENSE) file for details.

