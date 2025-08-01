#!/usr/bin/env python3
"""
Configuration test script

This script helps test the configuration injection locally without running the full sync.
"""

import os
import sys
from pathlib import Path

def test_environment_variables():
    """Test if required environment variables are set."""
    
    print("🔍 Testing Environment Variables")
    print("=" * 50)
    
    # Required secrets
    required_secrets = {
        'WEREAD_COOKIE': '微信读书 Cookie',
        'NOTION_TOKEN': 'Notion API Token',
        'NOTION_DATABASE_ID': 'Notion 数据库 ID'
    }
    
    # Optional variables with defaults
    optional_vars = {
        'SYNC_ALL_BOOKS': 'true',
        'SYNC_FINISHED_BOOKS': 'true',
        'SYNC_UNFINISHED_BOOKS': 'true',
        'BATCH_SIZE': '5',
        'LOG_LEVEL': 'INFO'
    }
    
    print("\n📋 Required Secrets:")
    missing_secrets = []
    for var, description in required_secrets.items():
        value = os.getenv(var)
        if value:
            print(f"  ✅ {var}: {'*' * min(len(value), 10)}...")
        else:
            print(f"  ❌ {var}: Missing")
            missing_secrets.append(var)
    
    print("\n⚙️  Optional Variables:")
    for var, default in optional_vars.items():
        value = os.getenv(var, default)
        print(f"  {'✅' if value else '❌'} {var}: {value}")
    
    if missing_secrets:
        print(f"\n⚠️  Missing required secrets: {', '.join(missing_secrets)}")
        print("   Please set these environment variables before running the sync.")
        return False
    
    print("\n✅ All required secrets are set!")
    return True

def test_config_injection():
    """Test the configuration injection script."""
    
    print("\n🔧 Testing Configuration Injection")
    print("=" * 50)
    
    try:
        # Import the injection script
        sys.path.insert(0, str(Path(__file__).parent))
        from inject_config import main
        
        # Run the injection
        main()
        
        # Check if config.py was created
        config_path = Path(__file__).parent.parent / 'config.py'
        if config_path.exists():
            print("✅ Configuration file created successfully")
            
            # Read and display a summary
            with open(config_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            print(f"📄 Config file size: {len(content)} characters")
            print("📄 Config file location:", config_path)
            
            return True
        else:
            print("❌ Configuration file was not created")
            return False
            
    except Exception as e:
        print(f"❌ Configuration injection failed: {e}")
        return False

def test_python_environment():
    """Test Python environment and dependencies."""
    
    print("\n🐍 Testing Python Environment")
    print("=" * 50)
    
    try:
        import asyncio
        print("✅ asyncio: Available")
    except ImportError:
        print("❌ asyncio: Not available")
        return False
    
    # Test if main.py can be imported
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        import main
        print("✅ main.py: Can be imported")
    except Exception as e:
        print(f"❌ main.py: Import failed - {e}")
        return False
    
    return True

def main():
    """Main test function."""
    
    print("🧪 Configuration Test Suite")
    print("=" * 50)
    
    tests = [
        ("Environment Variables", test_environment_variables),
        ("Python Environment", test_python_environment),
        ("Configuration Injection", test_config_injection)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name}: Test failed with exception - {e}")
            results.append((test_name, False))
    
    print("\n📊 Test Results Summary")
    print("=" * 50)
    
    all_passed = True
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status}: {test_name}")
        if not result:
            all_passed = False
    
    print("\n" + "=" * 50)
    if all_passed:
        print("🎉 All tests passed! Your configuration is ready.")
        print("💡 You can now run the GitHub Actions workflow.")
    else:
        print("⚠️  Some tests failed. Please fix the issues before running the workflow.")
        print("📖 Check the documentation at docs/GITHUB_SETUP.md for help.")
    
    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)