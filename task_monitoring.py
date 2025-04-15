import pymongo
import paramiko
from flask import (
    Blueprint,
    request,
    Response,
    json,
    stream_with_context,
)
from constants import (
    SSH_USERNAME,
    SSH_HOSTNAME,
    SSH_KEY,
    SLURM_STATUS,
    SLURM_TEST_JOB_ID,
    SLURM_TEST_JOB_STATUS,
    MONGODB_JOBS_COLLECTION,
)

SSH_CLIENT = paramiko.SSHClient()
SSH_CLIENT.set_missing_host_key_policy(paramiko.AutoAddPolicy())

SLURM_STATUS_KEYS = SLURM_STATUS.keys()

task_monitoring = Blueprint("task_monitoring", __name__)

"""
This module defines a Flask blueprint for task monitoring, which maintains job state via
a MongoDB database and communicates with a SLURM scheduler to generate updated job status.

A POST request contains a job id value and task metadata, which is added to the 
database if the job id is not already present. A successful POST response returns 
the job object from the original request.

A GET request takes a job id or status and returns job information via the SLURM
scheduler. A successful GET response returns the job object(s) from the query, with 
the job information appended.

A DELETE request takes a job id and removes the job from the database and SLURM scheduler.
A successful DELETE response returns the job object from the original request, with 
the job status appended.
"""


@task_monitoring.route("/", methods=["POST"])
def post() -> Response:
    request_info = request.get_json(force=True)
    job = request_info.get("job")
    if not job:
        return {"error": "No job provided"}, 400
    response = None
    if monitor_new_slurm_job(job):
        response = Response(
            stream_with_context(json.dumps(job)),
            status=200,
            mimetype="application/json",
        )
    else:
        response = Response(
            stream_with_context({"Error": "Failed to monitor job"}),
            status=400,
            mimetype="application/json",
        )
    return response


"""
CRUD operations for the job monitoring database.
"""

def monitor_new_slurm_job(job: dict) -> bool:
    slurm_job_id = int(job["slurm_job_id"])
    slurm_job_status_metadata = get_current_slurm_job_metadata_by_id(slurm_job_id)
    if not slurm_job_status_metadata:
        return False
    slurm_job_status = (
        slurm_job_status_metadata["state"] if slurm_job_status_metadata else "Unknown"
    )
    slurm_job_task_metadata = job["task"]
    # update the monitor database with the job information
    result = add_job_to_monitor_db(
        slurm_job_id, slurm_job_status, slurm_job_task_metadata
    )
    return result


def add_job_to_monitor_db(
    slurm_job_id: int, slurm_job_status: str, slurm_job_task_metadata: dict
) -> bool:
    job = {
        "slurm_job_id": slurm_job_id,
        "slurm_job_status": slurm_job_status,
        "task": slurm_job_task_metadata,
    }
    # check if the job already exists in the database
    try:
        jobs_coll = MONGODB_JOBS_COLLECTION
        if not jobs_coll.find_one({"slurm_job_id": slurm_job_id}):
            jobs_coll.insert_one(job)
        return True
    except pymongo.errors.PyMongoError as err:
        print(f" * Error adding job to monitor database: {err}")
        return False


def get_job_metadata_from_monitor_db(slurm_job_id: int) -> dict:
    # query the database for the job with the given slurm_job_id
    try:
        jobs_coll = MONGODB_JOBS_COLLECTION
        result = jobs_coll.find_one({"slurm_job_id": slurm_job_id})
        if result:
            job_metadata = {
                "slurm_job_id": result["slurm_job_id"],
                "slurm_job_status": result["slurm_job_status"],
                "task": result["task"],
            }
            return job_metadata
        else:
            return None
    except pymongo.errors.PyMongoError as err:
        print(f" * Error retrieving job information from monitor database: {err}")
        return None


