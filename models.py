"""
DiffSync models for LDAP to OpenFGA sync
"""

from diffsync import DiffSyncModel
from typing import Optional


class GroupMembership(DiffSyncModel):
    """
    DiffSync model representing a group membership.
    A membership is a relationship between a user (identified by username) and a group.
    """
    _modelname = "membership"
    _identifiers = ("user_username", "group_name")
    _attributes = ()

    user_username: str
    group_name: str

    @classmethod
    def create(cls, adapter, ids, attrs):
        """Create this membership in the target adapter (OpenFGA)."""
        # Create the model instance
        membership = cls(**ids, **attrs)
        membership.adapter = adapter

        # Queue the operation for the OpenFGA adapter to execute
        if hasattr(adapter, 'pending_operations'):
            adapter.pending_operations.append(('create', membership.user_username, membership.group_name))

        # Note: We don't add to the adapter's store here - diffsync handles that
        return membership

    def delete(self) -> Optional["GroupMembership"]:
        """Delete this membership from the target adapter (OpenFGA)."""
        # Queue the operation for the OpenFGA adapter to execute
        if hasattr(self.adapter, 'pending_operations'):
            self.adapter.pending_operations.append(('delete', self.user_username, self.group_name))

        # Note: We don't remove from the adapter's store here - diffsync handles that
        return self

