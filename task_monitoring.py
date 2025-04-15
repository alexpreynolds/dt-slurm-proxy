import paramiko
from flask import Blueprint, request, Response, json, stream_with_context
from constants import SSH_USERNAME, SSH_HOSTNAME, SSH_PRIVATE_KEY_PATH, SLURM_STATUS, SLURM_TEST_JOB_ID, SLURM_TEST_JOB_STATUS

SSH_CLIENT = None
SLURM_STATUS_KEYS = SLURM_STATUS.keys()

'''
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
'''
task_monitoring = Blueprint('task_monitoring', __name__)
@task_monitoring.route('/', methods=['POST'])
def post() -> Response:
  request_info = request.get_json(force=True)
  job = request_info.get('job')
  if not job:
    return {"error": "No job provided"}, 400
  response = None
  if monitor_job(job):
    response = Response(
      stream_with_context(json.dumps(job)),
      status=200,
      mimetype='application/json'
    )
  else:
    response = Response(
      stream_with_context({"Error": "Failed to monitor job"}),
      status=400,
      mimetype='application/json'
    )
  return response

def monitor_job(job: dict) -> bool:
  slurm_job_id = job['slurm_job_id']
  slurm_job_status_metadata = get_slurm_job_metadata_by_id(slurm_job_id) # replace with SLURM query
  if not slurm_job_status_metadata:
    return False
  slurm_job_status = slurm_job_status_metadata['state'] if slurm_job_status_metadata else 'Unknown'
  slurm_job_task_metadata = job['task']
  # update the monitor database with the job information
  return True

def get_slurm_job_metadata_by_id(slurm_job_id: int) -> dict:
  global SSH_CLIENT
  if not slurm_job_id:
    return None
  # test case
  if slurm_job_id == SLURM_TEST_JOB_ID:
    return SLURM_TEST_JOB_STATUS
  ssh_key = paramiko.Ed25519Key.from_private_key_file(SSH_PRIVATE_KEY_PATH)
  SSH_CLIENT = paramiko.SSHClient() if not SSH_CLIENT else SSH_CLIENT
  SSH_CLIENT.set_missing_host_key_policy(paramiko.AutoAddPolicy())
  SSH_CLIENT.connect(hostname=SSH_HOSTNAME, username=SSH_USERNAME, pkey=ssh_key)
  cmd = ' '.join([str(x) for x in ["sacct", "-j", slurm_job_id, "--format=JobID,Jobname%-128,state,User,partition,time,start,end,elapsed", "--noheader", "--parsable2"]])
  stdin, stdout, stderr = SSH_CLIENT.exec_command(cmd)
  job_status_str = stdout.read().decode('utf-8').strip()
  if not job_status_str:
    return None
  job_status_components = job_status_str.split('\n')[0].split('|')
  job_status_keys = ['job_id', 'job_name', 'state', 'user', 'partition', 'time', 'start', 'end', 'elapsed']
  job_status = dict(zip(job_status_keys, job_status_components))
  if job_status['state'] not in SLURM_STATUS_KEYS:
    job_status['state'] = 'Unknown'
  return job_status

def get_monitordb_job_metadata_by_id(slurm_job_id: int) -> dict:
  # query the database for the job with the given slurm_job_id
  # return the job status metadata
  return {} # replace with actual database query

@task_monitoring.route('/slurm_job_id/<slurm_job_id>', methods=['GET'])
def get_by_slurm_job_id(slurm_job_id: int) -> Response:
  slurm_job_status_metadata = get_slurm_job_metadata_by_id(slurm_job_id)
  monitordb_job_metadata = get_monitordb_job_metadata_by_id(slurm_job_id)
  if not slurm_job_status_metadata and not monitordb_job_metadata:
    return {"error": "Job not found"}, 404
  slurm_job_status = slurm_job_status_metadata['state'] if slurm_job_status_metadata else 'Unknown'
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
    mimetype='application/json'
  )
  return response

def get_slurm_jobs_metadata_by_status(slurm_job_status: str) -> dict:
  global SSH_CLIENT
  if not slurm_job_status:
    return None
  ssh_key = paramiko.Ed25519Key.from_private_key_file(SSH_PRIVATE_KEY_PATH)
  SSH_CLIENT = paramiko.SSHClient() if not SSH_CLIENT else SSH_CLIENT
  SSH_CLIENT.set_missing_host_key_policy(paramiko.AutoAddPolicy())
  SSH_CLIENT.connect(hostname=SSH_HOSTNAME, username=SSH_USERNAME, pkey=ssh_key)
  cmd = ' '.join([str(x) for x in ["sacct", "--state", slurm_job_status, "--format=JobID,Jobname%-128,state,User,partition,time,start,end,elapsed", "--noheader", "--parsable2"]])
  stdin, stdout, stderr = SSH_CLIENT.exec_command(cmd)
  job_status_strs = stdout.read().decode('utf-8').strip()
  if not job_status_strs:
    return None
  jobs_status = { "jobs": [] }
  for job_status_str in job_status_strs.split('\n'):
    job_status_components = job_status_str.split('|')
    job_status_keys = ['job_id', 'job_name', 'state', 'user', 'partition', 'time', 'start', 'end', 'elapsed']
    job_status_instance = dict(zip(job_status_keys, job_status_components))
    if job_status_instance['state'] not in SLURM_STATUS_KEYS:
      job_status_instance['state'] = 'Unknown'
    jobs_status['jobs'].append(job_status_instance)
  return jobs_status

@task_monitoring.route('/slurm_status/<slurm_status>', methods=['GET'])
def get_by_slurm_status(slurm_status: str) -> Response:
  if slurm_status not in SLURM_STATUS_KEYS:
    return {"error": "Invalid status key"}, 400
  # also query the database for jobs with the given status, for comparison
  jobs = get_slurm_jobs_metadata_by_status(slurm_status)
  response_data = jobs
  response = Response(
    stream_with_context(json.dumps(response_data)),
    status=200,
    mimetype='application/json'
  )
  return response

@task_monitoring.route('/slurm_job_id/<slurm_job_id>', methods=['DELETE'])
def delete(slurm_job_id: int) -> Response:
  print(f'slurm_job_id={slurm_job_id}')
  # only delete the job from the SLURM scheduler if it was already in the database (i.e. submitted)
  # delete the job from the database
  # return the job object
  deleted_job = {}
  response = Response(
    stream_with_context(json.dumps(deleted_job)),
    status=200,
    mimetype='application/json'
  )
  return response