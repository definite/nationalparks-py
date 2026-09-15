import json
import os
import re
from urllib.parse import quote_plus

from flask import Flask, jsonify, request
from pymongo import GEO2D, MongoClient

# MONGODB_SERVER_HOST, MONGODB_DATABASE, MONGODB_USER and MONGODB_PASSWORD are the
# variables the OpenShift workshop documents, and are shared with the Java, JS and
# .NET National Parks backends. The older DB_*/MONGODB_USERNAME names this backend
# used to require are still honoured so existing deployments keep working.
DB_HOST = (os.environ.get('MONGODB_SERVER_HOST') or os.environ.get('DB_HOST')
           or 'mongodb-nationalparks')
DB_PORT = (os.environ.get('MONGODB_SERVER_PORT') or os.environ.get('DB_PORT')
           or '27017')
DB_NAME = (os.environ.get('MONGODB_DATABASE') or os.environ.get('DB_NAME')
           or 'mongodb')
DB_USERNAME = (os.environ.get('MONGODB_USER') or os.environ.get('MONGODB_USERNAME')
               or 'mongodb')
DB_PASSWORD = (os.environ.get('MONGODB_PASSWORD') or os.environ.get('DB_PASSWORD')
               or 'mongodb')

DB_SERVICE_NAME = os.environ.get('DATABASE_SERVICE_NAME')

if os.environ.get('uri'):
    match = re.match(r'mongodb?:\/\/([^:^/]*):?(\d*)?', os.environ.get('uri'))

    if match:
        DB_HOST = match.group(1)

if DB_SERVICE_NAME:
    DB_HOST = DB_SERVICE_NAME

DB_URI = os.environ.get('DB_URI')

if not DB_URI:
    DB_URI = 'mongodb://%s:%s@%s:%s/%s' % (quote_plus(DB_USERNAME),
            quote_plus(DB_PASSWORD), DB_HOST, DB_PORT, DB_NAME)

DATASET_FILE = 'nationalparks.json'

application = Flask(__name__)

# One client per process, created on first use. MongoClient holds a connection
# pool and is not fork-safe, so it must not be built at import time: gunicorn
# forks its workers and each one needs its own.
_client = None


def get_collection():
    global _client

    if _client is None:
        _client = MongoClient(DB_URI)

    return _client[DB_NAME].nationalparks


@application.route('/ws/healthz/')
@application.route('/ws/healthz')
def healthcheck():
    return jsonify('OK')


@application.route('/ws/info/')
@application.route('/ws/info')
def info():
    return jsonify({
        'id': 'nationalparks-py',
        'displayName': 'National Parks (PY)',
        'type': 'cluster',
        'center': {'latitude': '47.039304', 'longitude': '14.505178'},
        'zoom': 4
    })


@application.route('/ws/data/load')
def data_load():
    collection = get_collection()

    collection.delete_many({})
    collection.create_index([('Location', GEO2D)])

    with open(DATASET_FILE, 'r') as fp:
        entries = []

        for data in fp.readlines():
            entry = json.loads(data)

            loc = [entry['coordinates'][1], entry['coordinates'][0]]
            entry['Location'] = loc

            entries.append(entry)

            if len(entries) >= 1000:
                collection.insert_many(entries)
                entries = []

        if entries:
            collection.insert_many(entries)

    return jsonify('Items inserted in database: %s'
                   % collection.estimated_document_count())


def format_result(entries):
    result = []

    for entry in entries:
        data = {}

        data['id'] = entry['name']
        data['latitude'] = str(entry['coordinates'][0])
        data['longitude'] = str(entry['coordinates'][1])
        data['name'] = entry['toponymName']

        result.append(data)

    return result


@application.route('/ws/data/all')
def data_all():
    return jsonify(format_result(get_collection().find()))


@application.route('/ws/data/within')
def data_within():
    args = request.args

    box = [[float(args['lon1']), float(args['lat1'])],
           [float(args['lon2']), float(args['lat2'])]]

    query = {'Location': {'$geoWithin': {'$box': box}}}

    return jsonify(format_result(get_collection().find(query)))


@application.route('/')
def index():
    return 'Welcome to the National Parks data service.'
