import os
import json
import time
import shutil
import click
import requests
import yaml
from tabulate import tabulate

from .provision import (launch_all, terminate_all, AVAILABLE_PROVIDERS)
from .kube import (get_deployment_status,
                   delete_all_deployments, get_pod_list, get_pod_logs, get_node_list)
from .master_client import (read_provision_settings, request_master, add_runner, 
                            add_url, get_results, list_screenshots,
                            list_screenshots_by_task, download_screenshot,
                            get_url_tasks, list_agents)
from .run import load_pymada_settings, run_agent


@click.group()
def cli():
    pass

@cli.command()
@click.argument('provider_name')
@click.argument('directory', default='.', type=click.Path())
def init(provider_name, directory='.'):
    # TODO: add help text showing available providers
    if not os.path.exists(directory):
        os.mkdir(directory)

    if provider_name not in AVAILABLE_PROVIDERS:
        print('provider_name argument needs to be one of: ' + ', '.join(AVAILABLE_PROVIDERS))
        return

    file_dir = os.path.dirname(os.path.realpath(__file__))
    settings_template_path = os.path.join(file_dir, 'provider_yaml',
                                          provider_name + '_settings_template.yaml')
    write_path = os.path.join(directory, 'pymada_settings.yaml')

    if os.path.exists(write_path):
        print('error file already exists at ' + write_path)
        return

    print('writing settings at ' + write_path)
    shutil.copyfile(settings_template_path, write_path)


'''
requires: 
    - provision_data.json
    - cloud_api_auth.json
    - pymada_settings.yaml
'''
@cli.command()
@click.argument('num-agents', type=click.INT)
def launch(num_agents, config_path=None):
    if type(num_agents) is not int:
        print('error: agents argument needs to be a number. given input:', num_agents)
        return

    try:
        launch_all(num_agents)
        print('done!')
    except Exception as e:
        print('error: ' + str(e))


'''
requires: 
    - provision_data.json
    - cloud_api_auth.json
    - pymada_settings.yaml
'''
@cli.command()
def terminate(config_path=None):
    try:
        load_pymada_settings() # just to check if settings file is in cwd
    except FileNotFoundError:
        print('error: pymada_settings.yaml not found in current directory')
        return

    terminate_all()


'''
requires: 
    - provision_data.json
    - k3s_config.yaml
    - pymada_settings.yaml
'''
@cli.command()
@click.argument('agent-type')
@click.argument('runner', type=click.Path(dir_okay=False, exists=True, readable=True))
@click.argument('replicas', type=click.INT, default=1)
@click.option('--dependency-file', type=click.Path(dir_okay=False, exists=True, readable=True), default=None)
@click.option('--master-url', default=None)
@click.option('--no-kube-deploy', default=False, flag_value=True)
@click.option('--no-token-auth', default=False, flag_value=True)
@click.option('--pymada-settings-path', default=None)
@click.option('--kube-config-path', default=None)
@click.option('--provision-data-path', default=None)
def run(agent_type, runner, replicas=1, dependency_file=None, master_url=None,
        no_kube_deploy=False, no_token_auth=False, pymada_settings_path=None,
        kube_config_path=None, provision_data_path=None):

    agent_types = {
        'puppeteer': 'node_puppeteer',
        'selenium_firefox': 'python_selenium_firefox',
        'selenium_chrome': 'python_selenium_chrome'
    }

    if agent_type not in agent_types:
        print('error, runner type needs to be one of: ' + ', '.join(list(agent_types)))
        return

    run_agent(agent_types[agent_type], runner,
              replicas=replicas, requirementsfile=dependency_file,
              master_url=master_url, no_kube_deploy=no_kube_deploy,
              no_token_auth=no_token_auth, pymada_settings_path=pymada_settings_path,
              kube_config_path=kube_config_path, provision_settings_path=provision_data_path)

'''
requires:
    - provision_data.json
'''
@cli.command()
@click.argument('url')
@click.option('--json-metadata', default=None)
@click.option('--master-url', default=None)
def add_url_task(url, json_metadata=None, master_url=None):
    if type(json_metadata) not in [type(None), dict]:
        print('error: json_metadata is not in json format.')

    add_url(url, json_metadata, master_url=master_url)


'''
requires:
    - provision_data.json
'''
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
            + str(stats['urls_complete']) + ', failed at least once: '
            + str(stats['urls_failed_min_once']) + ')')
    print('Agents: ' + str(stats['registered_agents']))
    print('Errors Logged: ' + str(stats['errors_logged']))


'''
requires:
    - provision_data.json
'''
@cli.command()
@click.argument('output_path', type=click.Path())
def get_output(output_path):
    results = get_results()
    if results is not None:
        with open(output_path, 'w') as outputfile:
            outputfile.write(results)

@cli.group()
@click.option('--kube-config', default=None, type=click.File(),
              help='kube config file, defaults to "k3s_config.yaml"')
@click.pass_context
def kube(ctx, kube_config=None):
    ctx.ensure_object(dict)

    if kube_config is None:
        base_dir = os.getcwd()
        kube_config = os.path.join(base_dir, 'k3s_config.yaml')

    ctx.obj['kube_config'] = kube_config

