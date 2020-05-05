import os
import time
import subprocess
import logging
import asyncio
import requests
import aiohttp
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "api_server.settings")
import django
django.setup()
from master_server.models import UrlTask, Agent
from master_server.serializers import UrlTaskSerializer
from django.contrib.auth.models import User
from asgiref.sync import sync_to_async
loop = asyncio.get_event_loop()

class Control:

    def __init__(self, max_task_duration_seconds=60*5, max_task_retries=3):
        self.max_duration_seconds = max_task_duration_seconds
        self.max_task_retries = max_task_retries
        self.aiosession = None
        self.assign_locked = False

        self.agents_being_checked = []

    @sync_to_async
    def check_for_new_agents(self):
        agents = Agent.objects.filter()
        for agent in agents:
            if agent.id not in self.agents_being_checked:
                self.agents_being_checked.append(agent.id)
                loop.create_task(self.check_agent(agent.id))

        return agents

    async def check_agent(self, agent_id):
        while True:
            loop.create_task(self.check_status(agent_id))
            loop.create_task(self.check_task_duration(agent_id))

            await asyncio.sleep(2)
    
    async def run(self):
        while True:
            await self.check_for_new_agents()
            await asyncio.sleep(3)

    async def assign_task(self, agent_id):
        while self.assign_locked == True:
            await asyncio.sleep(0.05)

        self.assign_locked = True
        task_data = await find_assign_task(agent_id)
        self.assign_locked = False

        if task_data is None:
            return

        response, code = await self._send_request(
            agent_id, '/start_run',
            json_data=task_data)

        if code != 200 or code is None:
            logging.error('error from assigning task ' + str(response))
            await remove_assigned_task(agent_id)
            await update_agent_state(agent_id, 'LOST')
            return

        logging.info('agent ' + str(agent_id) + ' assigned task ' + str(task_data['id']))

    
    async def check_status(self, agent_id):
        logging.debug('checking status of ' + str(agent_id))

        response, code = await self._send_request(agent_id, '/check_runner')

        if code == 200:
            accepted_states = ('IDLE', 'RUNNING', 'NO_RUNNER')
            response_status = str(response['status'])
            logging.debug('agent ' + str(agent_id) + ' reported state: ' + response_status)

            agent_state = await get_agent_state(agent_id)
            if agent_state != response_status and response_status in accepted_states:
                logging.info('agent ' + str(agent_id) + ' old state ' +
                    str(agent_state) + ' new state ' + response_status)

                await update_agent_state(agent_id, response_status)

                if response_status == 'IDLE':
                    await self.check_for_failed_task(agent_id)
                    await self.assign_task(agent_id)

        else:
            logging.warning('changing status of ' + str(agent_id) + ' to LOST')
            await update_agent_state(agent_id, 'LOST')
            
        await update_agent_last_contact(agent_id)
    
    async def check_task_duration(self, agent_id):

        assigned_task_id = await get_agent_assigned_task(agent_id)
        if assigned_task_id is None:
            return

        task_start_time = await get_task_start_time(assigned_task_id)
        if time.time() - task_start_time > self.max_duration_seconds:
            logging.info('task ' + str(assigned_task_id) + ' (agent: ' 
                + str(agent_id) + ') taking too long')
            await self.terminate_task(agent_id)

    async def check_for_failed_task(self, agent_id):
        assigned_task_id = await get_agent_assigned_task(agent_id)
        if assigned_task_id is None:
            return

        if await get_task_state(assigned_task_id) != 'ASSIGNED':
            return

        logging.info('task {} was assigned to agent {} but no results were returned'.format(
            assigned_task_id, agent_id))
        
        await fail_task(agent_id, assigned_task_id, self.max_task_retries)

    async def terminate_task(self, agent_id):
        response, _ = await self._send_request(
            agent_id, '/kill_run')

        if type(response) is dict:
            if 'error' in response:
                logging.error(response['error'])

    async def _send_request(self, agent_id: int, url_path: str, json_data: dict = None):

        if self.aiosession is None:
            self.aiosession = aiohttp.ClientSession()

        req_url = await get_agent_url(agent_id) + url_path

        try:
            async with self.aiosession.post(req_url, json=json_data) as res:
                if res.status == 200:
                    json_response = await res.json()
                    return (json_response, res.status)
                else:
                    return (None, res.status)
        except aiohttp.ServerConnectionError:
            logging.warning('unable to contact ' + req_url)
            return (None, None)


