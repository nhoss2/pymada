import time
import os
from pymada import master_client, kube

def run_puppeteer(runner, replicas=1, packagejson=None, master_url=None,
                        no_kube_deploy=False, no_token_auth=False, kube_config_path=None,
                        provision_settings_path=None):

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
            kube.run_master_server(kube_config_path)
        else:
            provision_settings = master_client.read_provision_settings(provision_settings_path)
            kube.run_master_server(kube_config_path, auth_token=provision_settings['pymada_auth_token'])

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
            kube.run_agent_deployment('nhoss2/pymada-node-puppeteer', replicas,
                                 config_path=kube_config_path)
        else:
            provision_settings = master_client.read_provision_settings(provision_settings_path)
            kube.run_agent_deployment('nhoss2/pymada-node-puppeteer', replicas,
                                 auth_token=provision_settings['pymada_auth_token'],
                                 config_path=kube_config_path)