'''
requires:
    - k3s_config.yaml
'''
@kube.command()
@click.pass_context
@click.option('--show-nodes', default=False, flag_value=True)
def pods(ctx, show_nodes=False):
    '''
    Show table of pods running on kubernetes
    '''
    kube_config = ctx.obj['kube_config']

    if not os.path.exists(kube_config):
        raise click.FileError(kube_config,
        'File doesn\'t exist. "k3s_config.yaml" either needs to be in your ' +
        'current working directory or you can specify a kube config file path with ' +
        '--kube-config')

    pod_list = get_pod_list(config_path=kube_config)

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

'''
requires:
    - k3s_config.yaml
'''
@kube.command()
@click.pass_context
@click.argument('pod_name')
def logs(ctx, pod_name):
    '''
    Show logs for POD_NAME
    '''
    kube_config = ctx.obj['kube_config']
    if not os.path.exists(kube_config):
        raise click.FileError(kube_config,
        'File doesn\'t exist. "k3s_config.yaml" either needs to be in your ' +
        'current working directory or you can specify a kube config file path with ' +
        '--kube-config')

    pod_names = [p['name'] for p in get_pod_list(config_path=kube_config)]

    if pod_name not in pod_names:
        click.echo('error: pod name not found')
        return

    print(get_pod_logs(pod_name))

'''
requires:
    - k3s_config.yaml
'''
@kube.command()
@click.pass_context
def delete_deployments(ctx):
    '''
    Delete the master and all agent deployments
    '''
    kube_config = ctx.obj['kube_config']
    if not os.path.exists(kube_config):
        raise click.FileError(kube_config,
        'File doesn\'t exist. "k3s_config.yaml" either needs to be in your ' +
        'current working directory or you can specify a kube config file path with ' +
        '--kube-config')

    delete_all_deployments(config_path=kube_config)

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

'''
requires:
    - k3s_config.yaml
'''
@kube.command()
@click.pass_context
def nodes(ctx):
    '''
    List all nodes and pymada images on each node
    '''
    kube_config = ctx.obj['kube_config']
    if not os.path.exists(kube_config):
        raise click.FileError(kube_config,
        'File doesn\'t exist. "k3s_config.yaml" either needs to be in your ' +
        'current working directory or you can specify a kube config file path with ' +
        '--kube-config')

    node_list = get_node_list()
    table = []

    header = ['node name', 'images']

    for node in node_list:
        row = [node['name'], '\n'.join(node['images'])]
        table.append(row)

    print(tabulate(table, headers=header))


@cli.group()
def info():
    pass

'''
requires:
    - provision_data.json
'''
@info.command()
@click.argument('min_id', required=False, type=click.INT)
@click.argument('max_id', required=False, type=click.INT)
def screenshots(min_id=None, max_id=None):
    if min_id != None and max_id is None or min_id is None and max_id != None:
        print('both min id and max id is required')
        return

    if min_id != None and max_id != None:
        screenshot_data = list_screenshots(min_id=min_id, max_id=max_id)
    else:
        screenshot_data = list_screenshots()
    
    click.echo(json.dumps(screenshot_data, indent='  '))
    

'''
requires:
    - provision_data.json
'''
@info.command()
@click.argument('task_id', required=True, type=click.INT)
def task_screenshot(task_id):
    screenshot_data = list_screenshots_by_task(task_id)

    click.echo(json.dumps(screenshot_data, indent='  '))

'''
requires:
    - provision_data.json
'''
@info.command()
@click.argument('screenshot_id', required=True, type=click.INT)
@click.argument('output_dir', type=click.Path(), required=False)
def get_screenshot(screenshot_id, output_dir=None):
    screenshot_info = list_screenshots(min_id=screenshot_id, max_id=screenshot_id)

    if screenshot_info is None:
        click.echo('error getting screenshot data')
        return
    
    if len(screenshot_info) == 0:
        click.echo('error no screenshot with id: ' + str(screenshot_id) + ' found')
        return

    screenshot_name = screenshot_info[0]['screenshot']

    screenshot = download_screenshot(screenshot_id)

    if output_dir is None:
        output_path = os.path.join(os.getcwd(), screenshot_name)
    else:
        output_path = os.path.join(output_dir, screenshot_name)
    with open(output_path, 'wb') as sfile:
        sfile.write(screenshot)
    
    click.echo('written: ' + output_path)

'''
requires:
    - provision_data.json
'''
@info.command()
@click.argument('min_id', required=False, type=click.INT)
@click.argument('max_id', required=False, type=click.INT)
def tasks(min_id=None, max_id=None):
    if min_id != None and max_id is None or min_id is None and max_id != None:
        print('both min id and max id is required')
        return

    if min_id != None and max_id != None:
        url_tasks = get_url_tasks(min_id=min_id, max_id=max_id)
    else:
        print('showing first 20 url tasks')
        url_tasks = get_url_tasks(min_id=0, max_id=20)
    
    click.echo(json.dumps(url_tasks, indent='  '))

'''
requires:
    - provision_data.json
'''
@info.command()
@click.argument('min_id', required=False, type=click.INT)
@click.argument('max_id', required=False, type=click.INT)
def agents(min_id=None, max_id=None):
    # TODO: add check for 'provision_data.json'

    if min_id != None and max_id is None or min_id is None and max_id != None:
        print('both min id and max id is required')
        return

    if min_id != None and max_id != None:
        agents = list_agents(min_id=min_id, max_id=max_id)
    else:
        agents = list_agents()
    
    click.echo(json.dumps(agents, indent='  '))


if __name__ == '__main__':
    cli()