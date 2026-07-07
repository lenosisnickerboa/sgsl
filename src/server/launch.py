import subprocess
import os

# source: https://lucadrf.dev/blog/python-subprocess-buffers/

full_program_path = os.path.abspath('./lab/server.bat')

# Replace 'your_program.exe' with the actual program name or path
program = [full_program_path, '3', '44']

with subprocess.Popen(program, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as p:
    while True:
        stdout_text = p.stdout.read1().decode("utf-8")
        print("STDIN: ", stdout_text, end='', flush=True)
        stderr_text = p.stderr.read1().decode("utf-8")
        print("STDERR: ", stderr_text, end='', flush=True)

        if not stdout_text and not stderr_text:
            break

# Wait for the process to finish and get the return code
return_code = p.wait()

# Check if the process exited successfully
if return_code == 0:
    print(f"\nThe program exited successfully.")
else:
    print(f"\nThe program exited with an error (return code {return_code}).")
