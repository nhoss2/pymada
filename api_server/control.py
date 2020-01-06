import os
import time
import subprocess
import logging
import requests
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "api_server.settings")
import django
django.setup()
from master_server.models import UrlTask, Agent
from master_server.serializers import UrlTaskSerializer
from django.contrib.auth.models import User

class Control(object):

    def __init__(self, max_task_duration_seconds=60*5):
        self.max_duration_seconds = max_task_duration_seconds

    # TODO: find better way of being notified of state changes instead of polling
    def loop(self):

        # assign queued tasks to idle agents if any exist
        try:
            idle_agent = Agent.objects.filter(agent_state='IDLE')[0]
            queued_task = UrlTask.objects.filter(
                task_state='QUEUED').order_by('fail_num')[0]
            self.assign_task(queued_task, idle_agent)
        except IndexError:
            pass
        
        # check last contact with agents and their task duration
        try:
            last_min = time.time() - 5
            agents = Agent.objects.filter(last_contact_attempt__lte=last_min)

            for agent in agents:
                self.check_status(agent)
                self.check_task_duration(agent)
        except IndexError:
            pass


        time.sleep(0.05)
    
    def run(self):
        while True:
            self.loop()

    def assign_task(self, task, agent):

        # check agent doesnt have existing assigned tasks that haven't completed
        assigned_tasks = UrlTask.objects.filter(assigned_agent=agent)
        for assigned_task in assigned_tasks:
            if assigned_task.task_state != 'COMPLETE':
                logging.warning('task {} ({}) was assigned but no results were returned'.format(
                    assigned_task.id, assigned_task.url))
                assigned_task.fail_num += 1
                assigned_task.task_state = 'QUEUED'
                assigned_task.start_time = 0.0

            assigned_task.assigned_agent = None
            assigned_task.save()

        logging.info('assigning ' + str(task.id) + ' to agent ' 
            + str(agent.id))

        task.assigned_agent = agent
        task.task_state = 'ASSIGNED'
        task.start_time = time.time()
        task.save()
        agent.agent_state = 'ASSIGNED'
        agent.assigned_task = task
        agent.save()

        response, code = self._send_request(
            agent.agent_url + '/start_run',
            json_data=UrlTaskSerializer(task).data)

        if code != 200 and type(response) is dict:
            logging.error('error from assigning task ' + str(response))
            task.task_state = 'QUEUED'
            task.save()
            agent.agent_state = 'LOST'
            agent.save()
        if code is None:
            agent.agent_state = 'LOST'
            agent.save()

        agent.last_contact_attempt = time.time()
        agent.save()
    
    def check_status(self, agent):
        logging.debug('checking status of ' + str(agent.id))

        response, code = self._send_request(agent.agent_url + '/check_runner')

        if code != 200 and type(response) is dict:
            logging.error('error from check status ' + str(response))
        elif code is None:
            agent.agent_state = 'LOST'
            agent.save()
        elif code == 200:
            accepted_states = ('IDLE', 'RUNNING', 'NO_RUNNER')
            response_status = str(response['status'])
            logging.debug('agent ' + str(agent.id) + ' reported state: ' + response_status)

            if agent.agent_state != response_status and response_status in accepted_states:
                logging.info('agent ' + str(agent.id) + ' old state ' +
                    str(agent.agent_state) + ' new state ' + response_status)
                agent.agent_state = response_status
                agent.save()
            
        agent.last_contact_attempt = time.time()
        agent.save()
    
    def check_task_duration(self, agent):

        if agent.assigned_task is None:
            return

        task_start_time = agent.assigned_task.start_time
        if time.time() - task_start_time > self.max_duration_seconds:
            logging.info('task ' + str(agent.assigned_task) + ' taking too long')
            self.terminate_task(agent, agent.assigned_task)

    def _send_request(self, req_url, json_data=None):
        try:
            r = requests.post(req_url, json=json_data, timeout=2)
            json_response = r.json()
            return (json_response, r.status_code)
        except (requests.exceptions.ConnectionError, requests.exceptions.ReadTimeout):
            logging.warning('unable to contact ' + req_url)
            return (None, None)
    
    def terminate_task(self, agent, task):
        response, _ = self._send_request(
            agent.agent_url + '/kill_run')

        if type(response) is dict:
            if 'error' in response:
                logging.error(response['error'])


def run():
    logging.basicConfig(format='%(asctime)s %(message)s', datefmt='%Y/%m/%d %I:%M:%S %p',
        level=os.getenv('LOG_LEVEL', 'INFO'))
    
    try:
        max_duration = int(os.getenv('PYMADA_MAX_TASK_DURATION_SECONDS'))
    except TypeError:
        max_duration = 60*5

    controller = Control(max_task_duration_seconds=max_duration)

    # create a default user for use for the token auth
    if len(User.objects.filter(username='pymadauser')) == 0:
        User.objects.create_user('pymadauser',None,None)
    
    command = ["gunicorn", "--bind", "0.0.0.0:8000", "api_server.wsgi"]
    file_dir = os.path.dirname(os.path.realpath(__file__))
    subprocess.Popen(command, cwd=file_dir)

    controller.run()


if __name__ == '__main__':
    run()

    '''
    tests to do:
        - idle agent gets assigned task
        - one controller loop checks assigned agent:
            - agent is finished
            - agent still running
            - agent contact lost
        - if task assigned to agent, make sure no other task assigned to same agent
        - agent runs but no result returned
        - check if last contact gets updated when django app called
        - runner crashes on agent

    '''
