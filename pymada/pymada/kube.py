import os
import urllib3
import time
from kubernetes import client, utils, config
from kubernetes.config import kube_config

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def run_master_server(config_path=None, num_retries=5):
    if config_path is None:
        cwd = os.getcwd()
        config_path = os.path.join(cwd, 'k3s_config.yaml')
    kube_config.load_kube_config(config_file=config_path)
    kube_client = client.ApiClient()

    try:
        base_dir = os.path.dirname(os.path.realpath(__file__))
        utils.create_from_yaml(kube_client, os.path.join(base_dir, 'kube_yaml', 'pymada_master.yaml'))
        utils.create_from_yaml(kube_client, os.path.join(base_dir, 'kube_yaml', 'pymada_master_service.yaml'))
        utils.create_from_yaml(kube_client, os.path.join(base_dir, 'kube_yaml', 'pymada_master_nodeport.yaml'))
    except utils.FailToCreateError as e:
        if num_retries > 0:
            time.sleep(5)
            return run_master_server(config_path, num_retries=num_retries-1)
        else:
            raise e

def autoretry_run(func, num_tries=0, *args, **kargs):
    try:
        pass
    except utils.FailToCreateError as e:
        if num_tries > 0:
            pass
        else:
            raise e


def create_deployment_object(config_path=None):
    if config_path is None:
        base_dir = os.getcwd()
        config_path = os.path.join(base_dir, 'k3s_config.yaml')
    kube_config.load_kube_config(config_file=config_path)

    container = client.V1Container(
        name="pymada-agent-container",
        image="docker.io/nhoss2/pymada_master",
        ports=[client.V1ContainerPort(container_port=80)])

    template = client.V1PodTemplateSpec(
        metadata=client.V1ObjectMeta(labels={"app": "pymada_agent"}),
        spec=client.V1PodSpec(containers=[container]))

    spec = client.ExtensionsV1beta1DeploymentSpec(
        replicas=1,
        template=template)

    deployment = client.ExtensionsV1beta1Deployment(
        api_version="extensions/v1beta1",
        kind="Deployment",
        metadata=client.V1ObjectMeta(name='testo'),
        spec=spec)

    return deployment

if __name__ == '__main__':
    run_master_server()


    '''
    deployment = create_deployment_object()

    extensions_v1beta1 = client.ExtensionsV1beta1Api()
    response = extensions_v1beta1.create_namespaced_deployment(body=deployment, namespace="default")
    print(response.status)
    '''
