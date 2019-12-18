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
        k3s_command = 'INSTALL_K3S_VERSION=v0.9.1 K3S_CLUSTER_SECRET=' + self.token + ' K3S_URL="https://' + master_ip + ':6443" sh /k3s_install.sh\n'

        return yaml_file + k3s_command

class Provision(object):

    def __init__(self, instance_info, driver_info, driver):
        self.instance = instance_info
        self.driver_info = driver_info
        self.driver = driver

        self.ccg = CloudConfigGen()
        self.node_suffix = uuid.uuid4().hex[:8]
        self.settings = None
    
    def create_node(self, name, user_data=None, preemptible=False):
        raise NotImplementedError()

    def create_node_mp(self, name_list, user_data=None, preemptible=False):
        raise NotImplementedError()

    def create_master(self, preemptible=False):
        master_node_name = 'pymada-master-' + self.node_suffix

        self.create_node(
            name=master_node_name,
            user_data=self.ccg.gen_master(),
            preemptible=preemptible
        )

        self.settings = {
            'master_node_name': master_node_name,
            'master_node_ip': '',
            'token': self.ccg.token,
            'agents': [],
            'pymada_auth_token': self.ccg.gen_token(30)
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
        
        agent_node_names = []
        for i in range(num):
            agent_node_names.append('pymada-agent-' + str(i) + '-' + self.node_suffix)
        
        self.create_node_mp(agent_node_names,
                            user_data=self.ccg.gen_node(self.settings['master_node_ip']),
                            preemptible=preemptible)
        
        if 'agents' in self.settings:
            self.settings['agents'] += agent_node_names
        else:
            self.settings['agents'] = agent_node_names
        
        self.save_settings()


    def delete_all(self):
        if self.settings is None:
            self.settings = self.load_settings()

        if 'master_node_name' in self.settings:
            node = get_node(self.driver, self.settings['master_node_name'])
            print('terminating:', node.name)
            self.driver.destroy_node(node)
            del(self.settings['master_node_name'])
            del(self.settings['master_node_ip'])
            
            self.save_settings()

        if 'agents' in self.settings:
            for node_name in self.settings['agents']:
                node = get_node(self.driver, node_name)
                print('terminating:', node.name)
                self.driver.destroy_node(node)

            del(self.settings['agents'])
            self.save_settings()

    def save_settings(self, settings_file=None):
        if settings_file is None:
            file_dir = os.getcwd()
            settings_file = os.path.join(file_dir, 'provision_data.json')
        with open(settings_file, 'w') as jsonfile:
            json.dump(self.settings, jsonfile)

    def load_settings(self, settings_file=None):
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
            # long time out due to kubernetes install happening on same process
            # on the server as serving the http response

            print(req_url)

            r = requests.get(req_url, timeout=360)
            response = r.text
            return response
        except requests.exceptions.ConnectionError:
            time.sleep(8)
            if num_tries > 30:
                print('unable to contact k3s master server')
                return
            return self.get_k3s_config(num_tries=num_tries+1)
    
    def write_modify_k3s_config(self, k3s_config, write_path=None):
        if write_path is None:
            base_path = os.getcwd()
            write_path = os.path.join(base_path, 'k3s_config.yaml')

        master_addr = self.settings['master_node_ip'] + ':6443\n    insecure-skip-tls-verify: true'
  
        updated_ip = master_addr.join(k3s_config.split('127.0.0.1:6443'))
        with open(write_path, 'w') as out_config:
            out_config.write(updated_ip)

class ProvisionDigitalOcean(Provision):
    def __init__(self, token, node_size, node_image, node_location=None):
        do_driver = get_driver(Provider.DIGITAL_OCEAN)

        driver_info = {
            'token': token
        }

        driver = do_driver(driver_info['token'], api_version='v2')

        instance = {
            'size': node_size,
            'image': node_image,
            'location': node_location
        }

        super().__init__(instance, driver_info, driver)
    
    def create_node(self, name, user_data=None, preemptible=False):
        node_info = {
            'name': name,
            'size': self.instance['size'],
            'image': self.instance['image'],
            'location': self.instance['location'],
            'ex_user_data': user_data
        }
        create_node_digial_ocean_mp(self.driver_info, node_info)

    def create_node_mp(self, name_list, user_data=None, preemptible=False):
        with Pool(processes=10) as pool:
            for node_name in name_list:
                node_info = {
                    'name': node_name,
                    'size': self.instance['size'],
                    'image': self.instance['image'],
                    'location': self.instance['location'],
                    'ex_user_data': user_data,
                }

                pool.apply_async(create_node_digial_ocean_mp, 
                                 (self.driver_info, node_info))

            pool.close()
            pool.join()


class ProvisionGoogleCloud(Provision):
    def __init__(self, user, auth, project, node_size, node_image, 
                 node_location=None):
        gc_driver = get_driver(Provider.GCE)

        driver_info = {
            'user': user,
            'auth': auth,
            'project': project
        }

        driver = gc_driver(user, auth, project=project)

        instance = {
            'size': node_size,
            'image': node_image,
            'location': node_location
        }

        super().__init__(instance, driver_info, driver)
    
    def create_node(self, name, user_data=None, preemptible=False):
        node_info = {
            'name': name,
            'size': self.instance['size'],
            'image': self.instance['image'],
            'location': self.instance['location'],
            'ex_metadata': {'user-data': user_data},
            'ex_preemptible': preemptible
        }
        create_node_gc_mp(self.driver_info, node_info)

    def create_node_mp(self, name_list, user_data=None, preemptible=False):
        
        with Pool(processes=10) as pool:
            for node_name in name_list:
                node_info = {
                    'name': node_name,
                    'size': self.instance['size'],
                    'image': self.instance['image'],
                    'location': self.instance['location'],
                    'ex_metadata': {'user-data': user_data},
                    'ex_preemptible': preemptible
                }

                pool.apply_async(create_node_gc_mp, 
                                 (self.driver_info, node_info))

            pool.close()
            pool.join()


class ProvisionAWS(Provision):

    def __init__(self, access_id, secret_key, region, node_size, node_image,
                 node_location, node_subnet, keyname=None, node_image_owner=None):

        aws_driver = get_driver(Provider.EC2)

        driver_info = {
            'access_id': access_id,
            'secret_key': secret_key,
            'region': region
        }

        driver = aws_driver(access_id, secret_key, region=region)

        instance = {
            'size': node_size,
            'image': node_image,
            'image_owner': node_image_owner,
            'location': node_location,
            'keyname': keyname,
            'subnet': node_subnet
        }

        super().__init__(instance, driver_info, driver)

    def create_node(self, name, user_data=None, preemptible=False):

        node_info = self.instance
        node_info['name'] = name
        node_info['ex_userdata'] = user_data
        create_node_aws_mp(self.driver_info, node_info)

    def create_node_mp(self, name_list, user_data=None, preemptible=False):

        with Pool(processes=10) as pool:
            for node_name in name_list:
                node_info = self.instance
                node_info['name'] = node_name
                node_info['ex_userdata'] = user_data

                pool.apply_async(create_node_aws_mp,
                                 (self.driver_info, node_info))

            pool.close()
            pool.join()


def create_node_gc_mp(driver_info, node_info):
    try:
        print('creating:', node_info['name'])
        compute_engine = get_driver(Provider.GCE)
        driver = compute_engine(driver_info['user'], driver_info['auth'], project=driver_info['project'])

        if 'location' in node_info and node_info['location'] is not None:
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

def create_node_digial_ocean_mp(driver_info, node_info):
    try:
        print('creating:', node_info['name'])
        provider = get_driver(Provider.DIGITAL_OCEAN)
        driver = provider(driver_info['token'], api_version='v2')

        if 'location' in node_info and node_info['location'] is not None:
            node_location = get_location(driver, node_info['location'])
        else:
            node_location = random.choice(driver.list_locations())

        driver.create_node(
            name=node_info['name'],
            size=get_size(driver, node_info['size']),
            image=get_image(driver, node_info['image']),
            location=node_location,
            ex_user_data=node_info['ex_user_data'],
            ex_create_attr={
                'ssh_keys': [k.fingerprint for k in driver.list_key_pairs()]
            }
        )
    except Exception as e:
        traceback.print_exc()

        raise e

def create_node_aws_mp(driver_info, node_info):
    try:
        print('creating:', node_info['name'])
        provider = get_driver(Provider.EC2)


        driver = provider(driver_info['access_id'],
                          driver_info['secret_key'],
                          region=driver_info['region'])
        

        if 'location' in node_info and node_info['location'] is not None:
            node_location = get_location(driver, node_info['location'])
        else:
            node_location = random.choice(driver.list_locations())
        
        if 'image_owner' in node_info and node_info['image_owner'] is not None:
            image_list = driver.list_images(
                location=node_location,
                ex_owner=node_info['image_owner']
            )
        else:
            image_list = driver.list_images(
                location=node_location
            )

        selected_image = None
        for image in image_list:
            if image.name == node_info['image']:
                selected_image = image
            
        subnet = driver.ex_list_subnets([node_info['subnet']])[0]

        driver.create_node(
            name=node_info['name'],
            size=get_size(driver, node_info['size']),
            image=selected_image,
            location=node_location,
            ex_subnet=subnet,
            ex_keyname=node_info['keyname'],
            ex_userdata=node_info['ex_userdata']
        )
    except Exception as e:
        traceback.print_exc()

        raise e


if __name__ == '__main__':
    '''
    do = ProvisionDigitalOcean(
        open('/home/nafis/code/pymada/test_project/do_token.txt').read(),
        's-1vcpu-1gb', '18.04.3 (LTS) x64')
    
    #do.create_master()
    do.delete_all()
    '''
    print('ok')