import pymongo
from flask import (
    Blueprint,
    request,
    Response,
)
from helpers import ssh_client, ssh_client_exec, stream_json_response
from constants import (
    SLURM_STATUS,
    SLURM_TEST_JOB_ID,
    SLURM_TEST_JOB_STATUS,
    MONGODB_JOBS_COLLECTION,
)

SSH_CLIENT = ssh_client()

SLURM_STATUS_KEYS = SLURM_STATUS.keys()

task_monitoring = Blueprint("task_monitoring", __name__)

"""
This module defines a Flask blueprint for task monitoring, which maintains job state via
a MongoDB database and communicates with a SLURM scheduler to generate updated job status.
"""


@task_monitoring.route("/", methods=["POST"])
def post() -> Response:
    """
    POST request to add a new job to the monitor database.
    The request body should contain a JSON object with the job information.
    """
    request_info = request.get_json(force=True)
    job = request_info.get("job")
    if not job:
        return {"error": "No job provided"}, 400
    response = None
    if monitor_new_slurm_job(job):
        response = stream_json_response(job, 200)
    else:
        response = stream_json_response({"Error": "Failed to monitor job"}, 400)
    return response


"""
CRUD operations for the job monitoring database.
"""


def monitor_new_slurm_job(job: dict) -> bool:
    """
    Monitor a new SLURM job by adding it to the database.
    The job dictionary should contain the SLURM job ID and task information.
    The SLURM job status is retrieved from the SLURM scheduler.

    Args:
        job (dict): A dictionary containing the SLURM job ID and task information.
    Returns:
        bool: True if the job was successfully monitored, False otherwise.
    """
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
    """
    Add a new job to the monitor database.
    The job dictionary should contain the SLURM job ID and task information.
    The SLURM job status is retrieved from the SLURM scheduler.

    Args:
        slurm_job_id (int): The SLURM job ID.
        slurm_job_status (str): The SLURM job status.
        slurm_job_task_metadata (dict): The task metadata for the job.

    Returns:
        bool: True if the job was successfully added to the monitor database, False otherwise.
    """
    job = {
        "slurm_job_id": slurm_job_id,
        "slurm_job_status": slurm_job_status,
        "task": slurm_job_task_metadata,
    }
    try:
        jobs_coll = MONGODB_JOBS_COLLECTION
        if not jobs_coll.find_one({"slurm_job_id": slurm_job_id}):
            jobs_coll.insert_one(job)
        return True
    except pymongo.errors.PyMongoError as err:
        print(f" * Error adding job to monitor database: {err}")
        return False


def get_job_metadata_from_monitor_db(slurm_job_id: int) -> dict:
    """
    Get job metadata from the monitor database using the SLURM job ID.

    Args:
        slurm_job_id (int): The SLURM job ID.

    Returns:
        dict: A dictionary containing the job metadata, or None if the job was not found.
    """
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
    """
    Update the job status in the monitor database.
    The job dictionary should contain the SLURM job ID and task information.
    The SLURM job status is retrieved from the SLURM scheduler.

    Args:
        slurm_job_id (int): The SLURM job ID.
        new_slurm_job_status (str): The new SLURM job status.

    Returns:
        bool: True if the job status was successfully updated, False otherwise.
    """
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
    """
    Remove a job from the monitor database using the SLURM job ID.

    Args:
        slurm_job_id (int): The SLURM job ID.

    Returns:
        bool: True if the job was successfully removed, False otherwise.
    """
    try:
        jobs_coll = MONGODB_JOBS_COLLECTION
        result = jobs_coll.delete_one({"slurm_job_id": slurm_job_id})
        if result.deleted_count == 0:
            return False
        return True
    except pymongo.errors.PyMongoError as err:
        print(f" * Error removing job from monitor database: {err}")
        return False


def remove_and_return_job_from_monitor_db(slurm_job_id: int) -> dict:
    """
    Remove a job from the monitor database and return the job metadata.

    Args:
        slurm_job_id (int): The SLURM job ID.

    Returns:
        dict: A dictionary containing the job metadata, or None if the job was not found.
    """
    try:
        jobs_coll = MONGODB_JOBS_COLLECTION
        result = jobs_coll.find_one_and_delete({"slurm_job_id": slurm_job_id})
        return result
    except pymongo.errors.PyMongoError as err:
        print(f" * Error removing job from monitor database: {err}")
        return None


