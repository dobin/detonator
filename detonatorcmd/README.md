# Detonator Command Line Client

A command line client for the Detonator malware analysis system.

## Installation

```bash
pip install -r requirements.txt
```

## Usage

### List available profiles

```bash
python -m detonatorcmd list-profiles
```

### Scan a file

```bash
python -m detonatorcmd scan /path/to/malware.exe --profile running_defender
```

### Scan with additional options

```bash
python -m detonatorcmd scan /path/to/malware.exe \
    --profile running_defender \
    --comment "Testing new payload" \
    --project "research_2025" \
    --source-url "https://github.com/user/repo" \
    --timeout 7200
```

## Options

- `--profile, -p`: Profile to use (default: running_defender)
- `--comment, -c`: Comment for the scan
- `--project, -j`: Project name for the scan
- `--source-url, -s`: Source URL of the file
- `--api-url`: API base URL (default: http://localhost:8000)
- `--timeout`: Timeout in seconds for scan completion (default: 10)

## Examples

```bash
# List profiles
python -m detonatorcmd list-profiles

# Basic scan
python -m detonatorcmd scan malware.exe

# Scan with custom profile
python -m detonatorcmd scan malware.exe -p new_defender

# Scan with full options
python -m detonatorcmd scan malware.exe \
    -p running_defender \
    -c "Testing obfuscated payload" \
    -j "evasion_research" \
    -s "https://malware-samples.com/sample123" \
    --timeout 7200
```
