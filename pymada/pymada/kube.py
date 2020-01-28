import os
import urllib3
import time
import datetime
import yaml
from dateutil.tz import tzutc
from kubernetes import client, utils, config
from kubernetes.config import kube_config

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

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


def run_deployment(pod_spec, replicas, deploy_name,
                    template_label, config_path=None):

    '''
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
    '''

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

def create_puppeteer_pod_spec(container_name, agent_container_ports, env_vars):
    agent_image_name = 'pymada/node-puppeteer'
    agent_container = client.V1Container(
        name=container_name,
        image=agent_image_name,
        ports=agent_container_ports,
        env=env_vars)

    pod_spec = client.V1PodSpec(containers=[agent_container])

    return pod_spec

def create_selenium_pod_spec(selenium_type, container_name, agent_container_ports, env_vars):
    if selenium_type == 'firefox':
        agent_image_name = 'pymada/selenium-firefox',
    elif selenium_type == 'chrome':
        agent_image_name = 'pymada/selenium-chrome'

    selenium_ports = [client.V1ContainerPort(container_port=4444)] + agent_container_ports
    selenium_container = client.V1Container(
        name=container_name,
        image=agent_image_name,
        ports=selenium_ports,
        env=env_vars,
        volume_mounts=[client.V1VolumeMount(mount_path='/dev/shm', name='dshm')]
    )

    pod_spec = client.V1PodSpec(containers=[selenium_container],
                                volumes=[client.V1Volume(name='dshm',
                                    empty_dir=client.V1EmptyDirVolumeSource(medium='Memory'))])

    return pod_spec

def run_agent_deployment(agent_type, replicas, deploy_name='pymada-agents-deployment',
                             template_label={'app': 'pymada-agent'},
                             agent_port=5001, container_name='pymada-single-agent',
                             auth_token=None, config_path=None):

    env_vars = [client.V1EnvVar("MASTER_URL", "http://pymadamaster:8000"),
        client.V1EnvVar("AGENT_PORT", str(agent_port)),
        client.V1EnvVar("AGENT_ADDR", value_from=client.V1EnvVarSource(
        field_ref=client.V1ObjectFieldSelector(field_path="status.podIP")))]

    if auth_token is not None:
        env_vars.append(client.V1EnvVar("PYMADA_TOKEN_AUTH", auth_token))

    agent_container_ports = [client.V1ContainerPort(container_port=agent_port)]

    if agent_type == 'node_puppeteer':
        pod_spec = create_puppeteer_pod_spec(container_name, agent_container_ports,
                                             env_vars)

    elif agent_type == 'python_selenium_firefox':
        pod_spec = create_selenium_pod_spec('firefox', container_name,
                        agent_container_ports, env_vars)
    
    elif agent_type == 'python_selenium_chrome':
        pod_spec = create_selenium_pod_spec('chrome', container_name,
                        agent_container_ports, env_vars)

    run_deployment(pod_spec, replicas, deploy_name, template_label,
                   config_path=config_path)

def run_master_deployment(deploy_name='pymada-master-deployment',
                          template_label={'app': 'pymada-master'},
                          container_port=8000, container_name='pymada-master-container',
                          config_path=None, auth_token=None, max_task_duration=None,
                          max_task_retries=None):

    env_vars = []

    if auth_token is not None:
        env_vars.append(client.V1EnvVar("PYMADA_TOKEN_AUTH", auth_token))

    if max_task_duration is not None:
        env_vars.append(client.V1EnvVar("PYMADA_MAX_TASK_DURATION_SECONDS", str(max_task_duration)))

    if  max_task_retries is not None:
        env_vars.append(client.V1EnvVar("PYMADA_MAX_TASK_RETRIES", str(max_task_retries)))

    container_ports = [client.V1ContainerPort(container_port=container_port)]

    container = client.V1Container(
        name=container_name,
        image='pymada/master',
        ports=container_ports,
        env=env_vars)

    pod_node_selector = {'pymada-role': 'master'}
    pod_spec = client.V1PodSpec(containers=[container],
                                node_selector=pod_node_selector)

    run_deployment(pod_spec, 1, deploy_name, template_label,
                   config_path=config_path)

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