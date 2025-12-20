#!/usr/bin/env python3
"""
Automated test script for Detonator server and VMs.

This script tests the complete workflow:
1. Connect to the Detonator server
2. Upload a test file
3. Wait for submission completion
4. Verify results

Usage:
    python tests/test_automated_submission.py --url http://localhost:8000 --token YOUR_TOKEN --profile PROFILE_NAME

Requirements:
    - A running Detonator server
    - At least one configured profile with a working VM
    - Valid authentication token
"""

import argparse
import os
import sys
import tempfile
import time
from pathlib import Path

# Add parent directory to path to import detonatorcmd
sys.path.insert(0, str(Path(__file__).parent.parent))

from detonatorcmd.client import DetonatorClient


class TestResults:
    """Container for test results"""
    def __init__(self):
        self.tests_run = 0
        self.tests_passed = 0
        self.tests_failed = 0
        self.errors = []
    
    def add_pass(self, test_name):
        self.tests_run += 1
        self.tests_passed += 1
        print(f"✓ PASS: {test_name}")
    
    def add_fail(self, test_name, error_msg):
        self.tests_run += 1
        self.tests_failed += 1
        self.errors.append((test_name, error_msg))
        print(f"✗ FAIL: {test_name}")
        print(f"  Error: {error_msg}")
    
    def summary(self):
        print("\n" + "="*60)
        print(f"Test Summary: {self.tests_passed}/{self.tests_run} passed")
        if self.tests_failed > 0:
            print(f"\nFailed tests:")
            for test_name, error in self.errors:
                print(f"  - {test_name}: {error}")
        print("="*60)
        return self.tests_failed == 0


def test_server_connection(client, results):
    """Test 1: Verify server is accessible and profiles are available"""
    print("\n[Test 1] Testing server connection...")
    try:
        profiles = client.get_profiles()
        if profiles:
            results.add_pass("Server connection and profile retrieval")
            print(f"  Found {len(profiles)} profile(s): {', '.join(profiles.keys())}")
            return profiles
        else:
            results.add_fail("Server connection", "No profiles returned (may be empty or error)")
            return None
    except Exception as e:
        results.add_fail("Server connection", str(e))
        return None


def test_profile_validation(client, profile_name, results):
    """Test 2: Verify specified profile exists"""
    print(f"\n[Test 2] Validating profile '{profile_name}'...")
    try:
        if client.valid_profile(profile_name):
            profile = client.get_profile(profile_name)
            results.add_pass(f"Profile '{profile_name}' validation")
            print(f"  Profile details:")
            print(f"    Connector: {profile.get('connector', 'N/A')}")
            print(f"    EDR Collector: {profile.get('edr_collector', 'N/A')}")
            return profile
        else:
            results.add_fail(f"Profile '{profile_name}' validation", 
                           f"Profile not found. Available profiles: {', '.join(client.get_profiles().keys())}")
            return None
    except Exception as e:
        results.add_fail(f"Profile '{profile_name}' validation", str(e))
        return None


def test_file_upload_and_submission(client: DetonatorClient, test_file, profile_name, runtime, results):
    """Test 3: Upload file and complete submission"""
    print(f"\n[Test 3] Uploading test file and running submission...")
    print(f"  File: {test_file}")
    print(f"  Profile: {profile_name}")
    print(f"  Runtime: {runtime}s")
    
    # Run the submission
    start_time = time.time()
    try:
        submission_id = client.submit_file(
            filename=test_file,
            source_url="automated_test",
            file_comment="automated_test",
            submission_comment="automated_test",
            project="automated_test",
            profile_name=profile_name,
            password="",
            runtime=runtime,
            randomize_filename=False
        )
        
        if not submission_id:
            results.add_fail("File upload and submission", "Failed to create submission (submission_id is None)")
            return
        
        elapsed_time = time.time() - start_time
        print(f"  Submission ID: {submission_id}")
        print(f"  Upload and submission time: {elapsed_time:.2f}s")

        # Retrieve submission results
        submission = client.get_submission(submission_id)
        if not submission:
            results.add_fail("File upload and submission", "Failed to retrieve submission results")
            return
        
        # Verify submission status is "finished"
        if submission.get('status') != 'finished':
            results.add_fail("File upload and submission", 
                           f"Expected status 'finished', got '{submission.get('status')}'")
            return
        
        # Verify submission edr_verdict is "not_detected"
        if submission.get('edr_verdict') != 'not_detected':
            results.add_fail("File upload and submission", 
                           f"Expected edr_verdict 'not_detected', got '{submission.get('edr_verdict')}'")
            return
        
        results.add_pass("File upload and submission")
        print(f"  Status: {submission.get('status')}")
        print(f"  Result: {submission.get('edr_verdict')}")
        
    except Exception as e:
        results.add_fail("File upload and submission", str(e))
          


def main():
    parser = argparse.ArgumentParser(
        description="Automated test for Detonator server and VMs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    # Required arguments
    parser.add_argument("--url", default="https://detonatorapi.r00ted.ch", help="Detonator server URL (e.g., http://localhost:8000)")
    parser.add_argument("--token", default="", help="Authentication token")
    parser.add_argument("--profile", default="mde", help="Profile name to test")
    
    # Optional arguments
    parser.add_argument("--runtime", type=int, default=10, 
                       help="Submission runtime in seconds (default: 10)")
    parser.add_argument("--test-file", default=None,
                       help="Path to test file (default: create temporary file)")
    parser.add_argument("--debug", action="store_true",
                       help="Enable debug output")
    parser.add_argument("--keep-test-file", action="store_true",
                       help="Keep the test file after completion")
    
    args = parser.parse_args()
    
    # Print test configuration
    print("="*60)
    print("Detonator Automated Test Suite")
    print("="*60)
    print(f"Server URL: {args.url}")
    print(f"Profile: {args.profile}")
    print(f"Runtime: {args.runtime}s")
    print(f"Debug: {args.debug}")
    
    # Initialize client
    client = DetonatorClient(
        baseUrl=args.url,
        token=args.token,
        debug=args.debug
    )

    # Initialize results tracker
    results = TestResults()
    
    # Create or use test file
    test_file = args.test_file
    if not test_file:
        test_file = "/mnt/d/hacking/some_malware/procexp64.exe"
    else:
        if not os.path.exists(test_file):
            print(f"Error: Test file not found: {test_file}")
            return 1
    print(f"Using test file: {test_file}")
    
    # Run tests
    profiles = test_server_connection(client, results)
    if profiles is None:
        print("\n⚠ Cannot continue without server connection")
        return 1
    
    profile = test_profile_validation(client, args.profile, results)
    if profile is None:
        print(f"\n⚠ Cannot continue without valid profile '{args.profile}'")
        return 1
    
    test_file_upload_and_submission(client, test_file, args.profile, args.runtime, results)

    
    # Print summary and exit
    success = results.summary()
    
    if success:
        print("\n✓ All tests passed! Server and VMs are operational.")
        return 0
    else:
        print("\n✗ Some tests failed. Please check the errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
