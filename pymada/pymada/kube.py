import os
import urllib3
import time
import datetime
import yaml
from dateutil.tz import tzutc
from kubernetes import client, utils, config
from kubernetes.config import kube_config

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

'''
def run_master_server(config_path=None, auth_token=None, num_retries=5):
    if config_path is None:
        cwd = os.getcwd()
        config_path = os.path.join(cwd, 'k3s_config.yaml')

    kube_config.load_kube_config(config_file=config_path)
    kube_client = client.ApiClient()

    try:
        base_dir = os.path.dirname(os.path.realpath(__file__))

        master_api_yaml_path = os.path.join(base_dir, 'kube_yaml', 'pymada_master.yaml')
        master_yaml = setup_master_api_deployment(master_api_yaml_path, auth_token)
        temp_path = os.path.join(base_dir, 'kube_yaml', 'temp_pymada_master.yaml')
        with open(temp_path, 'w') as temp_file:
            temp_file.write(master_yaml)
        utils.create_from_yaml(kube_client, temp_path)

        if len(get_service_status('service=pymada-master-service').items) == 0:
            utils.create_from_yaml(kube_client, os.path.join(base_dir, 'kube_yaml', 'pymada_master_service.yaml'))

        if len(get_service_status('service=pymada-master-nodeport').items) == 0:
            utils.create_from_yaml(kube_client, os.path.join(base_dir, 'kube_yaml', 'pymada_master_nodeport.yaml'))
    except (utils.FailToCreateError, client.rest.ApiException) as e:
        if num_retries > 0:
            time.sleep(5)
            return run_master_server(config_path, auth_token=auth_token, num_retries=num_retries-1)
        else:
            raise e

    if os.path.exists(temp_path):
        os.remove(temp_path)
'''

def setup_master_api_deployment(yaml_path, auth_token=None, max_task_duration=None):
    with open(yaml_path) as deploy_file:
        deploy_yaml = yaml.load(deploy_file.read(), Loader=yaml.FullLoader)

        env_vars = []

        if auth_token is not None:
            env_vars.append({'name': 'PYMADA_TOKEN_AUTH', 'value': auth_token})

        if max_task_duration is not None:
            env_vars.append({'name': 'PYMADA_MAX_TASK_DURATION_SECONDS', 'value': max_task_duration})

        if len(env_vars) > 0:
            deploy_yaml['spec']['template']['spec']['containers'][0]['env'] = env_vars

        return yaml.dump(deploy_yaml)
        


def run_deployment(image, replicas, deploy_name,
                    template_label, container_name, env_vars=[],
                    container_ports=[], pod_node_selector=None,
                    config_path=None):

    container = client.V1Container(
        name=container_name,
        image=image,
        ports=container_ports,
        env=env_vars)
    
    if pod_node_selector is None:
        pod_spec = client.V1PodSpec(containers=[container])
    else:
        pod_spec = client.V1PodSpec(containers=[container],
                                    node_selector=pod_node_selector)

    template = client.V1PodTemplateSpec(
        metadata=client.V1ObjectMeta(labels=template_label),
        spec=pod_spec)

    spec = client.V1DeploymentSpec(
        replicas=replicas,
        template=template,
        selector={'matchLabels': template_label})

    deployment_metadata = client.V1ObjectMeta(
        name=deploy_name,
        labels=template_label
    )

    deployment = client.V1Deployment(
        api_version="apps/v1",
        kind="Deployment",
        metadata=deployment_metadata,
        spec=spec)

    if config_path is None:
        base_dir = os.getcwd()
        config_path = os.path.join(base_dir, 'k3s_config.yaml')
    kube_config.load_kube_config(config_file=config_path)
    appsv1_client = client.AppsV1Api()
    appsv1_client.create_namespaced_deployment(body=deployment, namespace="default")


def run_agent_deployment(image, replicas, deploy_name='pymada-agents-deployment',
                             template_label={'app': 'pymada-agent'},
                             agent_port=5001, container_name='pymada-single-agent',
                             config_path=None, auth_token=None):

    env_vars = [client.V1EnvVar("MASTER_URL", "http://pymadamaster:8000"),
        client.V1EnvVar("AGENT_PORT", str(agent_port)),
        client.V1EnvVar("AGENT_ADDR", value_from=client.V1EnvVarSource(
        field_ref=client.V1ObjectFieldSelector(field_path="status.podIP")))]
    
    if auth_token is not None:
        env_vars.append(client.V1EnvVar("PYMADA_TOKEN_AUTH", auth_token))

    container_ports = [client.V1ContainerPort(container_port=agent_port)]


    run_deployment(image, replicas, deploy_name, template_label, 
            container_name, env_vars=env_vars, container_ports=container_ports,
            config_path=config_path)

