import os
import paramiko

'''
This is the port number on which the Flask application will run, unless overriden 
by the environment variable `PORT`.
'''
APP_PORT = 5001

'''
These parameters are used to connect to the SLURM scheduler via SSH. A private key is
used to authenticate the connection. The `SSH_USERNAME` is the username used to connect
to the SLURM scheduler, and the `SSH_HOSTNAME` is the hostname of the SLURM scheduler.
'''
SSH_USERNAME = "areynolds"
SSH_HOSTNAME = "tools0.altiusinstitute.org"
SSH_PRIVATE_KEY_PATH = os.path.expanduser(f'/Users/{SSH_USERNAME}/.ssh/id_ed25519')
SSH_KEY = paramiko.Ed25519Key.from_private_key_file(SSH_PRIVATE_KEY_PATH)

'''
SLURM test parameters
'''
BAD_SLURM_JOB_ID = -1
SLURM_TEST_JOB_ID = 123
SLURM_TEST_JOB_STATUS = {
  'job_id': '123', 
  'job_name': 'abcd1234', 
  'state': 'COMPLETED', 
  'user': 'username', 
  'partition': 'partition', 
  'time': 'UNLIMITED', 
  'start': '2025-04-14T08:57:46', 
  'end': '2025-04-14T11:00:44', 
  'elapsed': '02:02:58',
}

'''
These parameters are used to define the SLURM job status codes and their explanations.
'''
SLURM_STATUS = {
  "COMPLETED": {
    "code": "CD",
    "explanation": "The job has completed successfully.",
  },
  "COMPLETING": {
    "code": "CG",
    "explanation": "The job is finishing but some processes are still active.",
  },
  "FAILED": {
    "code": "F",
    "explanation": "The job terminated with a non-zero exit code and failed to execute.",
  },
  "PENDING": {
    "code": "PD",
    "explanation": "The job is waiting for resource allocation. It will eventually run.",
  },
  "PREEMPTED": {
    "code": "PR",
    "explanation": "The job was terminated because of preemption by another job.",
  },
  "RUNNING": {
    "code": "R",
    "explanation": "The job currently is allocated to a node and is running.",
  },
  "SUSPENDED": {
    "code": "S",
    "explanation": "A running job has been stopped with its cores released to other jobs.",
  },
  "STOPPED": {
    "code": "ST",
    "explanation": "A running job has been stopped with its cores retained.",
  },
}

'''
These parameters are used to define the tasks that can be submitted to the SLURM scheduler
through this proxy. 

The `cmd` parameter is the command that will be executed on the host submitting a job to 
the SLURM scheduler. The `description` parameter is a short summary of the task.
'''
TASK_DESCRIPTION = {
  "hello_world": {
    "cmd": "echo",
    "description": "Prints 'Hello world!'",
  },
}