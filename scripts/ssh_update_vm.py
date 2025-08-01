import subprocess
import sys 


hostname = sys.argv[1]
username = "hacker"
script_path = "C:\\Users\\hacker\\Desktop\\update_rededr.ps1"

base_cmd = f'ssh {username}@{hostname} '


print("Updating RedEdr")
cmd = base_cmd + f'powershell -ExecutionPolicy Bypass -File "{script_path}"'
result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
print(result.stdout)
print(result.stderr)


print("Rebooting")
cmd = base_cmd + "shutdown /r /t 0"
result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
print(result.stdout)
print(result.stderr)
