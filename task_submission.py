import os
import paramiko
from task_monitoring import monitor_job
from flask import Blueprint, request, Response, json, stream_with_context
from constants import SSH_USERNAME, SSH_HOSTNAME, SSH_PRIVATE_KEY_PATH, TASK_DESCRIPTION, BAD_SLURM_JOB_ID

SSH_CLIENT = None

'''
This module defines a Flask blueprint for task submission. 

The task is submitted via a POST request containing a JSON object with
information about the task to be submitted, including directories for input,
output, and error files, as well as SLURM parameters and the task name and
its parameters.

No other HTTP methods are supported at this time.
'''
task_submission = Blueprint('task_submission', __name__)
@task_submission.route('/', methods=['POST'])
def post() -> Response:
  request_info = request.get_json(force=True)
  task = request_info.get('task')
  if not task:
    return Response(
      stream_with_context(json.dumps({"Error": "No task provided"})),
      status=400,
      mimetype='application/json'
    )
  if not is_task_valid(task):
    return Response(
      stream_with_context(json.dumps({"Error": "Invalid task"})),
      status=400,
      mimetype='application/json'
    )
  submit_job_id = submit_slurm_task(task)
  if submit_job_id == BAD_SLURM_JOB_ID:
    return Response(
      stream_with_context(json.dumps({"Error": "Failed to submit task"})),
      status=400,
      mimetype='application/json'
    )
  # if successful, submit job metadata to the monitor service
  job = {
    'slurm_job_id': submit_job_id,
    'slurm_job_status': 'Unknown',
    'task': task
  }
  response = None
  if monitor_job(job):
    # return the task dictionary back to the client
    response = Response(
      stream_with_context(json.dumps(task)),
      status=200,
      mimetype='application/json'
    )
  else:
    response = Response(
      stream_with_context(json.dumps({"Error": "Failed to monitor job"})),
      status=400,
      mimetype='application/json'
    )
  return response

'''
This function takes a task dictionary and constructs a command to submit
the task to a SLURM scheduler. It first creates the necessary directories for
input, output, and error files. Then it constructs the SLURM command using
the parameters provided in the task dictionary. Finally, it sends the command
to the SLURM scheduler using SSH.
'''
def submit_slurm_task(task: dict) -> int:
  cmd = define_sbatch_cmd_for_task(task)
  job_id = send_sbatch_cmd(cmd) if cmd else BAD_SLURM_JOB_ID
  return job_id

def define_sbatch_cmd_for_task(task: dict) -> str:
  cmd_comps = []
  # construct the command to create the directories holding the input, output, and error files
  dir_comps = task['dirs']
  dir_cmd_comps = []
  dir_cmd_comps.append(f'mkdir -p {dir_comps["input"]}')
  dir_cmd_comps.append(f'mkdir -p {dir_comps["output"]}')
  dir_cmd_comps.append(f'mkdir -p {dir_comps["error"]}')
  dir_cmd = ' ; '.join(dir_cmd_comps)
  cmd_comps.append(dir_cmd)
  # construct the sbatch command
  slurm_comps = task['slurm']
  slurm_cmd_comps = []
  slurm_cmd_comps.append(f"sbatch")
  slurm_cmd_comps.append(f"--parsable")
  slurm_cmd_comps.append(f"--job-name={slurm_comps['job_name']}")
  slurm_cmd_comps.append(f"--output={os.path.join(dir_comps['output'], slurm_comps['output'])}")
  slurm_cmd_comps.append(f"--error={os.path.join(dir_comps['error'], slurm_comps['error'])}")
  slurm_cmd_comps.append(f"--nodes={slurm_comps['nodes']}")
  slurm_cmd_comps.append(f"--mem={slurm_comps['mem']}")
  slurm_cmd_comps.append(f"--cpus-per-task={slurm_comps['cpus_per_task']}")
  slurm_cmd_comps.append(f"--ntasks-per-node={slurm_comps['ntasks_per_node']}")
  slurm_cmd_comps.append(f"--partition={slurm_comps['partition']}")
  if slurm_comps['time']: slurm_cmd_comps.append(f"--time={slurm_comps['time']}")
  task_cmd = define_task_cmd(task['name'], task['params'])
  slurm_cmd_comps.append(f"--wrap=\'{task_cmd}\'")
  slurm_cmd = ' '.join(slurm_cmd_comps)
  cmd_comps.append(slurm_cmd)
  # construct the full list of commands
  cmd = ' ; '.join(cmd_comps)
  return cmd

def define_task_cmd(task_name: str, task_params: list) -> str:
  if task_name not in TASK_DESCRIPTION:
    raise ValueError(f"Task {task_name} is not defined")
  task_cmd = [TASK_DESCRIPTION[task_name]['cmd']]
  for param in task_params:
    task_cmd.append(param)
  task_cmd = ' '.join(task_cmd)
  return task_cmd

def send_sbatch_cmd(cmd: str) -> int:
  global SSH_CLIENT
  if not cmd:
    raise ValueError("Command cannot be empty")
  ssh_key = paramiko.Ed25519Key.from_private_key_file(SSH_PRIVATE_KEY_PATH)
  SSH_CLIENT = paramiko.SSHClient() if not SSH_CLIENT else SSH_CLIENT
  SSH_CLIENT.set_missing_host_key_policy(paramiko.AutoAddPolicy())
  SSH_CLIENT.connect(hostname=SSH_HOSTNAME, username=SSH_USERNAME, pkey=ssh_key)
  stdin, stdout, stderr = SSH_CLIENT.exec_command(cmd)
  try:
    # use of '--parsable' option in sbatch command means that 
    # the job id (integer) is the only thing sent to standard output
    job_id = int(stdout.read().decode('utf-8'))
    # if there is any output sent to standard error, log it as a failure
    stderr_val = stderr.read().decode('utf-8')
    if stderr_val:
      print(stderr_val)
      return BAD_SLURM_JOB_ID
  except ValueError as err:
    print(f"Error: {err}")
    return BAD_SLURM_JOB_ID
  return job_id

'''
This function checks if the task dictionary is valid by ensuring that
the required keys are present. The required keys are:

- 'name': The name of the task.
- 'params': The parameters for the task.
- 'uuid': A unique identifier for the task.
- 'slurm': A dictionary containing SLURM parameters.
- 'dirs': A dictionary containing directories for input, output, and error files.

The function returns True if all required keys are present, and False otherwise.
'''
def is_task_valid(task: dict) -> bool:
  return all([k in task for k in ['name', 'params', 'uuid', 'slurm', 'dirs']])