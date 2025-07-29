import os
import sys
import argparse

from .ui_client import DetonatorClientUi
from .api_client import DetonatorClientApi
from .client import DetonatorClient


def print_profiles(profiles):
    if not profiles:
        print("No profiles available or error fetching profiles")
        return

    for profile_name, profile in profiles.items():
        print("")
        print(f"Profile: {profile_name}")
        print(f"    Connector: {profile.get('connector', '')}")
        print(f"    EDR Collector: {profile.get('edr_collector', '')}")
        print(f"    Port: {profile.get('port', '')}")
        if profile.get('comment'):
            print(f"    Comment: {profile.get('comment', '')}")
        if profile.get('data', {}).get('image_reference'):
            image_reference_name = profile.get('data', {}).get('image_reference', '').split("/")[-1]  # Last part
            print(f"    Image Reference: {image_reference_name}")
        if profile.get('data', {}).get('ip'):
            print(f"    IP: {profile.get('data', {}).get('ip')}")


def main():
    parser = argparse.ArgumentParser(description="Detonator Command Line Client")
    parser.add_argument("mode", choices=["ui", "api"], help="Accessing \"ui\" for web UI or \"api\" for API mode")
    parser.add_argument("command", choices=["scan", "profiles"], help="Command to execute")
    parser.add_argument("filename", nargs="?", help="File to scan")

    # Connection related
    parser.add_argument("--url", default="http://localhost:8000", help="API base URL")
    parser.add_argument("--password", default="", help="Password for the profile (if required)")
    parser.add_argument("--token", default="", help="Token (if you have one)")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")

    # Scan related
    parser.add_argument("--profile", "-p", default="", help="Profile to use")
    parser.add_argument("--file-comment", "-c", default="", help="Comment for the file")
    parser.add_argument("--scan-comment", "-sc", default="", help="Comment for the scan")
    parser.add_argument("--project", "-j", default="", help="Project name for the scan")
    parser.add_argument("--source-url", "-s", default="", help="Source URL of the file")
    #parser.add_argument("--timeout", type=int, default=3600, help="Timeout in seconds for scan completion")
    parser.add_argument("--runtime", type=int, default=10, help="Runtime in seconds")
    parser.add_argument("--no-randomize-filename", action="store_true", default=False, help="Randomize filename before upload")
    
    args = parser.parse_args()
    
    detClient: DetonatorClient
    if args.mode == "ui":
        detClient = DetonatorClientUi(args.url, args.token, args.debug)
    elif args.mode == "api":
        detClient = DetonatorClientApi(args.url, args.token, args.debug)
    else:
        print("Invalid mode. Use 'ui' or 'api'.")
        sys.exit(1)

    if args.command == "profiles":
        profiles = detClient.get_profiles()
        print_profiles(profiles)
    
    elif args.command == "scan":
        if not args.filename:
            print("Error: filename is required for scan command")
            parser.print_help()
            return
            
        # Check: if file exists
        if not os.path.exists(args.filename):
            print(f"Error: File {args.filename} does not exist")
            return
        
        # Check: Profile
        if not detClient.valid_profile(args.profile):
            print(f"Error: Profile '{args.profile}' not found")
            print("Available profiles:")
            print_profiles(detClient.get_profiles())
            return
        
        detClient.scan_file(
                args.filename,
                args.source_url,
                args.file_comment,
                args.scan_comment,
                args.project,
                args.profile,
                args.password,
                args.runtime,
                not args.no_randomize_filename
            )
        

if __name__ == "__main__":
    main()
