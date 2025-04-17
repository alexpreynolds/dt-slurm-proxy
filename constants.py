import os
import pymongo
import paramiko
from enum import Enum

"""
Application name and port
"""
APP_NAME = os.environ.get("NAME", "dt-slurm-proxy")
APP_PORT = os.environ.get("PORT", 5001)

"""
RabbitMQ connection parameters

The defaults point to a local instance of a test RabbitMQ server, which is only
for test use.

Specific parameters should be passed in as environment variables, which reflect
the configuration of the organization's RabbitMQ server. Please see: 
https://github.com/Altius/messaging for more details on host, port, username,
password, path and other parameters.
"""
RABBITMQ_HOST = os.environ.get("RABBITMQ_HOST", "localhost")
RABBITMQ_PORT = os.environ.get("RABBITMQ_PORT", 5672)
RABBITMQ_USERNAME = os.environ.get("RABBITMQ_USERNAME", "guest")
RABBITMQ_PASSWORD = os.environ.get("RABBITMQ_PASSWORD", "guest")
RABBITMQ_PATH = os.environ.get("RABBITMQ_PATH", "/")

"""
These parameters are used to define the tasks that can be submitted to the SLURM scheduler
through this proxy. 

The `cmd` parameter is the command that will be executed on the host submitting a job to 
the SLURM scheduler. 

The `description` parameter is a short summary of the task. 

The `default_params` parameter is a list of default parameters that will be passed to the
command.

The `notification_queue` parameter is the name of the RabbitMQ queue that will be used to
send notifications about a completed task. This queue name should be specific to the task.
"""
TASK_DESCRIPTION = {
    "echo_hello_world": {
        "cmd": "echo",
        "default_params": [],
        "description": "Prints a generic hello world! message",
        "notification_queue": "hello",
    },
}

"""
Task submission methods
"""


class TaskSubmitMethods(Enum):
    SSH = 1
    REST = 2


"""
These parameters are used to connect to the SLURM scheduler via SSH. A private key is
used to authenticate the connection. The `SSH_USERNAME` is the username used to connect
to the SLURM scheduler, and the `SSH_HOSTNAME` is the hostname of the SLURM scheduler.
"""
SSH_USERNAME = os.environ.get("SSH_USERNAME", "areynolds")
SSH_HOSTNAME = os.environ.get("SSH_HOSTNAME", "tools0.altiusinstitute.org")
SSH_PRIVATE_KEY_PATH = os.path.expanduser(f"/Users/{SSH_USERNAME}/.ssh/id_ed25519")
SSH_KEY = paramiko.Ed25519Key.from_private_key_file(SSH_PRIVATE_KEY_PATH)

"""
Mongodb connection
"""
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
MONGODB_CLIENT = pymongo.MongoClient(
    MONGODB_URI,
    serverSelectionTimeoutMS=1000,
)
MONGODB_MONITOR_DB = MONGODB_CLIENT["monitordb"]
MONGODB_JOBS_COLLECTION = MONGODB_MONITOR_DB["jobs"]

"""
How frequently to poll the SLURM scheduler for job status updates.
"""
MONITOR_POLLING_INTERVAL = os.environ.get("MONITOR_POLLING_INTERVAL", 1)  # in minutes

"""
SLURM test parameters
"""
BAD_SLURM_JOB_ID = -1
SLURM_TEST_JOB_ID = 123
SLURM_TEST_JOB_STATUS = {
    "job_id": "123",
    "job_name": "abcd1234",
    "state": "COMPLETED",
    "user": "username",
    "partition": "partition",
    "time": "UNLIMITED",
    "start": "2025-04-14T08:57:46",
    "end": "2025-04-14T11:00:44",
    "elapsed": "02:02:58",
}

"""
These parameters are used to define the SLURM job status codes and their explanations.
"""
SLURM_STATE = {
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
SLURM_STATE_UNKNOWN = "UNKNOWN"
SLURM_STATE_END_STATES = ["COMPLETED", "FAILED", "CANCELLED", "SUSPENDED"]
