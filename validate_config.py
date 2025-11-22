#!/usr/bin/env python3
"""
Example script demonstrating how to use the LDAP to OpenFGA sync
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def validate_config():
    """Validate that all required configuration is set"""
    required_vars = [
        'LDAP_SERVER',
        'LDAP_BIND_DN',
        'LDAP_BIND_PASSWORD',
        'LDAP_GROUP_BASE_DN',
        'OPENFGA_API_URL',
        'OPENFGA_STORE_ID',
    ]

    missing = []
    for var in required_vars:
        if not os.getenv(var):
            missing.append(var)

    if missing:
        print("❌ Missing required configuration variables:")
        for var in missing:
            print(f"   - {var}")
        return False

    print("✅ All required configuration variables are set")
    return True

def display_config():
    """Display current configuration (masking sensitive values)"""
    print("\n📋 Current Configuration:")
    print(f"   LDAP Server: {os.getenv('LDAP_SERVER')}")
    print(f"   LDAP Bind DN: {os.getenv('LDAP_BIND_DN')}")
    print(f"   LDAP Group Base DN: {os.getenv('LDAP_GROUP_BASE_DN')}")
    print(f"   LDAP Group Filter: {os.getenv('LDAP_GROUP_FILTER', '(objectClass=groupOfNames)')}")
    print(f"   LDAP Member Attribute: {os.getenv('LDAP_MEMBER_ATTRIBUTE', 'member')}")
    print(f"   OpenFGA API URL: {os.getenv('OPENFGA_API_URL')}")
    print(f"   OpenFGA Store ID: {os.getenv('OPENFGA_STORE_ID')}")
    print(f"   Dry Run Mode: {os.getenv('SYNC_DRY_RUN', 'false')}")
    print()

if __name__ == "__main__":
    print("🔍 LDAP to OpenFGA Sync - Configuration Validator\n")

    if validate_config():
        display_config()
        print("✅ Configuration is valid. You can now run:")
        print("   python sync.py")
    else:
        print("\n❌ Please update your .env file with the missing configuration")
        print("   See .env.example for reference")

