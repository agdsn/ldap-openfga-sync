#!/usr/bin/env python3
"""
LDAP to OpenFGA Group Membership Sync

This script syncs group memberships from LDAP to OpenFGA using the diffsync library.
It only syncs memberships for groups that already exist in OpenFGA.
"""

import os
import sys
import logging
from dotenv import load_dotenv

from ldap_adapter import LDAPAdapter
from openfga_adapter import OpenFGAAdapter


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Load environment variables
load_dotenv()


def load_sync_groups_from_config():
    """Load the list of groups to sync from configuration."""
    groups_config = os.getenv("SYNC_GROUPS", "")

    if groups_config:
        # Parse comma-separated list and strip whitespace
        sync_groups = {g.strip() for g in groups_config.split(',') if g.strip()}
        logger.info(f"Loaded {len(sync_groups)} groups from config: {', '.join(sorted(sync_groups))}")
        return sync_groups
    else:
        # If no groups specified, sync all groups from LDAP
        logger.info("No SYNC_GROUPS configured - will sync all groups from LDAP")
        return None  # None means sync all groups


async def sync_ldap_to_openfga():
    """
    Main sync function.
    Syncs group memberships from LDAP to OpenFGA.
    """
    logger.info("Starting LDAP to OpenFGA sync")

    dry_run = os.getenv("SYNC_DRY_RUN", "false").lower() == "true"
    if dry_run:
        logger.info("Running in DRY RUN mode - no changes will be made")

    # Load sync groups from configuration
    sync_groups = load_sync_groups_from_config()

    # Initialize adapters
    ldap_adapter = LDAPAdapter()
    openfga_adapter = OpenFGAAdapter()
    openfga_adapter.dry_run = dry_run

    # Set sync groups for both adapters
    ldap_adapter.sync_groups = sync_groups
    openfga_adapter.sync_groups = sync_groups

    try:
        # Connect to OpenFGA
        await openfga_adapter.connect_openfga()

        # Connect to LDAP
        ldap_adapter.connect_ldap()

        # Load data from both sources
        ldap_adapter.load()
        await openfga_adapter.load()

        # Sync OpenFGA to match LDAP using diffsync's built-in sync mechanism
        logger.info("Syncing OpenFGA to match LDAP")
        logger.debug(f"LDAP adapter has {len(ldap_adapter.get_all('membership'))} memberships")
        logger.debug(f"OpenFGA adapter has {len(openfga_adapter.get_all('membership'))} memberships")

        # Use sync_from to automatically apply changes via the model's create/delete methods
        openfga_adapter.sync_from(ldap_adapter)

        # Execute the pending operations that were queued during sync
        await openfga_adapter.execute_pending_operations()

        logger.info("Sync completed successfully")

    except Exception as e:
        logger.error(f"Sync failed: {e}", exc_info=True)
        sys.exit(1)

    finally:
        # Cleanup
        ldap_adapter.disconnect_ldap()
        await openfga_adapter.close()


if __name__ == "__main__":
    import asyncio
    asyncio.run(sync_ldap_to_openfga())

