import socket
import requests
import time
import subprocess
import os
import logging
from flask import Flask, json, request

runner_configs = {
    'python': {
        'executable': 'python3',
        'dependency_manager': {
            'file_name': 'requirements.txt',
            'command': 'python3 -m pip install -r requirements.txt'
        }
    },
    'node_puppeteer': {
        'executable': 'node',
        'dependency_manager': {
            'file_name': 'package.json',
            'command': 'npm install'
        }
    }
}

class Agent(object):

    def __init__(self, master_base_url, agent_url=None, runner_num=1, auth_token=None, autoregister=True, runner_write_path=None):
        self.task = None
        self.runner = None
        self.registered_num = None
        self.dep_install_process = None
        self.master_url = master_base_url
        self.runner_num = runner_num
        self.auth_token = auth_token

        if autoregister:
            self.register_on_master(self_url=agent_url)
            self.get_runner(runner_num=runner_num, write_path=runner_write_path)

    def register_on_master(self, self_url=None, req_url=None):
        if req_url is None:
            req_url = '/register_agent/'

        register_response = self._request_master(req_url, 'POST', json_data={
            'hostname': socket.gethostname(),
            'agent_url': self_url,
            'runner_num': self.runner_num
        })

        parsed_response = register_response.json()
        logging.info('register response: ' + str(parsed_response))
        self.registered_num = parsed_response['id']

    def get_runner(self, runner_num=None, req_url=None, write_path=None):
        if runner_num is None:
            runner_num = self.runner_num

        if req_url is None:
            req_url = '/runner/' + str(runner_num) + '/'

        res = self._request_master(req_url, 'GET')

        if not res.ok:
            logging.warning('error with getting runner: ' + str(res.text))
            return
        
        runner_info = res.json()

        if runner_info['dependency_file'] is not None:
            write_folder = None
            if write_path is not None:
                write_folder = os.path.dirname(write_path)

            self.install_dependencies(runner_info['dependency_file'], 
                                      runner_info['file_type'], write_folder)

        logging.debug('runner data: ' + str(runner_info))

        self.save_runner(runner_info, write_path)
    
    def save_runner(self, runner_info, write_path=None):
        if write_path is None:
            agent_path = os.path.dirname(os.path.realpath(__file__))
            write_path = os.path.join(agent_path, runner_info['file_name'])
        
        with open(write_path, 'w') as runner_file:
            runner_file.write(runner_info['contents'])

        self.runner = Runner(write_path, runner_info['file_type'],
                             runner_info['custom_executable'])
        self.runner_num = runner_info['id']

        return {}
    
    def install_dependencies(self, dep_file, runner_type, write_folder=None):
        if  write_folder is None:
            write_folder = os.path.dirname(os.path.realpath(__file__))

        dep_config = runner_configs[runner_type]['dependency_manager']
        write_path = os.path.join(write_folder, dep_config['file_name'])

        with open(write_path, 'w') as depout:
            depout.write(dep_file)

        logging.info('installing dependencies')
        
        self.dep_install_process = subprocess.Popen(dep_config['command'], shell=True, cwd=write_folder)

    def get_task(self):
        return self.task

    def save_task_results(self, results, req_url=None):
        if self.task is None:
            return {'error': 'no current task'}
        
        logging.debug('saving: ' + str(results))

        if type(results) is str:
            self.task['task_result'] = results
        else:
            self.task['task_result'] = json.dumps(results)

        if req_url is None:
            req_url = '/urls/' + str(self.task['id']) + '/'

        r = self._request_master(req_url, 'PUT', json_data=self.task)

        if not r.ok:
            logging.warning('error with saving task result: ' + str(r.json()))

        self.task = None
    
    def start_runner(self, task_data):
        if self.runner is not None:
            self.task = task_data
            return self.runner.run()
        
        return {'error': 'no runner available'}
    
    def kill_runner(self):
        if self.runner is not None:
            self.runner.kill()
            return {}

        return {'error': 'no runner available'}
    
    def check_runner(self):
        if self.runner is None:
            self.get_runner()
            return 'NO_RUNNER'

        if self.dep_install_process is not None:
            if self.dep_install_process.poll() is not None:
                self.dep_install_process = None
            else:
                return 'NO_RUNNER'

        runner_status = self.runner.get_status()

        return runner_status


    def add_url(self, url, json_metadata=None, req_url=None):
        if req_url is None:
            req_url = '/urls/'

        new_url_task = {
            "url": url
        }

        if json_metadata is not None:

            print('json_metadata', type(json_metadata), json_metadata)
            if type(json_metadata) == dict:
                new_url_task['json_metadata'] = json.dumps(json_metadata)
            else:
                new_url_task['json_metadata'] = json_metadata
        
        print('new url data', new_url_task)

        r = self._request_master(req_url, 'POST', json_data=new_url_task)

        if not r.ok:
            err_msg = r.json()
            logging.warning('error with adding url: ' + str(err_msg))
            return err_msg
        else:
            return r.json()
    
    def log_error(self, error_msg, req_url=None):
        if req_url is None:
            req_url = '/log_error/'
        
        msg = {
            'message': error_msg,
            'reporting_agent': self.registered_num,
            'runner': self.runner_num
        }

        r = self._request_master(req_url, 'POST', json_data=msg)
        
        if not r.ok:
            err_msg = r.json()
            logging.warning('error with logging error: ' + str(err_msg))
            return err_msg
        else:
            return r.json()
    
    def save_screenshot(self, screenshot, filename, req_url=None):
        if req_url is None:
            req_url = '/screenshots/'
        
        r = self._request_master(req_url, 'POST',
                                 files={'screenshot': (filename, screenshot),
                                        'task': ('', self.task['id'])})

        if not r.ok:
            err_msg = r.json()
            return err_msg
        else:
            return r.json()

    def _send_request(self, req_url, method, json_data=None, headers={}, 
                      files={}, _num_tries=0):
        try:
            response = requests.request(method, req_url, json=json_data, 
            headers=headers, files=files, timeout=60)
            return response
        except (requests.ConnectionError, requests.Timeout) as e:
            if _num_tries < 10:
                logging.warning('unable to contact, retrying ' + req_url)
                time.sleep(3)
                return self._send_request(req_url, method, json_data=json_data, 
                    files=files, headers=headers, _num_tries=_num_tries+1)
            else:
                raise e
        
    def _request_master(self, url, method, json_data=None, files={}, master_url=None):
        if master_url is not None:
            req_url = master_url + url
        else:
            req_url = self.master_url + url

        headers = {}

        if self.auth_token is not None:
            headers = {
                'pymada_token_auth': self.auth_token
            }

        return self._send_request(req_url, method, json_data, headers=headers, files=files)


