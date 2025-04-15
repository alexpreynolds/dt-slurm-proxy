import os
from flask import Flask
from task_submission import task_submission
from task_monitoring import task_monitoring
from constants import APP_PORT

app = Flask(__name__)
app.register_blueprint(task_submission, url_prefix='/submit')
app.register_blueprint(task_monitoring, url_prefix='/monitor')

if __name__ == "__main__":
  port = int(os.environ.get("PORT", APP_PORT))
  app.run(
    debug=True, 
    threaded=True,
    host='0.0.0.0', 
    port=port
  )