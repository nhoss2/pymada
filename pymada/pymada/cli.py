import os
import json
import time
import fire
import requests

from .provision import ProvisionGoogle
from .kube import run_master_server, run_agent_deployment, get_deployment_status

'''
things to do:
    - create master instance
    - create agent instances
    - upload runner to master instance
    - add url to master instance

    - k3s stuff:
        - run master deployment
        - setup master service
        - connect to master server from this cli (maybe nodeport for now)
        - run agent deployments (depending on type of runner)
    
    - config required:
        - cloud provider
            - cloud provider auth file
            - instance types (optional?)
            - instance location (optional)
            - instance preemptible (optional)
            - docker image names and versions (optional)

    - commands:
        - launch (start instances, start k3s, start master server)
        - run-node-puppeteer (add js runner and deploy node-puppeteer pods)
        - run-selenium-chrome (add python runner and deploy selenium chrome pods)
        - run-selenium-firefox (add python runner and deploy selenium firefox pods)

        - stop run (stops all pods of a specific run)
        - terminate instances (terminates some or all instances)

        - add url (adds single url from command line)

        - view logs (of single pod through kubernetes api)

        - check status (see how many pods running, num urls completed/left)
            - how many pods running, individual pod stats?
            - num urls and num left

'''

def read_provision_settings(settings_path=None):
    if settings_path is None:
        dir_name = os.getcwd()
        settings_path = os.path.join(dir_name, 'provision_data.json')

    if not os.path.exists(settings_path):
        return None

    with open(settings_path) as provision_json:
        return json.load(provision_json)


def request_master(url, method, req_data, master_url=None, num_tries=0):
    provision_settings = read_provision_settings()

    if master_url is None:
        if provision_settings is None:
            raise FileNotFoundError('no provision_data.json file found')

        if 'master_node_ip' not in provision_settings:
            raise KeyError('master server ip address not in provision_data.json')
    
        master_url = 'http://' + provision_settings['master_node_ip'] + ':30200'

    try:
        response = requests.request(method, master_url + url, json=req_data)
    except (requests.ConnectionError, requests.Timeout) as e:
        if num_tries < 10:
            time.sleep(3)
            return request_master(url, method, req_data, master_url=master_url, num_tries=num_tries+1)
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

    new_url_data = {
        'url': url,
        'json_metadata': json_metadata
    }

    response = request_master('/urls/', 'POST', new_url_data, master_url=master_url)

    if response.ok:
        print('url added')
    else:
        print(response.text)


class CliClient(object):
    def launch(self, agents, provider='gc', preempt_agents=True, preempt_master=True):

        if type(agents) is not int:
            print('error: agents argument needs to be a number. given input:', agents)
            return
        
        gc = ProvisionGoogle()
        gc.create_master(preemptible=preempt_master)
        gc.create_agent(agents, preemptible=preempt_agents)
        print('waiting for kubernetes installation on master')
        config = gc.get_k3s_config()
        if config == "kube conf doesnt exist":
            raise Exception("There has been an error with installing kubernetes")

        config_path = os.path.join(os.getcwd(), 'k3s_config.yaml')
        gc.write_modify_k3s_config(config, write_path=config_path)
        print('deploying master api server on kubernetes')
        run_master_server(config_path)

        while True:
            dep_status = get_deployment_status('app=pymada-master')
            num_avail = dep_status['items'][0]['status']['available_replicas']
            if num_avail == 1:
                break

            time.sleep(2)
        

        print('done!')
    
    def run_node_puppeteer(self, runner, replicas=1, packagejson=None, master_url=None,
                           no_deploy=False):
        if type(replicas) is not int:
            print('error: replicas argument needs to be a number. given input:', replicas)
            return

        full_dep_path = None
        if packagejson is not None:
            full_dep_path = os.path.expanduser(packagejson)
            if not os.path.exists(full_dep_path):
                print('error: could not find package.json')
                return
        add_runner(runner, 'node_puppeteer', full_dep_path, master_url=master_url)

        if not no_deploy:
            run_agent_deployment('nhoss2/pymada-node-puppeteer', replicas)

    def add_url_task(self, url, json_metadata=None, master_url=None):
        if type(json_metadata) not in [type(None), dict]:
            print('error: json_metadata is not in json format.')

        add_url(url, json_metadata, master_url=master_url)
    

    def stats(self, master_url=None):
        try:
            stats = request_master('/stats/', 'GET', None, master_url=master_url)
        except (requests.ConnectionError, requests.Timeout):
            print('error connecting to master server')
            return
        
        stats = stats.json()
        print('URL Tasks: ' + str(stats['urls']) + ' (queued: ' + str(stats['urls_queued'])
              + ', assigned: ' + str(stats['urls_assigned']) + ', complete: '
              + str(stats['urls_complete']) + ')')
        print('Agents: ' + str(stats['registered_agents']))
        print('Errors Logged: ' + str(stats['errors_logged']))


def main():
    fire.Fire(CliClient)

if __name__ == '__main__':
    fire.Fire(CliClient)
