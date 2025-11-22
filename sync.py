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



async def sync_ldap_to_openfga():
    """
    Main sync function.
    Syncs group memberships from LDAP to OpenFGA.
    """
    logger.info("Starting LDAP to OpenFGA sync")

    dry_run = os.getenv("SYNC_DRY_RUN", "false").lower() == "true"
    if dry_run:
        logger.info("Running in DRY RUN mode - no changes will be made")

    # Initialize adapters
    ldap_adapter = LDAPAdapter()
    openfga_adapter = OpenFGAAdapter()
    openfga_adapter.dry_run = dry_run

    try:
        # Connect to OpenFGA and get existing groups
        await openfga_adapter.connect_openfga()
        existing_groups = await openfga_adapter.get_existing_groups()

        # Connect to LDAP and set valid groups
        ldap_adapter.connect_ldap()
        ldap_adapter.set_valid_groups(existing_groups)

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

