# Copyright 2013. Amazon Web Services, Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import sys
import json

from flask import Flask, request, Response, render_template

from boto import dynamodb2
from boto.dynamodb2.table import Table
from boto.dynamodb2.items import Item
from boto.dynamodb2.exceptions import ConditionalCheckFailedException
from boto import sns

# Create the Flask app
app = Flask(__name__)

# Load config values specified above
app.config.from_object(__name__)

# Load configuration values from a file
app.config.from_envvar('APP_CONFIG', silent=True)

# Only enable Flask debugging if an env var is set to true
app.debug = app.config['FLASK_DEBUG'].lower() in ['true', '1']

# Connect to DynamoDB and get ref to Table
ddb_conn = dynamodb2.connect_to_region(app.config['AWS_REGION'])
ddb_table = Table(table_name=app.config['STARTUP_SIGNUP_TABLE'],
                  connection=ddb_conn)

# Connect to SNS
sns_conn = sns.connect_to_region(app.config['AWS_REGION'])


class JsonResponse(Response):
    def __init__(body, status, *args, **kwargs):
        mime = 'application/json'
        base = super(JsonResponse)

        return base.__init__(body, status, mimetype=mime, *args, **kwargs)


@app.route('/')
def welcome():
    return render_template('index.html', theme=app.config['THEME'])


@app.route('/signup', methods=['POST'])
def signup():
    signup_data = dict()
    for item in request.form:
        signup_data[item] = request.form[item]

    try:
        store_in_dynamo(signup_data)
        publish_to_sns(signup_data)
    except ConditionalCheckFailedException:
        return JsonResponse("", status=409)

    return JsonResponse(json.dumps(signup_data), status=201)


def store_in_dynamo(signup_data):
    signup_item = Item(ddb_table, data=signup_data)
    signup_item.save()


def publish_to_sns(signup_data):
    topic = app.config['NEW_SIGNUP_TOPIC']
    json_data = json.dumps(signup_data)
    contents = "New signup: %s" % signup_data['email']
    error_msg = "Error publishing subscription message to SNS: %s"

    try:
        sns_conn.publish(topic, json_data, contents)
    except Exception as ex:
        sys.stderr.write(error_msg % ex.message)


if __name__ == '__main__':
    app.run(host='0.0.0.0')
