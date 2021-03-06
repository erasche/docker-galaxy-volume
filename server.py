#!/usr/bin/env python
import json
import os
import uuid
from flask import Flask
from flask import jsonify
from flask import request
from functools import wraps


app = Flask(__name__)
VOLUMES = {}


def error(msg):
    return jsonify({
        'Err': msg
    })


def post_data(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        # Docker doesn't send a proper content-type header, so we can't use `.json`.
        body = request.data.decode('utf-8')
        req = json.loads(body)
        kwargs.update(req)
        return f(*args, **kwargs)
    return wrapped


def require_volume(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        req = json.loads(request.data.decode('utf-8'))

        volume_name = req['Name']
        if volume_name not in VOLUMES:
            return error("Unknown volume")

        kwargs['volume'] = VOLUMES[volume_name]

        return f(*args, **kwargs)
    return wrapped


@app.route('/Plugin.Activate', methods=['GET', 'POST'])
def plugin_activate():
    return jsonify({
        'Implements': ['VolumeDriver']
    })


@app.route('/VolumeDriver.Create', methods=['GET', 'POST'])
@post_data
def volume_create(Name=None, Opts=None):
    if 'apikey' not in Opts:
        return error('missing apikey')

    if 'url' not in Opts:
        return error('missing url')

    VOLUMES[Name] = {
        'name': Name,
        'apikey': Opts['apikey'],
        'human_readable': Opts.get('human_readable', False),
        'url': Opts['url'],
    }

    return jsonify({
        'Err': ''
    })


@app.route('/VolumeDriver.Remove', methods=['POST'])
@post_data
@require_volume
def volume_remove(volume=None, **kwargs):

    try:
        os.rmdir(volume['mountpoint'])
    except Exception:
        pass

    del VOLUMES[volume['name']]

    return jsonify({
        'Err': ''
    })


@app.route('/VolumeDriver.Mount', methods=['GET', 'POST'])
@post_data
@require_volume
def volume_mount(volume=None, **kwargs):
    if 'mountpoint' not in volume:
        print('qq', volume)
        # Create a directory to mount it at.
        m = os.path.join('/tmp', uuid.uuid4().hex)
        cmd = ['python', 'galaxy-fuse.py', volume['url'], volume['apikey'], '-m', m]

        if volume.get('human_readable', False):
            cmd.append('--human')

        # > The “l” variants are perhaps the easiest to work with if the number of parameters is fixed
        # > include a second “p” near the end ... will use the PATH environment variable
        os.makedirs(m)
        pid = os.spawnlp(os.P_NOWAIT, 'python', *cmd)
        # pid = os.spawnlp(os.P_NOWAIT, 'python', 'python', 'memory.py', m)
        # TODO(hxr): store pid
        print(pid)
        # And path is stored
        volume['mountpoint'] = m

    mountpoint = volume['mountpoint']

    return jsonify({
        'Err': '',
        'Mountpoint': mountpoint,
    })


@app.route('/VolumeDriver.Path', methods=['GET', 'POST'])
@post_data
def volume_path(Name=None):
    return volume_mount(Name=Name)


@app.route('/VolumeDriver.Unmount', methods=['GET', 'POST'])
@require_volume
def volume_unmount(volume=None):
    # TODO: kill subprocess
    return jsonify({
        'Err': '',
    })


@app.route('/VolumeDriver.Get', methods=['GET', 'POST'])
@require_volume
def volume_get(volume=None):
    volinfo = {
        'Name': volume['name'],
        'Status': {}
    }
    if 'mountpoint' in volume:
        volinfo['Mountpoint'] = volume['mountpoint']

    return jsonify({
        'Volume': volinfo,
        'Err': ''
    })


@app.route('/VolumeDriver.List', methods=['POST'])
def volume_list():
    return jsonify({
        'Volumes': [
            {'Name': k, 'Mountpoint': v.get('mountpoint', '')}
            for k, v
            in VOLUMES.items()
        ],
        'Err': ''
    })


@app.route('/VolumeDriver.Capabilities', methods=['POST'])
def volume_caps():
    return jsonify({
        'Capabilities': {
            'Scope': 'global',
        }
    })


@app.route('/status', methods=['GET'])
def status():
    return jsonify(VOLUMES)


if __name__ == '__main__':
    app.run(port=8123)
