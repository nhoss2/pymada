import os
import secrets
import string
import uuid
import json
import time
import traceback
import random
from multiprocessing import Pool
import requests
from libcloud.compute.types import Provider
from libcloud.compute.providers import get_driver
from libcloud.compute.base import NodeAuthSSHKey
from libcloud.compute.deployment import ScriptDeployment, SSHKeyDeployment


def get_size(driver, name):
    for size in driver.list_sizes():
        if size.name == name:
            return size
    
    raise KeyError('size: ' + name + ' not found')

def get_image(driver, name):
    for image in driver.list_images():
        if image.name == name:
            return image

    raise KeyError('image: ' + name + ' not found')

def get_image_startswith(driver, name):
    for image in driver.list_images():
        if image.name.startswith(name):
            return image

    raise KeyError('image: ' + name + ' not found')

def get_location(driver, name):
    for location in driver.list_locations():
        if location.name == name:
            return location

    raise KeyError('location: ' + name + ' not found')

def get_key(driver, name):
    for key in driver.list_key_pairs():
        if key.name == name:
            return key

    raise KeyError('key: ' + name + ' not found')


def get_node(driver, name):
    nodes = driver.list_nodes()
    for node in nodes:
        if node.name == name:
            return node

    raise KeyError('node: ' + name + ' not found')

class CloudConfigGen(object):

    def __init__(self, token=None):
        self.file_dir = os.path.dirname(os.path.abspath(__file__))
        self.master_yaml = os.path.join(self.file_dir, 'cloud_init_master.yaml')
        self.node_yaml = os.path.join(self.file_dir, 'cloud_init_node.yaml')
        self.bootstrap_server = os.path.join(self.file_dir, 'bootstrap.py')

        if token is None:
            self.token = self.gen_token(80)
        else:
            self.token = token

        self.bootstrap_token = self.gen_token(30)

    def gen_token(self, token_length):
        chars = string.ascii_letters + string.digits
        return ''.join(secrets.choice(chars) for i in range(token_length))
    
    def gen_master(self):
        yaml_file = open(self.master_yaml).read()

        #k3s_command = 'K3S_CLUSTER_SECRET=' + self.token + ' K3S_KUBECONFIG_OUTPUT=/kubeconfig.yaml tmux new-session -d /k3s server\n'
        #k3s_command = 'K3S_CLUSTER_SECRET=' + self.token + ' K3S_KUBECONFIG_OUTPUT=/kubeconfig.yaml sh /k3s_install.sh --bind-address 0.0.0.0\n' +\
        k3s_command = 'python3 /bootstrap.py\n\nwrite_files:\n  - content: |\n'
        
        with open(self.bootstrap_server) as bootstrap_script:
            k3s_command += '      ' + 'route = "' + self.bootstrap_token + '"\n'
            k3s_command += '      ' + 'k3s_token = "' + self.token + '"\n'
            for line in bootstrap_script.read().split('\n')[2:]:
                k3s_command += '      ' + line + '\n'
        
        k3s_command += '\n    path: /bootstrap.py'

        return yaml_file + k3s_command
    
    def gen_node(self, master_ip):
        yaml_file = open(self.node_yaml).read()

        # note, if updating K3S version, need to update on bootstrap.py as well
        k3s_command = 'INSTALL_K3S_VERSION=v0.6.1 K3S_CLUSTER_SECRET=' + self.token + ' K3S_URL="https://' + master_ip + ':6443" sh /k3s_install.sh\n'

        return yaml_file + k3s_command