@sync_to_async
def find_assign_task(agent_id):
    try:
        task = UrlTask.objects.filter(
            task_state='QUEUED').order_by('fail_num')[0]
    except IndexError:
        return
    
    logging.info('assigning ' + str(task.id) + ' to agent '
        + str(agent_id))
    
    task_data = UrlTaskSerializer(task).data

    agent = Agent.objects.get(pk=agent_id)

    task.assigned_agent = agent
    task.task_state = 'ASSIGNED'
    task.start_time = time.time()
    task.save()

    agent.agent_state = 'ASSIGNED'
    agent.assigned_task = task
    agent.save()

    return task_data
    
@sync_to_async
def remove_assigned_task(agent_id):
    agent = Agent.objects.get(pk=agent_id)

    if agent.assigned_task is None:
        return
    
    task = agent.assigned_task
    task.assigned_agent = None
    task.task_state = 'QUEUED'
    task.save()

    agent.assigned_task = None
    agent.agent_state = 'LOST'
    agent.start_time = 0
    agent.save()


@sync_to_async
def update_agent_state(agent_id, new_state):
    agent = Agent.objects.get(pk=agent_id)
    agent.agent_state = new_state
    agent.save()

@sync_to_async
def update_agent_last_contact(agent_id):

    agent = Agent.objects.get(pk=agent_id)
    agent.last_contact_attempt = time.time()
    agent.save()

@sync_to_async
def get_agent_url(agent_id):
    agent = Agent.objects.get(pk=agent_id)
    return agent.agent_url

@sync_to_async
def get_agent_state(agent_id):
    agent = Agent.objects.get(pk=agent_id)
    return agent.agent_state

@sync_to_async
def get_agent_assigned_task(agent_id):
    agent = Agent.objects.get(pk=agent_id)

    if agent.assigned_task == None:
        return None
    
    assigned_task_id = agent.assigned_task.id

    return assigned_task_id

@sync_to_async
def get_task_start_time(task_id):
    task = UrlTask.objects.get(pk=task_id)
    return task.start_time

@sync_to_async
def get_task_state(task_id):
    task = UrlTask.objects.get(pk=task_id)
    return task.task_state

@sync_to_async
def fail_task(agent_id, task_id, max_task_retries):
    agent = Agent.objects.get(pk=agent_id)
    assigned_task = UrlTask.objects.get(pk=task_id)

    assigned_task.fail_num += 1
    assigned_task.start_time = 0

    if assigned_task.fail_num >= max_task_retries:
        assigned_task.task_state = 'COMPLETE'
    else:
        assigned_task.task_state = 'QUEUED'

    assigned_task.assigned_agent = None
    agent.assigned_task = None
    assigned_task.save()
    agent.save()


def run():
    logging.basicConfig(format='%(asctime)s %(message)s', datefmt='%Y/%m/%d %I:%M:%S %p',
        level=os.getenv('LOG_LEVEL', 'INFO'))
    
    try:
        max_duration = int(os.getenv('PYMADA_MAX_TASK_DURATION_SECONDS'))
    except TypeError:
        max_duration = 60*5

    try:
        max_retries = int(os.getenv('PYMADA_MAX_TASK_RETRIES'))
    except TypeError:
        max_retries = 3

    controller = Control(max_task_duration_seconds=max_duration,
                         max_task_retries=max_retries)

    # create a default user for use for the token auth
    if len(User.objects.filter(username='pymadauser')) == 0:
        User.objects.create_user('pymadauser',None,None)
    
    command = ["uvicorn", "--host", "0.0.0.0", "--port", "8000", "api_server.asgi:application"]
    file_dir = os.path.dirname(os.path.realpath(__file__))
    subprocess.Popen(command, cwd=file_dir)

    loop.run_until_complete(controller.run())


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