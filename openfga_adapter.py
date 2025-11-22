"""
OpenFGA adapter for diffsync
"""

import os
import logging
from typing import Optional, Set
from diffsync import Adapter
from openfga_sdk import ReadRequestTupleKey
from openfga_sdk.client import ClientConfiguration, OpenFgaClient
from openfga_sdk.client.models import (
    ClientTuple,
    ClientWriteRequest
)

from models import GroupMembership


logger = logging.getLogger(__name__)


class OpenFGAAdapter(Adapter):
    """
    DiffSync adapter for OpenFGA.
    Reads and writes group memberships to/from OpenFGA.
    """

    membership = GroupMembership
    top_level = ["membership"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client: Optional[OpenFgaClient] = None
        self.store_id: str = ""
        self.dry_run: bool = False
        self.pending_operations: list = []
        self.sync_groups: Optional[Set[str]] = None

    async def connect_openfga(self):
        """Establish connection to OpenFGA."""
        api_url = os.getenv("OPENFGA_API_URL")
        self.store_id = os.getenv("OPENFGA_STORE_ID")
        api_token = os.getenv("OPENFGA_API_TOKEN", "")

        logger.info(f"Connecting to OpenFGA: {api_url}")

        configuration = ClientConfiguration(
            api_url=api_url,
            store_id=self.store_id,
        )

        if api_token:
            configuration.credentials = {
                "method": "api_token",
                "config": {
                    "token": api_token
                }
            }

        self.client = OpenFgaClient(configuration)
        logger.info("Successfully connected to OpenFGA")



    async def load(self):
        """Load existing group memberships from OpenFGA."""
        logger.info("Loading data from OpenFGA")

        if not self.client:
            await self.connect_openfga()

        try:
            # Read all tuples and filter for 'member' relationships
            body = ReadRequestTupleKey()
            response = await self.client.read(body=body)

            membership_count = 0

            if hasattr(response, 'tuples') and response.tuples:
                for tuple_data in response.tuples:
                    if hasattr(tuple_data, 'key'):
                        key = tuple_data.key

                        # Only process 'member' relationships
                        if key.relation != 'member':
                            continue

                        # Extract user email and group name
                        user_str = key.user  # Format: "user:email@example.com"
                        group_str = key.object  # Format: "group:groupname"

                        if user_str.startswith('user:') and group_str.startswith('group:'):
                            user_email = user_str.split(':', 1)[1]
                            group_name = group_str.split(':', 1)[1]

                            # Only load memberships for groups in the sync list
                            if self.sync_groups is not None and group_name not in self.sync_groups:
                                logger.debug(f"Skipping membership {user_email} -> {group_name} - group not in sync list")
                                continue

                            membership = GroupMembership(
                                user_email=user_email,
                                group_name=group_name
                            )
                            self.add(membership)
                            membership_count += 1
                            logger.debug(f"Loaded membership: {user_email} -> {group_name}")

            logger.info(f"Loaded {membership_count} memberships from OpenFGA")

        except Exception as e:
            logger.error(f"Failed to load data from OpenFGA: {e}")
            raise

    async def add_membership(self, user_email: str, group_name: str):
        """Add a membership tuple to OpenFGA."""
        if self.dry_run:
            logger.info(f"[DRY RUN] Would add: user:{user_email} member group:{group_name}")
            return

        try:
            body = ClientWriteRequest(
                writes=[ClientTuple(
                    user=f"user:{user_email}",
                    relation="member",
                    object=f"group:{group_name}"
                )]
            )

            await self.client.write(body=body)
            logger.info(f"Added membership: user:{user_email} member group:{group_name}")

        except Exception as e:
            logger.error(f"Failed to add membership {user_email} -> {group_name}: {e}")
            raise

    async def remove_membership(self, user_email: str, group_name: str):
        """Remove a membership tuple from OpenFGA."""
        if self.dry_run:
            logger.info(f"[DRY RUN] Would remove: user:{user_email} member group:{group_name}")
            return

        try:
            body = ClientWriteRequest(
                deletes=[ClientTuple(
                    user=f"user:{user_email}",
                    relation="member",
                    object=f"group:{group_name}"
                )]
            )

            await self.client.write(body=body)
            logger.info(f"Removed membership: user:{user_email} member group:{group_name}")

        except Exception as e:
            logger.error(f"Failed to remove membership {user_email} -> {group_name}: {e}")
            raise

    async def execute_pending_operations(self):
        """Execute all pending operations that were queued during sync."""
        if not self.pending_operations:
            logger.info("No pending operations to execute")
            return

        logger.info(f"Executing {len(self.pending_operations)} pending operations")

        for operation, user_email, group_name in self.pending_operations:
            if operation == 'create':
                await self.add_membership(user_email, group_name)
            elif operation == 'delete':
                await self.remove_membership(user_email, group_name)

        # Clear the pending operations
        self.pending_operations = []

    async def close(self):
        """Close the OpenFGA client connection and cleanup resources."""
        if self.client:
            try:
                await self.client.close()
                logger.debug("OpenFGA client closed")
            except Exception as e:
                logger.warning(f"Error closing OpenFGA client: {e}")