class ProvisionGoogle(object):

    def __init__(self):
        self.instance = {
            'size': 'g1-small',
            'image': 'ubuntu-1804',
            'location': 'australia-southeast1-b'
        }

        base_path = os.getcwd()

        self.driver_info = {
            'user': 'compute@nafis-236908.iam.gserviceaccount.com',
            'auth': os.path.join(base_path, 'nafis_compute_-236908-a9e5d90dc318.json'),
            'project': 'nafis-236908'
        }

        self.ccg = CloudConfigGen()
        self.node_suffix = uuid.uuid4().hex[:8]
        self.settings = None

        compute_engine = get_driver(Provider.GCE)

        self.driver = compute_engine(
            self.driver_info['user'],
            self.driver_info['auth'],
            project=self.driver_info['project']
        )

    def create_master(self, preemptible=False):
        master_node_name = 'pymada-master-' + self.node_suffix
        print('creating:', master_node_name)

        self.driver.create_node(
            name=master_node_name,
            size=self.instance['size'],
            image=self.instance['image'],
            location=self.instance['location'],
            ex_metadata={'user-data': self.ccg.gen_master()},
            ex_preemptible=preemptible
        )

        self.settings = {
            'master_node_name': master_node_name,
            'master_node_ip': '',
            'token': self.ccg.token,
            'agents': []
        }

        self.save_settings()

        while True:
            master_node = get_node(self.driver, master_node_name)
            if len(master_node.public_ips) > 0:
                self.settings['master_node_ip'] = master_node.public_ips[0]
                print('master ip:', master_node.public_ips[0])
                break

            time.sleep(1)
        
        self.save_settings()

    def create_agent(self, num, preemptible=False):
        if self.settings is None:
            self.settings = self.load_settings()

            if 'token' in self.settings:
                self.ccg = CloudConfigGen(self.settings['token'])

        with Pool(processes=10) as pool:
            for i in range(num):
                agent_node_name = 'pymada-agent-' + str(i) + '-' + self.node_suffix

                node_info = {
                    'name': agent_node_name,
                    'size': self.instance['size'],
                    'image': self.instance['image'],
                    #'location': self.instance['location'],
                    'ex_metadata': {'user-data': self.ccg.gen_node(self.settings['master_node_ip'])},
                    'ex_preemptible': preemptible
                }

                pool.apply_async(create_node_gc_mp, (self.driver_info, node_info))

                self.settings['agents'].append(agent_node_name)

            pool.close()
            pool.join()
        
        self.save_settings()

    def delete_all(self):
        if self.settings is None:
            self.settings = self.load_settings()

        if 'master_node_name' in self.settings:
            node = get_node(self.driver, self.settings['master_node_name'])
            print('destroying:', node.name)
            self.driver.destroy_node(node)
            del(self.settings['master_node_name'])
            del(self.settings['master_node_ip'])
            
            self.save_settings()

        if 'agents' in self.settings:
            for node_name in self.settings['agents']:
                node = get_node(self.driver, node_name)
                print('destroying:', node.name)
                self.driver.destroy_node(node)

            del(self.settings['agents'])
            self.save_settings()

    def save_settings(self, settings_file=None):
        if settings_file is None:
            file_dir = os.getcwd()
            settings_file = os.path.join(file_dir, 'provision_data.json')
        with open(settings_file, 'w') as jsonfile:
            json.dump(self.settings, jsonfile)

    def load_settings(self, settings_file):
        if settings_file is None:
            file_dir = os.getcwd()
            settings_file = os.path.join(file_dir, 'provision_data.json')
        if os.path.exists(settings_file):
            with open(settings_file) as jsonfile:
                return json.load(jsonfile)
    
    def get_k3s_config(self, num_tries=0):
        if self.ccg.bootstrap_token is None:
            print('unable to get k3s config, no token generated')
            return
        
        req_url = 'http://' + self.settings['master_node_ip'] + ':30200/' +\
             self.ccg.bootstrap_token + '/' + self.settings['master_node_ip']
        
        try:
            r = requests.get(req_url, timeout=180)
            response = r.text
            return response
        except requests.exceptions.ConnectionError:
            time.sleep(8)
            #print('retrying', req_url)
            if num_tries > 30:
                print('unable to contact k3s master server')
                return
            return self.get_k3s_config(num_tries=num_tries+1)
    
    def write_modify_k3s_config(self, k3s_config, write_path=None):
        if write_path is None:
            base_path = os.getcwd()
            write_path = os.path.join(base_path, 'k3s_config.yaml')

        master_addr = self.settings['master_node_ip'] + ':6443\n    insecure-skip-tls-verify: true'
  
        updated_ip = master_addr.join(k3s_config.split('localhost:6443'))
        with open(write_path, 'w') as out_config:
            out_config.write(updated_ip)