def update_job_status_in_monitor_db(
    slurm_job_id: int, new_slurm_job_status: str
) -> bool:
    # update the job status in the database
    try:
        jobs_coll = MONGODB_JOBS_COLLECTION
        result = jobs_coll.update_one(
            {"slurm_job_id": slurm_job_id},
            {"$set": {"slurm_job_status": new_slurm_job_status}},
        )
        if result.modified_count == 0:
            return False
        return True
    except pymongo.errors.PyMongoError as err:
        print(f" * Error updating job status in monitor database: {err}")
        return False


def remove_job_from_monitor_db(slurm_job_id: int) -> bool:
    # remove the job from the database
    try:
        jobs_coll = MONGODB_JOBS_COLLECTION
        result = jobs_coll.delete_one({"slurm_job_id": slurm_job_id})
        if result.deleted_count == 0:
            return False
        return True
    except pymongo.errors.PyMongoError as err:
        print(f" * Error removing job from monitor database: {err}")
        return False


def get_current_slurm_job_metadata_by_id(slurm_job_id: int) -> dict:
    if not slurm_job_id:
        return None
    # test case
    if slurm_job_id == SLURM_TEST_JOB_ID:
        return SLURM_TEST_JOB_STATUS
    cmd = " ".join(
        [
            str(x)
            for x in [
                "sacct",
                "-j",
                slurm_job_id,
                "--format=JobID,Jobname%-128,state,User,partition,time,start,end,elapsed",
                "--noheader",
                "--parsable2",
            ]
        ]
    )
    SSH_CLIENT.connect(hostname=SSH_HOSTNAME, username=SSH_USERNAME, pkey=SSH_KEY)
    stdin, stdout, stderr = SSH_CLIENT.exec_command(cmd)
    job_status_str = stdout.read().decode("utf-8").strip()
    if not job_status_str:
        return None
    job_status_components = job_status_str.split("\n")[0].split("|")
    job_status_keys = [
        "job_id",
        "job_name",
        "state",
        "user",
        "partition",
        "time",
        "start",
        "end",
        "elapsed",
    ]
    job_status = dict(zip(job_status_keys, job_status_components))
    if job_status["state"] not in SLURM_STATUS_KEYS:
        job_status["state"] = "Unknown"
    return job_status


"""
Query the database for all jobs.
For each job, get the current status from SLURM.
If the job is not found in SLURM, remove it from the database.
If the job is found, compare the status in SLURM with the status in the database.
If the SLURM and monitor database statuses are different:
  1. If completed or terminated, send a message to notifications queue(s).
  2. Delete the job from the database, if complete. Else, update job status in the database.
If they are the same, do nothing.
"""

def poll_slurm_jobs() -> None:
    try:
        jobs_coll = MONGODB_JOBS_COLLECTION
        jobs = jobs_coll.find()
        for job in jobs:
            slurm_job_id = int(job["slurm_job_id"])
            monitordb_job_status = job["slurm_job_status"]
            slurm_job_status_metadata = get_current_slurm_job_metadata_by_id(
                slurm_job_id
            )
            current_slurm_job_status = slurm_job_status_metadata["state"]
            # print(f'poll: testing {slurm_job_id}')
            if not slurm_job_status_metadata:
                remove_job_from_monitor_db(slurm_job_id)
                continue
            if monitordb_job_status != current_slurm_job_status:
                new_slurm_job_status = (
                    current_slurm_job_status
                    if current_slurm_job_status in SLURM_STATUS_KEYS
                    else "Unknown"
                )
                if new_slurm_job_status in ["COMPLETED", "FAILED", "CANCELLED"]:
                    print(
                        f" * Job {slurm_job_id} status updated from {monitordb_job_status} to {new_slurm_job_status}"
                    )
                    send_status_update_to_notification_queue(
                        slurm_job_id, monitordb_job_status, new_slurm_job_status
                    )
                if new_slurm_job_status in ["COMPLETED"]:
                    print(
                        f" * Job {slurm_job_id} is completed. Removing from monitor database so that it is no longer tracked."
                    )
                    remove_job_from_monitor_db(slurm_job_id)
                else:
                    update_job_status_in_monitor_db(slurm_job_id, new_slurm_job_status)
    except pymongo.errors.PyMongoError as err:
        print(f" * Error polling SLURM jobs: {err}")


