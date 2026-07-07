import psutil

def list_processes():
    # Get a list of all running processes
    processes = psutil.process_iter(['pid', 'name'])

    # Print the details of each process
    for process in processes:
        print(f"PID: {process.info['pid']}, Name: {process.info['name']}")