def create_node_gc_mp(driver_info, node_info):
    try:
        print('creating', node_info['name'])
        compute_engine = get_driver(Provider.GCE)
        driver = compute_engine(driver_info['user'], driver_info['auth'], project=driver_info['project'])

        if 'location' in node_info:
            node_location = node_info['location']
        else:
            node_location = random.choice(driver.list_locations())

        driver.create_node(
            name=node_info['name'],
            size=node_info['size'],
            image=node_info['image'],
            location=node_location,
            ex_metadata=node_info['ex_metadata'],
            ex_preemptible=node_info['ex_preemptible']
        )
    except Exception as e:
        traceback.print_exc()

        raise e


def run_gc():
    gc = ProvisionGoogle()
    print(gc.ccg.gen_master())
    #gc.create_master(preemptible=True)
    #gc.create_agent(5, preemptible=True)
    #gc.delete_all()

'''
def run():
    cls = get_driver(Provider.DIGITAL_OCEAN)

    base_path = os.path.dirname(os.path.realpath(__file__))
    with open(os.path.join(base_path, 'do_token.txt')) as do_token:
        driver = cls(do_token.read(), api_version='v2')

    size = get_size(driver, 's-1vcpu-1gb')
    image = get_image(driver, '18.04 x64')
    location = get_location(driver, 'Singapore 1')
    key = get_key(driver, 'laptop-x1')

    ccg = CloudConfigGen()

    node_suffix = uuid.uuid4().hex[:8]

    master_node_name = 'pymada-master-' + node_suffix
    print('creating:', master_node_name)

    driver.create_node(name=master_node_name, size=size, image=image, location=location, ex_create_attr={'ssh_keys':[key.fingerprint]},
                              ex_user_data=ccg.gen_master())
    
    settings = {
        'master_node_name': master_node_name,
        'master_node_ip': '',
        'agents': []
    }
    save_settings(settings)
    
    while True:
        master_node = get_node(driver, master_node_name)
        if len(master_node.public_ips) > 0:
            settings['master_node_ip'] = master_node.public_ips[0]
            break

        time.sleep(2)
    
    save_settings(settings)

    for i in range(2):
        agent_node_name = 'pymada-agent-' + str(i) + '-' + node_suffix
        print('creating:', agent_node_name)

        driver.create_node(name=agent_node_name, size=size, image=image, location=location, ex_create_attr={'ssh_keys':[key.fingerprint]},
                              ex_user_data=ccg.gen_node(settings['master_node_ip']))
        
        settings['agents'].append(agent_node_name)
    
    save_settings(settings)

def delete_nodes():
    cls = get_driver(Provider.DIGITAL_OCEAN)

    base_path = os.path.dirname(os.path.realpath(__file__))
    with open(os.path.join(base_path, 'do_token.txt')) as do_token:
        driver = cls(do_token.read(), api_version='v2')
    
    settings = load_settings()

    if 'master_node_name' in settings:
        node = get_node(driver, settings['master_node_name'])
        print('destroying:', node.name)
        driver.destroy_node(node)
        del(settings['master_node_name'])
        del(settings['master_node_ip'])
        
        save_settings(settings)

    if 'agents' in settings:
        for node_name in settings['agents']:
            node = get_node(driver, node_name)
            print('destroying:', node.name)
            driver.destroy_node(node)

        del(settings['agents'])
'''


if __name__ == '__main__':
    run_gc()
    print('ok')
