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

### Submission a file

```bash
python -m detonatorcmd /path/to/malware.exe --profile live_defender
```

### Submission with additional options

```bash
python -m detonatorcmd /path/to/malware.exe \
    --profile live_defender \
    --comment "Testing new payload" \
    --project "research_2025" \
    --source-url "https://github.com/user/repo" \
    --timeout 7200
```

## Options

- `--profile, -p`: Profile to use (default: live_defender)
- `--comment, -c`: Comment for the submission
- `--project, -j`: Project name for the submission
- `--source-url, -s`: Source URL of the file
- `--api-url`: API base URL (default: http://localhost:8000)
- `--timeout`: Timeout in seconds for submission completion (default: 10)

## Examples

```bash
# List profiles
python -m detonatorcmd list-profiles

# Basic submission
python -m detonatorcmd submission malware.exe

# Submission with custom profile
python -m detonatorcmd submission malware.exe -p new_defender

# Submission with full options
python -m detonatorcmd submission malware.exe \
    -p live_defender \
    -c "Testing obfuscated payload" \
    -j "evasion_research" \
    -s "https://malware-samples.com/sample123" \
    --timeout 7200
```
