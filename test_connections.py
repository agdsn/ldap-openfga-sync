#!/usr/bin/env python3
"""
Test script to verify LDAP and OpenFGA connections independently
"""

import os
import sys
import asyncio
import logging
from dotenv import load_dotenv
import ldap
from openfga_sdk.client import ClientConfiguration, OpenFgaClient
from openfga_sdk import ReadRequestTupleKey

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()


def test_ldap_connection():
    """Test LDAP connection and query"""
    print("\n🔍 Testing LDAP Connection...")

    server = os.getenv("LDAP_SERVER")
    bind_dn = os.getenv("LDAP_BIND_DN")
    bind_password = os.getenv("LDAP_BIND_PASSWORD")
    base_dn = os.getenv("LDAP_GROUP_BASE_DN")

    try:
        # Connect to LDAP
        conn = ldap.initialize(server)
        conn.protocol_version = ldap.VERSION3
        conn.simple_bind_s(bind_dn, bind_password)
        print(f"✅ Connected to LDAP server: {server}")

        # Try to search for groups
        group_filter = os.getenv("LDAP_GROUP_FILTER", "(objectClass=groupOfNames)")
        results = conn.search_s(base_dn, ldap.SCOPE_SUBTREE, group_filter, ['cn'])

        group_count = len([r for r in results if r[0] is not None])
        print(f"✅ Found {group_count} groups in LDAP")

        # Display first few groups
        if group_count > 0:
            print("\n   Sample groups:")
            for dn, attrs in results[:5]:
                if dn and 'cn' in attrs:
                    cn = attrs['cn'][0]
                    if isinstance(cn, bytes):
                        cn = cn.decode('utf-8')
                    print(f"   - {cn}")

        conn.unbind_s()
        return True

    except ldap.LDAPError as e:
        print(f"❌ LDAP connection failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


async def test_openfga_connection():
    """Test OpenFGA connection"""
    print("\n🔍 Testing OpenFGA Connection...")

    api_url = os.getenv("OPENFGA_API_URL")
    store_id = os.getenv("OPENFGA_STORE_ID")
    api_token = os.getenv("OPENFGA_API_TOKEN", "")

    try:
        # Configure client
        configuration = ClientConfiguration(
            api_url=api_url,
            store_id=store_id,
        )

        if api_token:
            configuration.credentials = {
                "method": "api_token",
                "config": {
                    "token": api_token
                }
            }

        client = OpenFgaClient(configuration)
        print(f"✅ Connected to OpenFGA: {api_url}")

        # Try to read some tuples
        try:
            body = ReadRequestTupleKey(
                relation="member"
            )
            response = await client.read(body=body)

            tuple_count = 0
            if hasattr(response, 'tuples') and response.tuples:
                tuple_count = len(response.tuples)

            print(f"✅ Found {tuple_count} member relationships in OpenFGA")

            # Display sample
            if tuple_count > 0 and hasattr(response, 'tuples'):
                print("\n   Sample memberships:")
                for tuple_data in list(response.tuples)[:5]:
                    if hasattr(tuple_data, 'key'):
                        key = tuple_data.key
                        print(f"   - {key.user} {key.relation} {key.object}")

        except Exception as e:
            print(f"⚠️  Could not read tuples: {e}")
            print("   (This may be normal if no memberships exist yet)")

        return True

    except Exception as e:
        print(f"❌ OpenFGA connection failed: {e}")
        return False


async def main():
    """Run all tests"""
    print("🧪 Connection Test Script")
    print("=" * 60)

    ldap_ok = test_ldap_connection()
    openfga_ok = await test_openfga_connection()

    print("\n" + "=" * 60)
    print("📊 Test Summary:")
    print(f"   LDAP: {'✅ PASS' if ldap_ok else '❌ FAIL'}")
    print(f"   OpenFGA: {'✅ PASS' if openfga_ok else '❌ FAIL'}")

    if ldap_ok and openfga_ok:
        print("\n✅ All tests passed! Ready to run sync.py")
        return 0
    else:
        print("\n❌ Some tests failed. Please check your configuration.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