def get_current_slurm_job_metadata_by_id(slurm_job_id: int) -> dict:
    """
    Get the current SLURM job metadata by job ID.

    Args:
        slurm_job_id (int): The SLURM job ID.

    Returns:
        dict: A dictionary containing the job metadata, or None if the job was not found.
    """
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
    (stdin, stdout, stderr) = ssh_client_exec(SSH_CLIENT, cmd)
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


def poll_slurm_jobs() -> None:
    """
    Poll the SLURM scheduler periodically for job status updates.
    This function checks the status of all jobs in the monitor database and updates
    the job status if there are any changes. If a job is completed, it is removed
    from the monitor database.
    """
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
                    send_status_update_to_notification_queue(
                        slurm_job_id, monitordb_job_status, new_slurm_job_status
                    )
                    remove_job_from_monitor_db(slurm_job_id)
                else:
                    update_job_status_in_monitor_db(slurm_job_id, new_slurm_job_status)
    except pymongo.errors.PyMongoError as err:
        print(f" * Error polling SLURM jobs: {err}")


def send_status_update_to_notification_queue(
    slurm_job_id: int, old_slurm_job_status: str, new_slurm_job_status: str
) -> None:
    """
    Send a message to the notification queue with the job status update.
    This function is a placeholder and should be implemented to send the message
    to the appropriate notification service.

    Args:
        slurm_job_id (int): The SLURM job ID.
        old_slurm_job_status (str): The old SLURM job status.
        new_slurm_job_status (str): The new SLURM job status.
    """
    pass


@task_monitoring.route("/slurm_job_id/<slurm_job_id>", methods=["GET"])
def get_job_metadata_by_slurm_job_id(slurm_job_id: str) -> Response:
    """
    GET request to retrieve job metadata from the monitor database using the SLURM job ID.
    The job ID is passed as a URL parameter.

    Args:
        slurm_job_id (str): The SLURM job ID.

    Returns:
        Response: A Flask Response object containing the job metadata in JSON format.
    """
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
    response = stream_json_response(response_data, 200)
    return response


def get_slurm_jobs_metadata_by_status(slurm_job_status: str) -> dict:
    """
    Get SLURM job metadata by job status.
    The job status is passed as a URL parameter.

    Args:
        slurm_job_status (str): The SLURM job status.

    Returns:
        dict: A dictionary containing the job metadata for the given status.
    """
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
    (stdin, stdout, stderr) = ssh_client_exec(SSH_CLIENT, cmd)
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
    """
    GET request to retrieve job metadata from the monitor database using the SLURM job status.
    The job status is passed as a URL parameter.

    Args:
        slurm_status (str): The SLURM job status.

    Returns:
        Response: A Flask Response object containing the job metadata in JSON format.
    """
    if slurm_status not in SLURM_STATUS_KEYS:
        return {"error": "Invalid status key"}, 400
    # also query the database for jobs with the given status, for comparison
    jobs = get_slurm_jobs_metadata_by_status(slurm_status)
    response = stream_json_response(jobs, 200)
    return response


@task_monitoring.route("/slurm_job_id/<slurm_job_id>", methods=["DELETE"])
def delete(slurm_job_id: int) -> Response:
    """
    DELETE request to remove a job from the monitor database using the SLURM job ID.
    The job ID is passed as a URL parameter.

    Args:
        slurm_job_id (int): The SLURM job ID.

    Returns:
        Response: A Flask Response object indicating the success or failure of the operation.
    """
    response = None
    # check if job was already in the monitor database
    slurm_job_id = int(slurm_job_id)
    job_metadata = get_job_metadata_from_monitor_db(slurm_job_id)
    if job_metadata:
        try:
            # delete the job from SLURM queue
            cmd = " ".join(
                [
                    str(x)
                    for x in [
                        "scancel",
                        str(slurm_job_id),
                    ]
                ]
            )
            (stdin, stdout, stderr) = ssh_client_exec(SSH_CLIENT, cmd)
            exit_code = stdout.channel.recv_exit_status()
            if exit_code != 0:
                response = stream_json_response(
                    {"error": "Job could not be deleted from SLURM scheduler"}, 400
                )
                return response
        except paramiko.SSHException as err:
            response = stream_json_response(
                {"error": f"Failed to delete job from SLURM: {err}"}, 500
            )
            return response
        except Exception as err:
            response = stream_json_response({"error": f"Unexpected error: {err}"}, 500)
            return response
    else:
        # job not found in the database
        response = stream_json_response(
            {"error": f"Job not found in monitor database"}, 404
        )
        return response
    # delete the job from the database
    deleted_job = remove_and_return_job_from_monitor_db(slurm_job_id)
    # return the job object
    response = stream_json_response(deleted_job, 200)
    return response
