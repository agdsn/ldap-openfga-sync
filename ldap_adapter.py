"""
LDAP adapter for diffsync
"""

import os
import logging
from typing import Set
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
        self.sync_groups: Set[str] = set()

    def connect_ldap(self):
        """Establish connection to LDAP server."""
        server = os.getenv("LDAP_SERVER")
        bind_dn = os.getenv("LDAP_BIND_DN")
        bind_password = os.getenv("LDAP_BIND_PASSWORD")
        use_tls = os.getenv("LDAP_USE_TLS", "false").lower() == "true"
        ca_cert_file = os.getenv("LDAP_CA_CERT_FILE")

        logger.info(f"Connecting to LDAP server: {server}")

        try:
            # Configure TLS certificate verification if CA cert is provided
            if ca_cert_file and os.path.exists(ca_cert_file):
                logger.info(f"Using custom CA certificate: {ca_cert_file}")
                ldap.set_option(ldap.OPT_X_TLS_CACERTFILE, ca_cert_file)
                ldap.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_DEMAND)
            elif ca_cert_file:
                logger.warning(f"CA certificate file not found: {ca_cert_file}")

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


    def load(self):
        """Load group memberships from LDAP."""
        logger.info("Loading data from LDAP")

        if not self.ldap_conn:
            self.connect_ldap()

        # Check which lookup method to use
        use_memberof = os.getenv("LDAP_USE_MEMBEROF", "false").lower() == "true"

        if use_memberof:
            self._load_using_memberof()
        else:
            self._load_using_member_attribute()

    def _add_membership(self, username: str, group_name: str) -> None:
        """Helper to create and add a membership object."""
        membership = GroupMembership(
            user_username=username,
            group_name=group_name
        )
        self.add(membership)
        logger.debug(f"Added membership: {username} -> {group_name}")

    def _load_using_memberof(self):
        """Load group memberships using memberOf attribute (reverse lookup from users)."""
        logger.info("Using memberOf attribute for group membership lookup")

        user_base_dn = os.getenv("LDAP_USER_BASE_DN", os.getenv("LDAP_GROUP_BASE_DN"))
        group_base_dn = os.getenv("LDAP_GROUP_BASE_DN")
        username_attr = os.getenv("LDAP_USERNAME_ATTRIBUTE", "uid")
        groups_to_sync = self._get_groups_to_sync()
        membership_count = 0

        try:
            for group_name in groups_to_sync:
                logger.info(f"Processing group: {group_name}")
                group_dn = f"cn={group_name},{group_base_dn}"
                search_filter = f"(memberOf={group_dn})"

                try:
                    results = self.ldap_conn.search_s(
                        user_base_dn,
                        ldap.SCOPE_SUBTREE,
                        search_filter,
                        [username_attr]
                    )

                    for dn, attrs in results:
                        if not dn:
                            continue

                        if username_attr in attrs and len(attrs[username_attr]) > 0:
                            username = attrs[username_attr][0]
                            if isinstance(username, bytes):
                                username = username.decode('utf-8')

                            self._add_membership(username, group_name)
                            membership_count += 1
                        else:
                            logger.warning(f"User {dn} in group {group_name} has no {username_attr} attribute")

                except ldap.NO_SUCH_OBJECT:
                    logger.warning(f"Group DN not found: {group_dn}")
                except ldap.LDAPError as e:
                    logger.warning(f"Error searching for members of {group_name}: {e}")

            logger.info(f"Loaded {membership_count} memberships from LDAP using memberOf")

        except ldap.LDAPError as e:
            logger.error(f"LDAP search failed: {e}")
            raise

    def _load_using_member_attribute(self):
        """Load group memberships using member attribute (forward lookup from groups)."""
        logger.info("Using member attribute for group membership lookup")

        base_dn = os.getenv("LDAP_GROUP_BASE_DN")
        member_attribute = os.getenv("LDAP_MEMBER_ATTRIBUTE", "member")
        username_attr = os.getenv("LDAP_USERNAME_ATTRIBUTE", "uid")
        group_filter = os.getenv("LDAP_GROUP_FILTER", "(objectClass=groupOfNames)")
        groups_to_sync = self._get_groups_to_sync()
        membership_count = 0
        skipped_groups = 0

        try:
            results = self.ldap_conn.search_s(
                base_dn,
                ldap.SCOPE_SUBTREE,
                group_filter,
                [member_attribute, 'cn']
            )

            for dn, attrs in results:
                if not dn:
                    continue

                if 'cn' not in attrs or len(attrs['cn']) == 0:
                    logger.warning(f"Group {dn} has no cn attribute, skipping")
                    continue

                group_name = attrs['cn'][0]
                if isinstance(group_name, bytes):
                    group_name = group_name.decode('utf-8')

                if group_name not in groups_to_sync:
                    logger.debug(f"Skipping group '{group_name}' - not in SYNC_GROUPS config")
                    skipped_groups += 1
                    continue

                logger.info(f"Processing group: {group_name}")

                if member_attribute in attrs:
                    members = attrs[member_attribute]
                    if not isinstance(members, list):
                        members = [members]

                    for member_dn in members:
                        if isinstance(member_dn, bytes):
                            member_dn = member_dn.decode('utf-8')

                        # Query the member DN for the username attribute
                        try:
                            user_result = self.ldap_conn.search_s(
                                member_dn,
                                ldap.SCOPE_BASE,
                                attrlist=[username_attr]
                            )
                            if user_result and len(user_result) > 0:
                                _, user_attrs = user_result[0]
                                if username_attr in user_attrs and len(user_attrs[username_attr]) > 0:
                                    username = user_attrs[username_attr][0]
                                    if isinstance(username, bytes):
                                        username = username.decode('utf-8')

                                    self._add_membership(username, group_name)
                                    membership_count += 1
                                else:
                                    logger.warning(f"User {member_dn} has no {username_attr} attribute")
                            else:
                                logger.warning(f"Could not find user {member_dn}")
                        except ldap.LDAPError as e:
                            logger.warning(f"Could not query {username_attr} for {member_dn}: {e}")

            logger.info(f"Loaded {membership_count} memberships from LDAP using member attribute")
            if skipped_groups > 0:
                logger.info(f"Skipped {skipped_groups} groups not in SYNC_GROUPS config")

        except ldap.LDAPError as e:
            logger.error(f"LDAP search failed: {e}")
            raise

    def _get_groups_to_sync(self) -> Set[str]:
        """Get the set of groups to sync (either from config or by discovering all groups)."""
        if self.sync_groups is not None:
            return self.sync_groups

        # If no specific groups configured, discover all groups
        logger.info("No SYNC_GROUPS configured - discovering all groups")
        group_base_dn = os.getenv("LDAP_GROUP_BASE_DN")
        group_filter = os.getenv("LDAP_GROUP_FILTER", "(objectClass=groupOfNames)")

        try:
            results = self.ldap_conn.search_s(
                group_base_dn,
                ldap.SCOPE_SUBTREE,
                group_filter,
                ['cn']
            )
            groups_to_sync = set()
            for dn, attrs in results:
                if dn and 'cn' in attrs:
                    group_name = attrs['cn'][0]
                    if isinstance(group_name, bytes):
                        group_name = group_name.decode('utf-8')
                    groups_to_sync.add(group_name)
            logger.info(f"Found {len(groups_to_sync)} groups to sync")
            return groups_to_sync
        except ldap.LDAPError as e:
            logger.error(f"Failed to discover groups: {e}")
            raise

