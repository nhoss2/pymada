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


def run_agent_deployment(image, replicas, deploy_name='pymada-agent',
                             template_label={'app': 'pymada-agent'},
                             agent_port='5001', container_name='pymada-signle-agent',
                             config_path=None):

    container = client.V1Container(
        name=container_name,
        image=image,
        ports=[client.V1ContainerPort(container_port=5001)],
        env=[client.V1EnvVar("MASTER_URL", "http://pymadamaster:8000"),
             client.V1EnvVar("AGENT_PORT", agent_port),
             client.V1EnvVar("AGENT_ADDR", value_from=client.V1EnvVarSource(
                 field_ref=client.V1ObjectFieldSelector(field_path="status.podIP")))])

    template = client.V1PodTemplateSpec(
        metadata=client.V1ObjectMeta(labels=template_label),
        spec=client.V1PodSpec(containers=[container]))

    spec = client.ExtensionsV1beta1DeploymentSpec(
        replicas=replicas,
        template=template)

    deployment = client.ExtensionsV1beta1Deployment(
        api_version="extensions/v1beta1",
        kind="Deployment",
        metadata=client.V1ObjectMeta(name=deploy_name),
        spec=spec)

    if config_path is None:
        base_dir = os.getcwd()
        config_path = os.path.join(base_dir, 'k3s_config.yaml')
    kube_config.load_kube_config(config_file=config_path)
    extensions_v1beta1 = client.ExtensionsV1beta1Api()
    extensions_v1beta1.create_namespaced_deployment(body=deployment, namespace="default")


def get_deployment_status(label_selector=None, config_path=None):
    if config_path is None:
        base_dir = os.getcwd()
        config_path = os.path.join(base_dir, 'k3s_config.yaml')

    kube_config.load_kube_config(config_file=config_path)
    k_client = client.AppsV1beta1Api()
    api_response = k_client.list_namespaced_deployment('default', label_selector=label_selector)
    return api_response.to_dict()