def run_master_deployment(image, deploy_name='pymada-master-deployment',
                          template_label={'app': 'pymada-master'},
                          container_port=8000, container_name='pymada-master-container',
                          config_path=None, auth_token=None, max_task_duration=None):

    env_vars = []

    if auth_token is not None:
        env_vars.append(client.V1EnvVar("PYMADA_TOKEN_AUTH", auth_token))

    if max_task_duration is not None:
        env_vars.append(client.V1EnvVar("PYMADA_MAX_TASK_DURATION_SECONDS", max_task_duration))

    container_ports = [client.V1ContainerPort(container_port=container_port)]

    pod_node_selector = {'pymada-role': 'master'}

    run_deployment(image, 1, deploy_name, template_label,
            container_name, env_vars=env_vars, container_ports=container_ports,
            pod_node_selector=pod_node_selector, config_path=config_path)

    base_dir = os.path.dirname(os.path.realpath(__file__))

    if config_path is None:
        cwd = os.getcwd()
        config_path = os.path.join(cwd, 'k3s_config.yaml')

    kube_config.load_kube_config(config_file=config_path)
    kube_client = client.ApiClient()

    if len(get_service_status('service=pymada-master-service').items) == 0:
        utils.create_from_yaml(kube_client, os.path.join(base_dir, 'kube_yaml', 'pymada_master_service.yaml'))

    if len(get_service_status('service=pymada-master-nodeport').items) == 0:
        utils.create_from_yaml(kube_client, os.path.join(base_dir, 'kube_yaml', 'pymada_master_nodeport.yaml'))


def get_deployment_status(label_selector=None, config_path=None):
    if config_path is None:
        base_dir = os.getcwd()
        config_path = os.path.join(base_dir, 'k3s_config.yaml')

    kube_config.load_kube_config(config_file=config_path)
    appsv1_client = client.AppsV1Api()

    api_response = appsv1_client.list_namespaced_deployment('default', label_selector=label_selector)
    
    return api_response.to_dict()


def delete_deployment(deployment_name, config_path=None):
    if config_path is None:
        base_dir = os.getcwd()
        config_path = os.path.join(base_dir, 'k3s_config.yaml')
    kube_config.load_kube_config(config_file=config_path)
    appsv1_client = client.AppsV1Api()
    try:
        appsv1_client.delete_namespaced_deployment(deployment_name, 'default', propagation_policy='Foreground')
    except client.rest.ApiException:
        # ignore 404s
        pass

def delete_all_deployments(config_path=None):
    deployment_names = ['pymada-agents-deployment', 'pymada-master-deployment']

    for deployment_name in deployment_names:
        delete_deployment(deployment_name, config_path=config_path)


def get_service_status(label_selector='', config_path=None):
    if config_path is None:
        base_dir = os.getcwd()
        config_path = os.path.join(base_dir, 'k3s_config.yaml')
    
    kube_config.load_kube_config(config_file=config_path)
    k_client = client.CoreV1Api()
    return k_client.list_namespaced_service('default', label_selector=label_selector)


def get_pod_logs(pod_name, config_path=None):
    if config_path is None:
        base_dir = os.getcwd()
        config_path = os.path.join(base_dir, 'k3s_config.yaml')
    
    kube_config.load_kube_config(config_file=config_path)
    k_client = client.CoreV1Api()
    return k_client.read_namespaced_pod_log(pod_name, 'default')


def get_pod_list(config_path=None):
    if config_path is None:
        base_dir = os.getcwd()
        config_path = os.path.join(base_dir, 'k3s_config.yaml')
    
    kube_config.load_kube_config(config_file=config_path)
    k_client = client.CoreV1Api()

    output = []
    pod_info = k_client.list_namespaced_pod('default')
    for pod in pod_info.items:
        output.append({
            'name': pod.metadata.name,
            'node_name': pod.spec.node_name,
            'status': pod.status.phase,
            'age': datetime.datetime.now(tz=tzutc()) - pod.status.start_time,
            'restart_count': pod.status.container_statuses[0].restart_count,
            'deletion_timestamp': pod.metadata.deletion_timestamp
        })

    return output