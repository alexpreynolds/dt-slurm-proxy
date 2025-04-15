import os
from flask import Flask
from apscheduler.schedulers.background import BackgroundScheduler

from task_submission import task_submission
from task_monitoring import task_monitoring, poll_slurm_jobs
from constants import (APP_PORT,
                       MONITOR_POLLING_INTERVAL,
                       )

app = Flask(__name__)
app.register_blueprint(task_submission, url_prefix='/submit')
app.register_blueprint(task_monitoring, url_prefix='/monitor')

scheduler = BackgroundScheduler()
poll_scheduler = scheduler.add_job(
  poll_slurm_jobs, 
  'interval', 
  minutes=int(os.environ.get("MONITOR_POLLING_INTERVAL", MONITOR_POLLING_INTERVAL))
  )
scheduler.start()

if __name__ == "__main__":
  port = int(os.environ.get("PORT", APP_PORT))
  app.run(
    debug=True, 
    threaded=True,
    host='0.0.0.0', 
    port=port
  )