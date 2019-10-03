import os
import json
import time
import shutil
import click
import requests
from tabulate import tabulate

from .provision import ProvisionGoogle
from .kube import (run_master_server, run_agent_deployment, get_deployment_status,
                   delete_all_deployments, get_pod_list, get_pod_logs)
from .master_client import read_provision_settings, request_master, add_runner, add_url

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

@click.group()
def cli():
    pass

@cli.command()
@click.argument('directory', default='.')
def init(directory='.'):
    if not os.path.exists(directory):
        os.mkdir(directory)

    file_dir = os.path.dirname(os.path.realpath(__file__))
    settings_template_path = os.path.join(file_dir, 'settings_template.yaml')
    write_path = os.path.join(directory, 'pymada_settings.yaml')

    print('writing settings at ' + write_path)
    shutil.copyfile(settings_template_path, write_path)


@cli.command()
@click.argument('num-agents', type=click.INT)
@click.option('-p', '--provider', default='gc')
@click.option('--preempt-agents/--no-preempt-agents', default=True)
@click.option('--preempt-master/--no-preempt-master', default=True)
#@click.option('--no-token-auth', default=False, flag_value=True)
def launch(num_agents, provider, preempt_agents=True, preempt_master=True, no_token_auth=False,
           config_path=None):

    if type(num_agents) is not int:
        print('error: agents argument needs to be a number. given input:', num_agents)
        return
    
    gc = ProvisionGoogle()
    gc.create_master(preemptible=preempt_master)
    gc.create_agent(num_agents, preemptible=preempt_agents)
    print('waiting for kubernetes installation on master')
    config = gc.get_k3s_config()
    if config == "kube conf doesnt exist":
        raise Exception("There has been an error with installing kubernetes")

    if config_path is None:
        config_path = os.path.join(os.getcwd(), 'k3s_config.yaml')
    gc.write_modify_k3s_config(config, write_path=config_path)

    print('done!')

@cli.command()
@click.argument('runner', type=click.Path(dir_okay=False, exists=True, readable=True))
@click.argument('replicas', type=click.INT, default=1)
@click.option('--packagejson', type=click.Path(dir_okay=False, exists=True, readable=True), default=None)
@click.option('--master-url', default=None)
@click.option('--no-kube-deploy', default=False, flag_value=True)
@click.option('--no-token-auth', default=False, flag_value=True)
def run_node_puppeteer(runner, replicas=1, packagejson=None, master_url=None,
                        no_kube_deploy=False, no_token_auth=False, config_path=None):
    

    #todo: show error message if deployment already exists

    if not no_kube_deploy:
        print('deploying master api server on kubernetes')

        if config_path is None:
            config_path = os.path.join(os.getcwd(), 'k3s_config.yaml')

        if no_token_auth:
            run_master_server(config_path)
        else:
            provision_settings = read_provision_settings()
            run_master_server(config_path, auth_token=provision_settings['pymada_auth_token'])

        # wait for master api server deployment on kubernetes
        while True:
            dep_status = get_deployment_status('app=pymada-master')
            num_avail = dep_status['items'][0]['status']['available_replicas']
            if num_avail == 1:
                break

            time.sleep(2)

    add_runner(runner, 'node_puppeteer', packagejson, master_url=master_url)

    if not no_kube_deploy:
        if no_token_auth:
            run_agent_deployment('nhoss2/pymada-node-puppeteer', replicas)
        else:
            print('deploying agents on kubernetes')
            provision_settings = read_provision_settings()
            run_agent_deployment('nhoss2/pymada-node-puppeteer', replicas,
                                 auth_token=provision_settings['pymada_auth_token'],
                                 config_path=config_path)


@cli.command()
@click.argument('url')
@click.option('--json-metadata', default=None)
@click.option('--master-url', default=None)
def add_url_task(url, json_metadata=None, master_url=None):
    if type(json_metadata) not in [type(None), dict]:
        print('error: json_metadata is not in json format.')

    add_url(url, json_metadata, master_url=master_url)


@cli.command()
@click.option('--master-url', default=None)
def stats(master_url=None):
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


@cli.group()
#@click.options()
def kube():
    pass

@kube.command()
@click.option('--show-nodes', default=False, flag_value=True)
def list_pods(show_nodes=False):
    pod_list = get_pod_list()

    table = []
    header = ['Name', 'Status', 'Restarts', 'Age']
    for pod in pod_list:
        row = []
        row.append(pod['name'])

        if pod['deletion_timestamp'] is not None:
            row.append('Terminating')
        else:
            row.append(pod['status'])
        
        row.append(pod['restart_count'])

        row.append(str(pod['age']).split('.')[0])

        if show_nodes:
            row.append(pod['node_name'])
            header.append('Node Name')
        
        table.append(row)

    print(tabulate(table, headers=header))

@kube.command()
@click.argument('pod_name')
def get_logs(pod_name):
    pod_names = [p['name'] for p in get_pod_list()]

    if pod_name not in pod_names:
        click.echo('error: pod name not found')
        return

    print(get_pod_logs(pod_name))

@kube.command()
def delete_deployments():
    delete_all_deployments()

    print('waiting for deployments to terminate')

    while True:
        dep_status = get_deployment_status('app=pymada-master')
        items = len(dep_status['items'])
        if items == 0:
            break

        time.sleep(2)

    while True:
        dep_status = get_deployment_status('app=pymada-agent')
        items = len(dep_status['items'])
        if items == 0:
            break

        time.sleep(2)

    print('deleted')


if __name__ == '__main__':
    cli()
