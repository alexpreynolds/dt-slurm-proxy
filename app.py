# -*- coding: utf-8 -*-

from flask import Flask
from apscheduler.schedulers.background import BackgroundScheduler

from task_submission import task_submission
from task_monitoring import task_monitoring, poll_slurm_jobs
from constants import (
    APP_NAME,
    APP_PORT,
    MONITOR_POLLING_INTERVAL,
)
from helpers import (
    init_mongodb,
)

app = Flask(APP_NAME)
app.register_blueprint(task_submission, url_prefix="/submit")
app.register_blueprint(task_monitoring, url_prefix="/monitor")

if __name__ == "__main__":
    init_mongodb()
    scheduler = BackgroundScheduler()
    poll_scheduler = scheduler.add_job(
        poll_slurm_jobs,
        "interval",
        minutes=int(MONITOR_POLLING_INTERVAL),
    )
    scheduler.start()
    port = int(APP_PORT)
    app.run(debug=True, threaded=True, host="0.0.0.0", port=port)
