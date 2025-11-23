#!/usr/bin/env python3
"""
Comprehensive test suite for LDAP to OpenFGA sync

This script tests various scenarios:
1. Initial sync (empty OpenFGA, populated LDAP)
2. No changes (already in sync)
3. Additions (new members in LDAP)
4. Deletions (removed members from LDAP)
5. Mixed changes (additions + deletions)
6. Group filtering (only sync groups in OpenFGA)
"""

import asyncio
import json
import logging
import os
import re
import sys
import time
from typing import Dict, List, Set

import ldap
import requests
from dotenv import load_dotenv
from openfga_sdk.client import ClientConfiguration, OpenFgaClient
from openfga_sdk import ReadRequestTupleKey
from openfga_sdk.client.models import (
    ClientTuple,
    ClientWriteRequest
)

# Load test environment BEFORE importing sync module
# This ensures the sync module gets the right environment variables
load_dotenv('.env.test', override=True)

# Import the sync function
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sync import sync_ldap_to_openfga

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TestEnvironment:
    """Manages the test environment (LDAP and OpenFGA)"""

    def __init__(self):
        self.ldap_conn = None
        self.openfga_client = None
        self.store_id = None
        self.model_id = None

    def wait_for_services(self):
        """Wait for LDAP and OpenFGA to be ready"""
        logger.info("Waiting for services to be ready...")

        # Wait for LDAP
        max_retries = 10
        logger.info("Waiting for LDAP...")
        for i in range(max_retries):
            try:
                conn = ldap.initialize(os.getenv("LDAP_SERVER"))
                conn.protocol_version = ldap.VERSION3
                conn.simple_bind_s(os.getenv("LDAP_BIND_DN"), os.getenv("LDAP_BIND_PASSWORD"))
                conn.unbind_s()
                logger.info("✅ LDAP is ready")
                break
            except Exception as e:
                if i == max_retries - 1:
                    raise Exception(f"LDAP failed to start after {max_retries} attempts: {e}")
                time.sleep(2)

        # Wait for OpenFGA
        logger.info("Waiting for OpenFGA...")
        for i in range(max_retries):
            try:
                response = requests.get(f"{os.getenv('OPENFGA_API_URL')}/healthz", timeout=2)
                if response.status_code == 200:
                    logger.info("✅ OpenFGA is ready")
                    break
            except Exception as e:
                if i == max_retries - 1:
                    raise Exception(f"OpenFGA failed to start after {max_retries} attempts: {e}")
                time.sleep(2)

    async def setup_openfga(self):
        """Initialize OpenFGA with store and authorization model"""
        logger.info("Setting up OpenFGA...")

        api_url = os.getenv("OPENFGA_API_URL")

        # Create store
        response = requests.post(
            f"{api_url}/stores",
            json={"name": "test-store"},
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        self.store_id = response.json()["id"]
        logger.info(f"Created store: {self.store_id}")

        os.environ['OPENFGA_STORE_ID'] = self.store_id

        # Create authorization model
        with open('test/data/authorization-model.json', 'r') as f:
            model = json.load(f)

        response = requests.post(
            f"{api_url}/stores/{self.store_id}/authorization-models",
            json=model,
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        self.model_id = response.json()["authorization_model_id"]
        logger.info(f"Created authorization model: {self.model_id}")

        # Initialize client
        config = ClientConfiguration(
            api_url=api_url,
            store_id=self.store_id
        )
        self.openfga_client = OpenFgaClient(config)

    async def clear_openfga_tuples(self):
        """Remove all tuples from OpenFGA"""
        logger.info("Clearing OpenFGA tuples...")

        # Read all tuples
        body = ReadRequestTupleKey()
        response = await self.openfga_client.read(body=body)

        if hasattr(response, 'tuples') and response.tuples:
            # Delete all tuples
            deletes = []
            for tuple_data in response.tuples:
                if hasattr(tuple_data, 'key'):
                    key = tuple_data.key
                    deletes.append(ClientTuple(
                        user=key.user,
                        relation=key.relation,
                        object=key.object
                    ))

            if deletes:
                body = ClientWriteRequest(deletes=deletes)
                await self.openfga_client.write(body=body)
                logger.info(f"Deleted {len(deletes)} tuples")

    async def add_openfga_groups(self, groups: List[str], admin_email: str = "admin@example.com"):
        """Create groups in OpenFGA by adding admin relationships"""
        logger.info(f"Adding {len(groups)} groups to OpenFGA...")

        writes = []
        for group in groups:
            writes.append(ClientTuple(
                user=f"user:{admin_email}",
                relation="admin",
                object=f"group:{group}"
            ))

        if writes:
            body = ClientWriteRequest(writes=writes)
            await self.openfga_client.write(body=body)
            logger.info(f"✅ Added {len(groups)} groups")

    async def add_openfga_memberships(self, memberships: List[Dict[str, str]]):
        """Add specific memberships to OpenFGA"""
        logger.info(f"Adding {len(memberships)} memberships to OpenFGA...")

        writes = []
        for m in memberships:
            writes.append(ClientTuple(
                user=f"user:{m['email']}",
                relation="member",
                object=f"group:{m['group']}"
            ))

        if writes:
            body = ClientWriteRequest(writes=writes)
            await self.openfga_client.write(body=body)
            logger.info(f"✅ Added {len(memberships)} memberships")

    async def get_openfga_memberships(self) -> Set[tuple]:
        """Get all member relationships from OpenFGA"""
        body = ReadRequestTupleKey()
        response = await self.openfga_client.read(body=body)

        memberships = set()
        if hasattr(response, 'tuples') and response.tuples:
            for tuple_data in response.tuples:
                if hasattr(tuple_data, 'key'):
                    key = tuple_data.key
                    # Only get member relationships
                    if key.relation == 'member' and key.user.startswith('user:') and key.object.startswith('group:'):
                        email = key.user.split(':', 1)[1]
                        group = key.object.split(':', 1)[1]
                        memberships.add((email, group))

        return memberships

    def get_ldap_memberships(self, groups: List[str] = None) -> Set[tuple]:
        """Get memberships from LDAP for specific groups"""
        if not self.ldap_conn:
            self.ldap_conn = ldap.initialize(os.getenv("LDAP_SERVER"))
            self.ldap_conn.simple_bind_s(os.getenv("LDAP_BIND_DN"), os.getenv("LDAP_BIND_PASSWORD"))

        memberships = set()
        base_dn = os.getenv("LDAP_GROUP_BASE_DN")
        group_filter = os.getenv("LDAP_GROUP_FILTER")

        results = self.ldap_conn.search_s(base_dn, ldap.SCOPE_SUBTREE, group_filter, ['cn', 'member'])

        for dn, attrs in results:
            if not dn:
                continue

            group_name = attrs['cn'][0].decode('utf-8')

            # Filter by groups if specified
            if groups and group_name not in groups:
                continue

            if 'member' in attrs:
                members = attrs['member']
                if not isinstance(members, list):
                    members = [members]

                for member_dn in members:
                    member_dn = member_dn.decode('utf-8')
                    # Get user's email
                    try:
                        user_result = self.ldap_conn.search_s(
                            member_dn,
                            ldap.SCOPE_BASE,
                            attrlist=['mail']
                        )
                        if user_result and 'mail' in user_result[0][1]:
                            email = user_result[0][1]['mail'][0].decode('utf-8')
                            memberships.add((email, group_name))
                    except:
                        pass

        return memberships

    async def cleanup(self):
        """Cleanup connections"""
        if self.ldap_conn:
            self.ldap_conn.unbind_s()
        if self.openfga_client:
            try:
                await self.openfga_client.close()
            except Exception as e:
                logger.warning(f"Error closing OpenFGA client: {e}")


class TestRunner:
    """Runs test scenarios"""

    def __init__(self, env: TestEnvironment):
        self.env = env
        self.passed = 0
        self.failed = 0

    def set_sync_groups(self, groups: List[str]):
        """Set the SYNC_GROUPS environment variable for the test"""
        os.environ['SYNC_GROUPS'] = ','.join(groups)

    async def run_test(self, name: str, test_func):
        """Run a single test scenario"""
        logger.info(f"\n{'='*60}")
        logger.info(f"TEST: {name}")
        logger.info(f"{'='*60}")

        try:
            await test_func()
            self.passed += 1
            logger.info(f"✅ PASSED: {name}\n")
        except AssertionError as e:
            self.failed += 1
            logger.error(f"❌ FAILED: {name}")
            logger.error(f"   Error: {e}\n")
        except Exception as e:
            self.failed += 1
            logger.error(f"❌ ERROR: {name}")
            logger.error(f"   Exception: {e}\n", exc_info=True)

    async def test_initial_sync(self):
        """Test 1: Initial sync from LDAP to empty OpenFGA"""
        await self.env.clear_openfga_tuples()

        # Set groups to sync
        self.set_sync_groups(['developers', 'operations', 'managers', 'qa-team'])

        # Get expected memberships from LDAP
        expected = self.env.get_ldap_memberships(['developers', 'operations', 'managers', 'qa-team'])
        logger.info(f"Expected memberships from LDAP: {len(expected)}")

        before = await self.env.get_openfga_memberships()
        logger.info(f"Before sync: {before}")

        # Run sync
        await sync_ldap_to_openfga()

        # Check OpenFGA has correct memberships
        actual = await self.env.get_openfga_memberships()
        logger.info(f"After sync: {actual}")

        assert actual == expected, f"Mismatch: Expected {expected}, got {actual}"

    async def test_no_changes(self):
        """Test 2: No changes when already in sync"""
        await self.env.clear_openfga_tuples()

        # Set groups to sync
        self.set_sync_groups(['developers', 'operations'])

        # Create memberships
        await self.env.add_openfga_memberships([
            {'email': 'alice@example.com', 'group': 'developers'},
            {'email': 'bob@example.com', 'group': 'developers'},
            {'email': 'charlie@example.com', 'group': 'operations'},
            {'email': 'dave@example.com', 'group': 'operations'},
        ])

        before = await self.env.get_openfga_memberships()
        logger.info(f"Before sync: {before}")

        # Run sync
        await sync_ldap_to_openfga()

        after = await self.env.get_openfga_memberships()
        logger.info(f"After sync: {after}")

        assert before == after, "Memberships changed when they shouldn't have"

    async def test_additions(self):
        """Test 3: Add new members from LDAP"""
        await self.env.clear_openfga_tuples()

        # Set groups to sync
        self.set_sync_groups(['developers', 'operations'])

        # Create partial memberships
        await self.env.add_openfga_memberships([
            {'email': 'alice@example.com', 'group': 'developers'},
            # Missing bob in developers
            # Missing charlie and dave in operations
        ])

        before = await self.env.get_openfga_memberships()
        logger.info(f"Before sync: {before}")

        # Run sync
        await sync_ldap_to_openfga()

        after = await self.env.get_openfga_memberships()
        logger.info(f"After sync: {after}")

        # Should have added bob, charlie, and dave
        expected = {
            ('alice@example.com', 'developers'),
            ('bob@example.com', 'developers'),
            ('charlie@example.com', 'operations'),
            ('dave@example.com', 'operations'),
        }

        assert after == expected, f"Expected {expected}, got {after}"

    async def test_deletions(self):
        """Test 4: Remove members not in LDAP"""
        await self.env.clear_openfga_tuples()

        # Set groups to sync
        self.set_sync_groups(['developers'])

        # Create extra memberships not in LDAP
        await self.env.add_openfga_memberships([
            {'email': 'alice@example.com', 'group': 'developers'},
            {'email': 'bob@example.com', 'group': 'developers'},
            {'email': 'charlie@example.com', 'group': 'developers'},  # Not in LDAP
            {'email': 'eve@example.com', 'group': 'developers'},      # Not in LDAP
        ])

        before = await self.env.get_openfga_memberships()
        logger.info(f"Before sync: {before}")

        # Run sync
        await sync_ldap_to_openfga()

        after = await self.env.get_openfga_memberships()
        logger.info(f"After sync: {after}")

        # Should have removed charlie and eve from developers
        expected = {
            ('alice@example.com', 'developers'),
            ('bob@example.com', 'developers'),
        }

        assert after == expected, f"Expected {expected}, got {after}"

    async def test_mixed_changes(self):
        """Test 5: Mixed additions and deletions"""
        await self.env.clear_openfga_tuples()

        # Set groups to sync
        self.set_sync_groups(['developers', 'operations', 'managers'])

        # Create some correct, some extra, some missing
        await self.env.add_openfga_memberships([
            {'email': 'alice@example.com', 'group': 'developers'},     # Correct
            {'email': 'charlie@example.com', 'group': 'developers'},   # Should be removed
            # Missing bob in developers
            {'email': 'charlie@example.com', 'group': 'operations'},   # Correct
            {'email': 'dave@example.com', 'group': 'operations'},      # Correct
            # Missing alice in managers
        ])

        before = await self.env.get_openfga_memberships()
        logger.info(f"Before sync: {before}")

        # Run sync
        await sync_ldap_to_openfga()

        after = await self.env.get_openfga_memberships()
        logger.info(f"After sync: {after}")

        expected = {
            ('alice@example.com', 'developers'),
            ('bob@example.com', 'developers'),
            ('charlie@example.com', 'operations'),
            ('dave@example.com', 'operations'),
            ('alice@example.com', 'managers'),
        }

        assert after == expected, f"Expected {expected}, got {after}"

    async def test_group_filtering(self):
        """Test 6: Only sync specified groups (not all groups)"""
        await self.env.clear_openfga_tuples()

        # Set only specific groups to sync (others should be skipped)
        self.set_sync_groups(['developers', 'operations'])

        before = await self.env.get_openfga_memberships()
        logger.info(f"Before sync: {before}")

        # Run sync
        await sync_ldap_to_openfga()

        after = await self.env.get_openfga_memberships()
        logger.info(f"After sync: {after}")

        # Should only have developers and operations, not managers/qa-team/not-in-openfga
        for email, group in after:
            assert group in ['developers', 'operations'], f"Unexpected group {group} was synced"

        # Verify we have the expected groups
        groups_synced = {group for email, group in after}
        assert groups_synced == {'developers', 'operations'}, f"Expected developers and operations, got {groups_synced}"

    async def test_empty_ldap_group(self):
        """Test 7: Handle groups with different members"""
        await self.env.clear_openfga_tuples()

        # Set groups to sync
        self.set_sync_groups(['qa-team'])

        # Create a group with members in OpenFGA
        await self.env.add_openfga_memberships([
            {'email': 'alice@example.com', 'group': 'qa-team'},  # Not in LDAP for this group
            {'email': 'bob@example.com', 'group': 'qa-team'},    # Not in LDAP for this group
            {'email': 'eve@example.com', 'group': 'qa-team'},    # This one IS in LDAP
        ])

        before = await self.env.get_openfga_memberships()
        logger.info(f"Before sync: {before}")

        # Run sync
        await sync_ldap_to_openfga()

        after = await self.env.get_openfga_memberships()
        logger.info(f"After sync: {after}")

        # Should only have eve (the actual member in LDAP)
        expected = {('eve@example.com', 'qa-team')}
        assert after == expected, f"Expected {expected}, got {after}"

    async def test_sync_all_groups(self):
        """Test 8: Sync all LDAP groups when SYNC_GROUPS is not specified"""
        await self.env.clear_openfga_tuples()

        # Don't set SYNC_GROUPS - should sync all groups from LDAP
        os.environ['SYNC_GROUPS'] = ''

        before = await self.env.get_openfga_memberships()
        logger.info(f"Before sync: {before}")

        # Run sync
        await sync_ldap_to_openfga()

        after = await self.env.get_openfga_memberships()
        logger.info(f"After sync: {after}")

        # Should have synced ALL groups from LDAP (including not-in-openfga)
        # Get all memberships from LDAP
        expected = self.env.get_ldap_memberships()

        assert after == expected, f"Expected all groups to be synced. Expected {expected}, got {after}"

        # Verify we have all the different groups
        groups_synced = {group for email, group in after}
        logger.info(f"Groups synced: {groups_synced}")

        # Should include all groups from LDAP
        assert 'developers' in groups_synced, "developers group not synced"
        assert 'operations' in groups_synced, "operations group not synced"
        assert 'managers' in groups_synced, "managers group not synced"
        assert 'qa-team' in groups_synced, "qa-team group not synced"
        assert 'not-in-openfga' in groups_synced, "not-in-openfga group not synced"

    async def test_ignore_groups_not_in_sync_list(self):
        """Test 9: Groups not in SYNC_GROUPS should not be touched"""
        await self.env.clear_openfga_tuples()

        # Set only specific groups to sync
        self.set_sync_groups(['developers', 'operations'])

        # Add memberships for groups both in and NOT in the sync list
        await self.env.add_openfga_memberships([
            # Groups in sync list
            {'email': 'alice@example.com', 'group': 'developers'},
            {'email': 'bob@example.com', 'group': 'developers'},
            {'email': 'charlie@example.com', 'group': 'operations'},
            # Groups NOT in sync list - these should remain untouched
            {'email': 'alice@example.com', 'group': 'managers'},
            {'email': 'eve@example.com', 'group': 'qa-team'},
            {'email': 'frank@example.com', 'group': 'external-group'},
        ])

        before = await self.env.get_openfga_memberships()
        logger.info(f"Before sync: {before}")

        # Run sync
        await sync_ldap_to_openfga()

        after = await self.env.get_openfga_memberships()
        logger.info(f"After sync: {after}")

        # Groups in sync list should be synced correctly
        assert ('alice@example.com', 'developers') in after
        assert ('bob@example.com', 'developers') in after
        assert ('charlie@example.com', 'operations') in after
        assert ('dave@example.com', 'operations') in after  # Should be added from LDAP

        # Groups NOT in sync list should remain completely untouched
        assert ('alice@example.com', 'managers') in after, "managers group membership was removed but shouldn't be"
        assert ('eve@example.com', 'qa-team') in after, "qa-team group membership was removed but shouldn't be"
        assert ('frank@example.com', 'external-group') in after, "external-group membership was removed but shouldn't be"

        # Verify the untouched groups are still there
        groups_in_openfga = {group for email, group in after}
        assert 'managers' in groups_in_openfga, "managers group should still exist"
        assert 'qa-team' in groups_in_openfga, "qa-team group should still exist"
        assert 'external-group' in groups_in_openfga, "external-group should still exist"

    async def test_member_attribute_mode(self):
        """Test 10: Verify member attribute mode works (default)"""
        await self.env.clear_openfga_tuples()

        # Explicitly set to use member attribute (default mode)
        os.environ['LDAP_USE_MEMBEROF'] = 'false'
        self.set_sync_groups(['developers', 'operations'])

        before = await self.env.get_openfga_memberships()
        logger.info(f"Before sync (member mode): {before}")

        # Run sync
        await sync_ldap_to_openfga()

        after = await self.env.get_openfga_memberships()
        logger.info(f"After sync (member mode): {after}")

        # Verify correct memberships
        expected = {
            ('alice@example.com', 'developers'),
            ('bob@example.com', 'developers'),
            ('charlie@example.com', 'operations'),
            ('dave@example.com', 'operations'),
        }

        assert after == expected, f"Member attribute mode failed. Expected {expected}, got {after}"
        logger.info("✅ Member attribute mode works correctly")

    async def test_memberof_mode(self):
        """Test 11: Verify memberOf mode works (for FreeIPA/AD)"""
        await self.env.clear_openfga_tuples()

        # Set to use memberOf attribute
        os.environ['LDAP_USE_MEMBEROF'] = 'true'
        os.environ['LDAP_USER_BASE_DN'] = 'ou=users,dc=example,dc=com'
        self.set_sync_groups(['developers', 'operations'])

        before = await self.env.get_openfga_memberships()
        logger.info(f"Before sync (memberOf mode): {before}")

        # Run sync
        await sync_ldap_to_openfga()

        after = await self.env.get_openfga_memberships()
        logger.info(f"After sync (memberOf mode): {after}")

        # Verify correct memberships (should be same as member mode for test data)
        expected = {
            ('alice@example.com', 'developers'),
            ('bob@example.com', 'developers'),
            ('charlie@example.com', 'operations'),
            ('dave@example.com', 'operations'),
        }

        assert after == expected, f"MemberOf mode failed. Expected {expected}, got {after}"
        logger.info("✅ MemberOf mode works correctly")

        # Reset to default
        os.environ['LDAP_USE_MEMBEROF'] = 'false'

    async def test_both_modes_produce_same_result(self):
        """Test 12: Both member and memberOf modes should produce identical results"""

        # Test with member attribute mode
        await self.env.clear_openfga_tuples()
        os.environ['LDAP_USE_MEMBEROF'] = 'false'
        self.set_sync_groups(['developers', 'operations', 'managers'])

        await sync_ldap_to_openfga()
        member_mode_result = await self.env.get_openfga_memberships()
        logger.info(f"Member mode result: {member_mode_result}")

        # Test with memberOf mode
        await self.env.clear_openfga_tuples()
        os.environ['LDAP_USE_MEMBEROF'] = 'true'
        os.environ['LDAP_USER_BASE_DN'] = 'ou=users,dc=example,dc=com'
        self.set_sync_groups(['developers', 'operations', 'managers'])

        await sync_ldap_to_openfga()
        memberof_mode_result = await self.env.get_openfga_memberships()
        logger.info(f"MemberOf mode result: {memberof_mode_result}")

        # Both should produce identical results
        assert member_mode_result == memberof_mode_result, \
            f"Member and memberOf modes produced different results!\n" \
            f"Member mode: {member_mode_result}\n" \
            f"MemberOf mode: {memberof_mode_result}"

        logger.info("✅ Both modes produce identical results")

        # Reset to default
        os.environ['LDAP_USE_MEMBEROF'] = 'false'

    def print_summary(self):
        """Print test summary"""
        total = self.passed + self.failed
        logger.info(f"\n{'='*60}")
        logger.info(f"TEST SUMMARY")
        logger.info(f"{'='*60}")
        logger.info(f"Total tests: {total}")
        logger.info(f"Passed: {self.passed}")
        logger.info(f"Failed: {self.failed}")
        logger.info(f"Success rate: {(self.passed/total*100) if total > 0 else 0:.1f}%")
        logger.info(f"{'='*60}\n")


async def main():
    """Main test execution"""
    logger.info("Starting LDAP to OpenFGA Sync Test Suite")

    env = TestEnvironment()

    try:
        # Wait for services
        env.wait_for_services()

        # Setup OpenFGA
        await env.setup_openfga()

        # Create test runner
        runner = TestRunner(env)

        # Run all tests
        await runner.run_test("Initial sync from LDAP to empty OpenFGA", runner.test_initial_sync)
        await runner.run_test("No changes when already in sync", runner.test_no_changes)
        await runner.run_test("Add new members from LDAP", runner.test_additions)
        await runner.run_test("Remove members not in LDAP", runner.test_deletions)
        await runner.run_test("Mixed additions and deletions", runner.test_mixed_changes)
        await runner.run_test("Group filtering (only sync specified groups)", runner.test_group_filtering)
        await runner.run_test("Handle groups with different members", runner.test_empty_ldap_group)
        await runner.run_test("Sync all groups when SYNC_GROUPS not specified", runner.test_sync_all_groups)
        await runner.run_test("Groups not in SYNC_GROUPS are not touched", runner.test_ignore_groups_not_in_sync_list)
        await runner.run_test("Member attribute mode works correctly", runner.test_member_attribute_mode)
        await runner.run_test("MemberOf mode works correctly", runner.test_memberof_mode)
        await runner.run_test("Both modes produce identical results", runner.test_both_modes_produce_same_result)

        # Print summary
        runner.print_summary()

        # Exit with appropriate code
        sys.exit(0 if runner.failed == 0 else 1)

    finally:
        await env.cleanup()


if __name__ == "__main__":
    asyncio.run(main())