class Runner(object):

    class states(object):
        RUNNING = 'RUNNING'
        IDLE = 'IDLE'

    def __init__(self, file_path, file_type='python', custom_executable=None):
        if custom_executable is not None:
            self.executable = custom_executable
        else:
            self.executable = runner_configs[file_type]['executable']
        self.process = None
        self.file = file_path
        self.last_run_code = None

    def run(self):
        if self.process is None:
            self.get_status()
            command = [self.executable, self.file]
            cwd = os.path.dirname(os.path.realpath(__file__))
            self.process = subprocess.Popen(command, cwd=cwd)
            logging.debug('running ' + str(command))

            return {}

    def get_status(self):
        if self.process is None:
            return self.states.IDLE

        poll_result = self.process.poll()
        logging.debug('get status called, poll result ' + str(poll_result))

        if poll_result is None:
            return self.states.RUNNING

        if poll_result is not None:
            self.process = None
            self.last_run_code = poll_result
            return self.states.IDLE
    
    def kill(self):
        if self.process is not None:
            self.process.kill()

def gen_flask_app():

    logging.basicConfig(format='%(asctime)s %(message)s', datefmt='%Y/%m/%d %I:%M:%S %p',
        level=os.getenv('LOG_LEVEL', 'INFO'))

    flask_app = Flask(__name__)

    agent_url = "http://127.0.0.1:5001"
    agent_port = "5001"

    if 'AGENT_PORT' in os.environ:
        agent_port = os.environ['AGENT_PORT']

    if 'AGENT_ADDR' in os.environ:
        agent_url = 'http://' + os.environ['AGENT_ADDR'] + ':' + agent_port

    runner_num = 1
    if 'RUNNER_NUM' in os.environ:
        try:
            runner_num = int(os.environ['RUNNER_NUM'])
        except ValueError:
            pass

    auth_token = None
    if 'PYMADA_TOKEN_AUTH' in os.environ:
        auth_token = os.environ['PYMADA_TOKEN_AUTH']

    if 'MASTER_URL' in os.environ:
        agent = Agent(os.environ['MASTER_URL'], agent_url=agent_url, runner_num=runner_num, auth_token=auth_token)
    else:
        agent = Agent('http://localhost:8000', agent_url=agent_url, runner_num=runner_num, auth_token=auth_token)

    
    @flask_app.route('/get_task', methods=['POST'])
    def get_task():
        return json.jsonify(agent.get_task())
    
    @flask_app.route('/save_results', methods=['POST'])
    def save_results():
        json_data = request.get_json()
        response = agent.save_task_results(json_data)

        return json.jsonify(response)
    
    @flask_app.route('/save_screenshot', methods=['POST'])
    def save_screenshot():
        screenshot = request.files['screenshot']
        response = agent.save_screenshot(screenshot.read(), screenshot.filename)
        print('res', response)
        return json.jsonify(response)

    @flask_app.route('/assign_runner', methods=['POST'])
    def assign_runner():
        runner_data = request.get_json()
        logging.debug('runner info: ' + str(runner_data))

        return json.jsonify(agent.save_runner(runner_data))

    @flask_app.route('/start_run', methods=['POST'])
    def start_runner():
        task_data = request.get_json()
        logging.debug('task data' + str(task_data))
        return json.jsonify(agent.start_runner(task_data))

    @flask_app.route('/kill_run', methods=['POST'])
    def kill_runner():
        return json.jsonify(agent.kill_runner())

    @flask_app.route('/check_runner', methods=['POST'])
    def check_runner():
        status = agent.check_runner()
        if 'error' in status:
            return json.jsonify(status), 500
        else:
            return json.jsonify({'status': status})

    @flask_app.route('/add_url', methods=['POST'])
    def add_url():
        url_data = request.get_json()
        logging.debug('new url to add' + str(url_data))
        return json.jsonify(agent.add_url(url_data['url'], url_data['json_metadata']))
    
    @flask_app.route('/log_error', methods=['POST'])
    def log_error():
        err_info = request.get_json()
        if 'message' in err_info:
            return json.jsonify(agent.log_error(err_info['message']))
        
        return json.jsonify({'error': 'request needs to have a "message" attribute'})

    return flask_app

if __name__ == '__main__':
    agent = Agent('http://localhost:8000', autoregister=False)
