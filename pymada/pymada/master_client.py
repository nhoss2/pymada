import os
import json
import time
import requests

from .provision import ProvisionGoogle
from .kube import run_master_server, run_agent_deployment, get_deployment_status

def read_provision_settings(settings_path=None):
    if settings_path is None:
        dir_name = os.getcwd()
        settings_path = os.path.join(dir_name, 'provision_data.json')

    if not os.path.exists(settings_path):
        return None

    with open(settings_path) as provision_json:
        return json.load(provision_json)


def request_master(url, method, req_data, auth_token=None, master_url=None, _num_tries=0):
    provision_settings = read_provision_settings()

    if master_url is None:
        if provision_settings is None:
            raise FileNotFoundError('no provision_data.json file found')

        if 'master_node_ip' not in provision_settings:
            raise KeyError('master server ip address not in provision_data.json')
    
        master_url = 'http://' + provision_settings['master_node_ip'] + ':30200'
    

    if 'pymada_auth_token' in  provision_settings and auth_token is None:
        auth_token = provision_settings['pymada_auth_token']
    
    headers = {}

    if auth_token is not None:
        headers['pymada_token_auth'] = auth_token
    
    # todo: test request master with auth token and test with request failure

    try:
        response = requests.request(method, master_url + url, json=req_data, headers=headers)
    except (requests.ConnectionError, requests.Timeout) as e:
        if _num_tries < 10:
            time.sleep(3)
            return request_master(url, method, req_data, auth_token=auth_token,
                                    master_url=master_url, _num_tries=_num_tries+1)
        else:
            raise e
    
    return response

def add_runner(runner_path, file_type, dependency_file_path=None, master_url=None):
    full_runner_path = os.path.expanduser(runner_path)

    if not os.path.exists(full_runner_path):
        print('error: could not find runner file')
        return

    runner_data = {
        'contents': open(full_runner_path).read(),
        'file_name': os.path.basename(full_runner_path),
        'file_type': file_type
    }

    if dependency_file_path is not None:
        runner_data['dependency_file'] = open(dependency_file_path).read()

    response = request_master('/register_runner/', 'POST', runner_data,
        master_url=master_url)
    
    if response.ok:
        print('runner added')
    else:
        print(response.text)

def add_url(url, json_metadata=None, master_url=None):

    if type(json_metadata) is dict:
        json_metadata = json.dumps(json_metadata)

    new_url_data = {
        'url': url,
        'json_metadata': json_metadata
    }

    response = request_master('/urls/', 'POST', new_url_data, master_url=master_url)

    if response.ok:
        print('url added')
    else:
        print(response.text)

