"""
LDAP adapter for diffsync
"""

import os
import logging
from typing import Optional, Set
import ldap
from diffsync import Adapter

from models import GroupMembership


logger = logging.getLogger(__name__)


class LDAPAdapter(Adapter):
    """
    DiffSync adapter for LDAP.
    Reads group memberships from LDAP.
    """

    membership = GroupMembership
    top_level = ["membership"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ldap_conn = None
        self.valid_groups: Set[str] = set()

    def connect_ldap(self):
        """Establish connection to LDAP server."""
        server = os.getenv("LDAP_SERVER")
        bind_dn = os.getenv("LDAP_BIND_DN")
        bind_password = os.getenv("LDAP_BIND_PASSWORD")
        use_tls = os.getenv("LDAP_USE_TLS", "false").lower() == "true"

        logger.info(f"Connecting to LDAP server: {server}")

        try:
            self.ldap_conn = ldap.initialize(server)
            self.ldap_conn.protocol_version = ldap.VERSION3

            if use_tls and server.startswith("ldap://"):
                self.ldap_conn.start_tls_s()

            self.ldap_conn.simple_bind_s(bind_dn, bind_password)
            logger.info("Successfully connected to LDAP")
        except ldap.LDAPError as e:
            logger.error(f"Failed to connect to LDAP: {e}")
            raise

    def disconnect_ldap(self):
        """Close LDAP connection."""
        if self.ldap_conn:
            self.ldap_conn.unbind_s()
            logger.info("Disconnected from LDAP")

    def set_valid_groups(self, groups: Set[str]):
        """Set the list of valid groups that exist in OpenFGA."""
        self.valid_groups = groups
        logger.info(f"Set {len(groups)} valid groups for sync")

    def extract_email_from_dn(self, dn: str) -> Optional[str]:
        """
        Extract email from a user DN.
        Tries to find 'mail=' attribute in the DN.
        If not found, tries to extract from uid or cn and construct email.
        """
        try:
            # Parse the DN
            dn_parts = ldap.dn.str2dn(dn)

            # Look for mail attribute
            for rdn in dn_parts:
                for attr, value, _ in rdn:
                    if attr.lower() == 'mail':
                        return value

            # If we need to query LDAP for the user's email
            if self.ldap_conn:
                try:
                    result = self.ldap_conn.search_s(
                        dn,
                        ldap.SCOPE_BASE,
                        attrlist=['mail']
                    )
                    if result and len(result) > 0:
                        _, attrs = result[0]
                        if 'mail' in attrs and len(attrs['mail']) > 0:
                            email = attrs['mail'][0]
                            if isinstance(email, bytes):
                                email = email.decode('utf-8')
                            return email
                except ldap.LDAPError as e:
                    logger.warning(f"Could not query LDAP for email of {dn}: {e}")

            return None
        except Exception as e:
            logger.warning(f"Failed to extract email from DN {dn}: {e}")
            return None

    def load(self):
        """Load group memberships from LDAP."""
        logger.info("Loading data from LDAP")

        if not self.ldap_conn:
            self.connect_ldap()

        base_dn = os.getenv("LDAP_GROUP_BASE_DN")
        group_filter = os.getenv("LDAP_GROUP_FILTER", "(objectClass=groupOfNames)")
        member_attribute = os.getenv("LDAP_MEMBER_ATTRIBUTE", "member")

        try:
            # Search for all groups
            results = self.ldap_conn.search_s(
                base_dn,
                ldap.SCOPE_SUBTREE,
                group_filter,
                [member_attribute, 'cn']
            )

            membership_count = 0
            skipped_groups = 0

            for dn, attrs in results:
                if not dn:  # Skip search references
                    continue

                # Get group name (cn)
                group_name = None
                if 'cn' in attrs and len(attrs['cn']) > 0:
                    group_name = attrs['cn'][0]
                    if isinstance(group_name, bytes):
                        group_name = group_name.decode('utf-8')

                if not group_name:
                    logger.warning(f"Group {dn} has no cn attribute, skipping")
                    continue

                # Only process groups that exist in OpenFGA
                if group_name not in self.valid_groups:
                    logger.debug(f"Skipping group '{group_name}' - not in OpenFGA")
                    skipped_groups += 1
                    continue

                logger.info(f"Processing group: {group_name}")

                # Get members
                if member_attribute in attrs:
                    members = attrs[member_attribute]
                    if not isinstance(members, list):
                        members = [members]

                    for member in members:
                        if isinstance(member, bytes):
                            member = member.decode('utf-8')

                        # Extract email from member DN
                        email = self.extract_email_from_dn(member)

                        if email:
                            # Create membership object
                            membership = GroupMembership(
                                user_email=email,
                                group_name=group_name
                            )
                            self.add(membership)
                            membership_count += 1
                            logger.debug(f"Added membership: {email} -> {group_name}")
                        else:
                            logger.warning(f"Could not extract email from member DN: {member}")

            logger.info(f"Loaded {membership_count} memberships from LDAP")
            logger.info(f"Skipped {skipped_groups} groups not in OpenFGA")

        except ldap.LDAPError as e:
            logger.error(f"LDAP search failed: {e}")
            raise

