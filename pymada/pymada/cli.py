import os
import json
import time
import shutil
import click
import requests
import yaml
from tabulate import tabulate

from .provision import (ProvisionGoogleCloud, ProvisionDigitalOcean,
                        ProvisionAWS)
from .kube import (get_deployment_status,
                   delete_all_deployments, get_pod_list, get_pod_logs)
from .master_client import (read_provision_settings, request_master, add_runner, 
                            add_url, get_results, list_screenshots,
                            list_screenshots_by_task, download_screenshot,
                            get_url_tasks, list_agents)
from .run import run_puppeteer, load_pymada_settings


AVAILABLE_PROVIDERS = ['aws', 'digital_ocean', 'google_cloud']

@click.group()
def cli():
    pass

@cli.command()
@click.argument('provider_name')
@click.argument('directory', default='.', type=click.Path())
def init(provider_name, directory='.'):
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
@click.option('-p', '--provider', default='gc')
@click.option('--preempt-agents/--no-preempt-agents', default=True)
@click.option('--preempt-master/--no-preempt-master', default=True)
def launch(num_agents, provider, preempt_agents=True, preempt_master=True, config_path=None):

    if type(num_agents) is not int:
        print('error: agents argument needs to be a number. given input:', num_agents)
        return
    
    pymada_settings = load_pymada_settings()

    provider_name = pymada_settings['provision']['provider']['name']

    if provider_name in AVAILABLE_PROVIDERS:
        provider = load_provider(provider_name, pymada_settings)
    else:
        print('Error with provider name in pymada_settings.yaml. Needs to be one of: '
              + ', '.join(AVAILABLE_PROVIDERS))
        return
    
    provider.create_master(preemptible=preempt_master)
    provider.create_agent(num_agents, preemptible=preempt_agents)
    print('waiting for kubernetes installation on master')
    config = provider.get_k3s_config()

    if config == "kube conf doesnt exist":
        raise Exception("There has been an error with installing kubernetes")

    if config_path is None:
        config_path = os.path.join(os.getcwd(), 'k3s_config.yaml')
    
    provider.write_modify_k3s_config(config, write_path=config_path)

    print('done!')

'''
requires: 
    - provision_data.json
    - cloud_api_auth.json
'''
@cli.command()
def terminate(config_path=None):
    pymada_settings = load_pymada_settings()
    provider_name = pymada_settings['provision']['provider']['name']
    provider = load_provider(provider_name, pymada_settings)
    provider.delete_all()

@cli.group()
def run():
    pass
'''
requires: 
    - provision_data.json
    - k3s_config.yaml
    - pymada_settings.yaml
'''
@run.command()
@click.argument('runner', type=click.Path(dir_okay=False, exists=True, readable=True))
@click.argument('replicas', type=click.INT, default=1)
@click.option('--packagejson', type=click.Path(dir_okay=False, exists=True, readable=True), default=None)
@click.option('--master-url', default=None)
@click.option('--no-kube-deploy', default=False, flag_value=True)
@click.option('--no-token-auth', default=False, flag_value=True)
@click.option('--pymada-settings-path', default=None)
@click.option('--kube-config-path', default=None)
@click.option('--provision-data-path', default=None)
def puppeteer(runner, replicas=1, packagejson=None, master_url=None, no_kube_deploy=False,
              no_token_auth=False, pymada_settings_path=None, kube_config_path=None,
              provision_data_path=None):
    
    run_puppeteer(runner, replicas, packagejson, master_url, no_kube_deploy,
                 no_token_auth, pymada_settings_path, kube_config_path,
                 provision_data_path)

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
            + str(stats['urls_complete']) + ')')
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
    Delete the master api server deployment and all agent deployments
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
        url_tasks = get_url_tasks()
    
    click.echo(json.dumps(url_tasks, indent='  '))

'''
requires:
    - provision_data.json
'''
@info.command()
@click.argument('min_id', required=False, type=click.INT)
@click.argument('max_id', required=False, type=click.INT)
def agents(min_id=None, max_id=None):
    if min_id != None and max_id is None or min_id is None and max_id != None:
        print('both min id and max id is required')
        return

    if min_id != None and max_id != None:
        agents = list_agents(min_id=min_id, max_id=max_id)
    else:
        agents = list_agents()
    
    click.echo(json.dumps(agents, indent='  '))


def load_provider(provider_name, pymada_settings):
    if provider_name == 'aws':
        image_owner = None
        if 'image_owner' in pymada_settings['provision']['instance']:
            image_owner = pymada_settings['provision']['instance']['image_owner']

        keyname = None
        if 'keyname' in pymada_settings['provision']['instance']:
            keyname = pymada_settings['provision']['instance']['keyname']

        return ProvisionAWS(
            pymada_settings['provision']['provider']['access_id'],
            pymada_settings['provision']['provider']['secret_key'],
            pymada_settings['provision']['provider']['region'],
            pymada_settings['provision']['instance']['size'],
            pymada_settings['provision']['instance']['image'],
            pymada_settings['provision']['instance']['location'],
            pymada_settings['provision']['instance']['subnet'],
            keyname,
            image_owner
        )

    elif provider_name == 'google_cloud':
        node_location = None
        if 'location' in pymada_settings['provision']['instance']:
            node_location = pymada_settings['provision']['instance']['location']

        return ProvisionGoogleCloud(
            pymada_settings['provision']['provider']['user'],
            pymada_settings['provision']['provider']['auth_file'],
            pymada_settings['provision']['provider']['project'],
            pymada_settings['provision']['instance']['size'],
            pymada_settings['provision']['instance']['image'],
            node_location
        )

    elif provider_name == 'digital_ocean':
        node_location = None
        if 'location' in pymada_settings['provision']['instance']:
            node_location = pymada_settings['provision']['instance']['location']

        return ProvisionDigitalOcean(
            pymada_settings['provision']['provider']['token'],
            pymada_settings['provision']['instance']['size'],
            pymada_settings['provision']['instance']['image'],
            node_location
        )


if __name__ == '__main__':
    cli()