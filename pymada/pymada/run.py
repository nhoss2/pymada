import time
import os
import yaml
from pymada import master_client, kube

def load_pymada_settings(settings_path=None):
    if settings_path is not None:
        pymada_settings_path = settings_path
    else:
        base_path = os.getcwd()
        pymada_settings_path = os.path.join(base_path, 'pymada_settings.yaml')

    with open(pymada_settings_path) as settingsfile:
        pymada_settings = yaml.load(settingsfile.read(), Loader=yaml.FullLoader)

    return pymada_settings


'''
def run_puppeteer(runner, replicas=1, packagejson=None, master_url=None,
                        no_kube_deploy=False, no_token_auth=False, pymada_settings_path=None,
                        kube_config_path=None, provision_settings_path=None):

    pymada_settings = load_pymada_settings(pymada_settings_path)

    max_task_retries = None
    if 'max_task_retries' in pymada_settings['pymada']:
        max_task_retries = pymada_settings['pymada']['max_task_retries']

    max_task_duration = None
    if 'max_task_duration_seconds' in pymada_settings['pymada']:
        max_task_duration = pymada_settings['pymada']['max_task_duration_seconds']

    if not no_kube_deploy:
        if kube_config_path is None:
            kube_config_path = os.path.join(os.getcwd(), 'k3s_config.yaml')

        # check if master deployment already exists
        master_dep_status = kube.get_deployment_status('app=pymada-master')
        if len(master_dep_status['items']) != 0:
            print('error: master api server deployment already exists. ' +
                  'You can remove all current deployments with "pymada kube delete-deployments"')
            return

        print('deploying master api server on kubernetes')

        if no_token_auth:
            kube.run_master_deployment('nhoss2/pymada-master', config_path=kube_config_path,
                                       max_task_duration=max_task_duration,
                                       max_task_retries=max_task_retries)
        else:
            provision_settings = master_client.read_provision_settings(provision_settings_path)
            kube.run_master_deployment('nhoss2/pymada-master', config_path=kube_config_path,
                                       auth_token=provision_settings['pymada_auth_token'],
                                       max_task_duration=max_task_duration,
                                       max_task_retries=max_task_retries)

        # wait for master api server deployment on kubernetes
        while True:
            dep_status = kube.get_deployment_status('app=pymada-master')
            num_avail = dep_status['items'][0]['status']['available_replicas']
            if num_avail == 1:
                break

            time.sleep(2)

    master_client.add_runner(runner, 'node_puppeteer', packagejson, master_url=master_url)

    if not no_kube_deploy:
        print('deploying agents on kubernetes')
        if no_token_auth:
            kube.run_agent_deployment('puppeteer', replicas,
                                 config_path=kube_config_path)
        else:
            provision_settings = master_client.read_provision_settings(provision_settings_path)
            kube.run_agent_deployment('puppeteer', replicas,
                                 auth_token=provision_settings['pymada_auth_token'],
                                 config_path=kube_config_path)

'''

def run_master_kube(kube_config_path, pymada_settings_path, pymada_auth_token=None):
    pymada_settings = load_pymada_settings(pymada_settings_path)

    max_task_retries = None
    if 'max_task_retries' in pymada_settings['pymada']:
        max_task_retries = pymada_settings['pymada']['max_task_retries']

    max_task_duration = None
    if 'max_task_duration_seconds' in pymada_settings['pymada']:
        max_task_duration = pymada_settings['pymada']['max_task_duration_seconds']

    # check if master deployment already exists
    master_dep_status = kube.get_deployment_status('app=pymada-master')
    if len(master_dep_status['items']) != 0:
        print('error: master api server deployment already exists. ' +
                'You can remove all current deployments with "pymada kube delete-deployments"')
        return

    print('deploying master api server on kubernetes')

    if pymada_auth_token is None:
        kube.run_master_deployment(config_path=kube_config_path,
                                    max_task_duration=max_task_duration,
                                    max_task_retries=max_task_retries)
    else:
        kube.run_master_deployment(config_path=kube_config_path,
                                    auth_token=pymada_auth_token,
                                    max_task_duration=max_task_duration,
                                    max_task_retries=max_task_retries)

    # wait for master api server deployment on kubernetes
    while True:
        dep_status = kube.get_deployment_status('app=pymada-master')
        num_avail = dep_status['items'][0]['status']['available_replicas']
        if num_avail == 1:
            break

        time.sleep(2)


def run_agent(agent_type, runner, replicas=1, requirementsfile=None, master_url=None,
              no_kube_deploy=False, no_token_auth=False, pymada_settings_path=None,
              kube_config_path=None, provision_settings_path=None):
    '''
    current agent types: "node_puppeteer", "python_selenium_firefox", "python_selenium_chrome"
    '''
    if kube_config_path is None:
        kube_config_path = os.path.join(os.getcwd(), 'k3s_config.yaml')

    if provision_settings_path is None:
        provision_settings_path = os.path.join(os.getcwd(), 'provision_data.json')

    if pymada_settings_path is None:
        pymada_settings_path = os.path.join(os.getcwd(), 'pymada_settings.yaml')

    if not no_kube_deploy:
        if no_token_auth:
            run_master_kube(kube_config_path, pymada_settings_path, pymada_auth_token=None)
        else:
            provision_settings = master_client.read_provision_settings(provision_settings_path)
            auth_token = provision_settings['pymada_auth_token']
            run_master_kube(kube_config_path, pymada_settings_path, pymada_auth_token=auth_token)

    master_client.add_runner(runner, agent_type, requirementsfile, master_url=master_url)

    if not no_kube_deploy:
        print('deploying agents on kubernetes')
        if no_token_auth:
            kube.run_agent_deployment(agent_type, replicas, config_path=kube_config_path)
        else:
            provision_settings = master_client.read_provision_settings(provision_settings_path)
            kube.run_agent_deployment(agent_type, replicas,
                                 auth_token=provision_settings['pymada_auth_token'],
                                 config_path=kube_config_path)