def send_status_update_to_notification_queue(
    slurm_job_id: int, old_slurm_job_status: str, new_slurm_job_status: str
) -> None:
    # send a message to the notification queue
    pass
    # this is a placeholder function


@task_monitoring.route("/slurm_job_id/<slurm_job_id>", methods=["GET"])
def get_by_slurm_job_id(slurm_job_id: str) -> Response:
    slurm_job_id = int(slurm_job_id)
    slurm_job_status_metadata = get_current_slurm_job_metadata_by_id(slurm_job_id)
    monitordb_job_metadata = get_job_metadata_from_monitor_db(slurm_job_id)
    if not slurm_job_status_metadata and not monitordb_job_metadata:
        return {"error": "Job information not found"}, 404
    slurm_job_status = (
        slurm_job_status_metadata["state"] if slurm_job_status_metadata else "Unknown"
    )
    response_data = {
        "slurm": {
            "job_id": slurm_job_id,
            "job_status": slurm_job_status,
        },
        "monitordb": {
            "md": monitordb_job_metadata,
        },
    }
    response = Response(
        stream_with_context(json.dumps(response_data)),
        status=200,
        mimetype="application/json",
    )
    return response


def get_slurm_jobs_metadata_by_status(slurm_job_status: str) -> dict:
    if not slurm_job_status:
        return None
    cmd = " ".join(
        [
            str(x)
            for x in [
                "sacct",
                "--state",
                slurm_job_status,
                "--format=JobID,Jobname%-128,state,User,partition,time,start,end,elapsed",
                "--noheader",
                "--parsable2",
            ]
        ]
    )
    SSH_CLIENT.connect(hostname=SSH_HOSTNAME, username=SSH_USERNAME, pkey=SSH_KEY)
    stdin, stdout, stderr = SSH_CLIENT.exec_command(cmd)
    job_status_strs = stdout.read().decode("utf-8").strip()
    if not job_status_strs:
        return None
    jobs_status = {"jobs": []}
    for job_status_str in job_status_strs.split("\n"):
        job_status_components = job_status_str.split("|")
        job_status_keys = [
            "job_id",
            "job_name",
            "state",
            "user",
            "partition",
            "time",
            "start",
            "end",
            "elapsed",
        ]
        job_status_instance = dict(zip(job_status_keys, job_status_components))
        if job_status_instance["state"] not in SLURM_STATUS_KEYS:
            job_status_instance["state"] = "Unknown"
        jobs_status["jobs"].append(job_status_instance)
    return jobs_status


@task_monitoring.route("/slurm_status/<slurm_status>", methods=["GET"])
def get_by_slurm_status(slurm_status: str) -> Response:
    if slurm_status not in SLURM_STATUS_KEYS:
        return {"error": "Invalid status key"}, 400
    # also query the database for jobs with the given status, for comparison
    jobs = get_slurm_jobs_metadata_by_status(slurm_status)
    response_data = jobs
    response = Response(
        stream_with_context(json.dumps(response_data)),
        status=200,
        mimetype="application/json",
    )
    return response


@task_monitoring.route("/slurm_job_id/<slurm_job_id>", methods=["DELETE"])
def delete(slurm_job_id: int) -> Response:
    # print(f'slurm_job_id={slurm_job_id}')
    # only delete the job from the SLURM scheduler if it was already in the database (i.e. submitted)
    # delete the job from the database
    # return the job object
    deleted_job = {}
    response = Response(
        stream_with_context(json.dumps(deleted_job)),
        status=200,
        mimetype="application/json",
    )
    return response
