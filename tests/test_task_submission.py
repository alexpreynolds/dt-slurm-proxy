import unittest
from flask import Flask

import sys
from pathlib import Path

file = Path(__file__).resolve()
parent, root = file.parent, file.parents[1]
sys.path.append(str(root))
from task_submission import task_submission

class TestTaskSubmission(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.register_blueprint(task_submission, url_prefix="/")
        self.client = self.app.test_client()

    def test_index_with_data(self):
        # Send a POST request with valid JSON data
        test_data = {
            "task": {
                "dirs": {
                    "error": "/home/areynolds/dt-slurm-proxy/error",
                    "input": "/home/areynolds/dt-slurm-proxy/input",
                    "output": "/home/areynolds/dt-slurm-proxy/output",
                },
                "slurm": {
                    "cpus_per_task": 1,
                    "error": "dt-slurm-proxy.hello_world.error.txt",
                    "job_name": "dt-slurm-proxy.hello_world",
                    "mem": "1G",
                    "nodes": 1,
                    "ntasks_per_node": 1,
                    "output": "dt-slurm-proxy.hello_world.output.txt",
                    "partition": "queue1",
                    "time": "00:30:00",
                },
                "name": "echo_hello_world",
                "params": [
                    "-e",
                    "\"Hello world!\t(sent to $USER)\n\"",
                ],
                "uuid": "123e4567-e89b-12d3-a456-426614174000",
            }
        }
        response = self.client.post("/", json=test_data)
        self.assertEqual(response.status_code, 200)
        # Response should mirror back the sent JSON task uuid
        self.assertEqual(response.get_json(), {"uuid": test_data["task"]["uuid"]})

    def test_index_without_data(self):
        # Send a POST request without any JSON data
        response = self.client.post("/")
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
