#!/bin/bash

#
# Docker container script for launching MongoDB and Python Flask app
#

mongod --bind_ip 0.0.0.0 --fork --logpath /var/log/mongodb/mongod.log
python /app/app.py