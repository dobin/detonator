# Detonator Command Line Client

A command line client for the Detonator malware analysis system.

## Installation

```bash
pip install -r requirements.txt
```

## Usage

### List available EDR templates

```bash
python -m detonatorcmd list-templates
```

### Scan a file

```bash
python -m detonatorcmd scan /path/to/malware.exe --edr-template running_rededr
```

### Scan with additional options

```bash
python -m detonatorcmd scan /path/to/malware.exe \
    --edr-template running_rededr \
    --comment "Testing new payload" \
    --project "research_2025" \
    --source-url "https://github.com/user/repo" \
    --timeout 7200
```

## Options

- `--edr-template, -t`: EDR template to use (default: running_rededr)
- `--comment, -c`: Comment for the scan
- `--project, -p`: Project name for the scan
- `--source-url, -s`: Source URL of the file
- `--api-url`: API base URL (default: http://localhost:8000)
- `--timeout`: Timeout in seconds for scan completion (default: 3600)

## Examples

```bash
# List templates
python -m detonatorcmd list-templates

# Basic scan
python -m detonatorcmd scan malware.exe

# Scan with custom template
python -m detonatorcmd scan malware.exe -t elastic_edr

# Scan with full options
python -m detonatorcmd scan malware.exe \
    -t running_rededr \
    -c "Testing obfuscated payload" \
    -p "evasion_research" \
    -s "https://malware-samples.com/sample123" \
    --timeout 7200
```
