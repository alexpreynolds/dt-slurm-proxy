import sys
import pika
import unittest
from pathlib import Path

file = Path(__file__).resolve()
parent, root = file.parent, file.parents[1]
sys.path.append(str(root))

from constants import (
    RABBITMQ_HOST,
    RABBITMQ_PORT,
    RABBITMQ_USERNAME,
    RABBITMQ_PASSWORD,
    RABBITMQ_PATH,
)

class TestGetSlurmJobCompletionMessaging(unittest.TestCase):
    def test_rabbitmq_connection(self):
        # Setup RabbitMQ connection parameters
        rq_credentials = pika.PlainCredentials(RABBITMQ_USERNAME, RABBITMQ_PASSWORD)
        rq_connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                RABBITMQ_HOST,
                RABBITMQ_PORT,
                RABBITMQ_PATH,
                rq_credentials
            )
        )
        rq_channel = rq_connection.channel()

        # Publish a message
        rq_channel.basic_publish(exchange="", routing_key="hello", body="Hello World!")

        # Close the connection
        rq_connection.close()


if __name__ == "__main__":
    unittest.main()
