import time
import json
from unittest.mock import patch
from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIRequestFactory, APIClient
from master_server.models import UrlTask, Agent, Runner, ErrorLog
import control

class MasterServerTestCase(TestCase):

    def setUp(self):

        User.objects.create_user('pymadauser', None, None)

        default_runner = Runner.objects.create(
            contents="print('hello')",
            file_name="main_runner.py",
        )
        default_runner.save()

        for i in range(3):
            agent = Agent.objects.create(
                hostname='test',
                agent_url='http://127.0.0.1:' + str(5001 + i),
                last_contact_attempt=time.time()
            )

            agent.save()
        
        for i in range(10):
            task = UrlTask.objects.create(url='http://' + str(i))
            task.save()
    
    def test_get_runner(self):
        c = APIClient()
        runner1 = c.post('/runner/1/', format='json')
        res = json.loads(runner1.content)
        assert runner1.status_code == 200
        assert 'contents' in res
        assert 'file_name' in res
    
    def test_add_runner(self):
        c = APIClient()
        runner_info = {
            'contents': 'test',
            'file_name': 'test.py',
            'file_type': 'python'
        }
        res = c.post('/register_runner/', runner_info, format='json')

        assert res.status_code == 201
    
    def test_register_agent(self):
        c = APIClient()
        res = c.post('/register_agent/', {
            'hostname': 'test-req',
            'agent_url': 'http://testagent',
            'runner_num': 1,
        }, format='json')

        assert res.status_code == 201
        json_response = res.json()
        assert 'id' in json_response
        assert json_response['runner_num'] == 1
    
    def test_reconnect_agent(self):
        c = APIClient()
        agent_details = {
            'hostname': 'reconnect-test',
            'agent_url': 'http://reconnect',
            'runner_num': 1
        }

        res = c.post('/register_agent/', agent_details, format='json')
        assert res.status_code == 201

        num_agents = len(Agent.objects.all())

        # do call to register_agent again with same details and make sure a new
        # agent doesnt get created
        res = c.post('/register_agent/', agent_details, format='json')
        assert res.status_code == 200
        assert num_agents == len(Agent.objects.all())

    def test_add_url(self):
        c = APIClient()
        res = c.post('/urls/', [{
            'url': 'http://test'
        }], format='json')

        assert res.status_code == 201
        assert 'id' in res.json()[0]

    def test_add_multiple_urls(self):
        c = APIClient()
        res = c.post('/urls/', [
                {'url': 'http://test1,'}, {'url': 'http://test2'},
                {'url': 'http://test3', 'json_metadata': '{"some":"data"}'}
            ], format='json')
        
        assert res.status_code == 201
        assert len(res.json()) == 3

    def test_get_results(self):
        c = APIClient()
        res = c.get('/urls/')

        assert res.status_code == 200
        assert type(res.json()) == list
        assert 'url' in res.json()[0]

    def test_save_results(self):
        c = APIClient()
        result_data = {
            'url': 'http://0',
            'task_result': '{"some":"data"}'
        }

        res = c.put('/urls/1/', result_data, format='json')
        assert res.status_code == 200
        assert UrlTask.objects.get(pk=1).task_result == '{"some":"data"}'

    def test_add_error_log(self):
        c = APIClient()
        err_info = {
            'message': 'this is an error',
            'reporting_agent': 1,
            'runner': ''
        }

        res = c.post('/log_error/', err_info, format='json')

        assert res.status_code == 201
        assert ErrorLog.objects.get(id=1).message == 'this is an error'

    def test_get_error_log(self):
        c = APIClient()
        res = c.get('/log_error/')

        assert res.status_code == 200
        assert type(res.json()) == list



class ControlTestCast(TestCase):
    def setUp(self):
        User.objects.create_user('pymadauser', None, None)

        default_runner = Runner.objects.create(
            contents="print('hello')",
            file_name="main_runner.py",
        )
        default_runner.save()

        for i in range(3):
            agent = Agent.objects.create(
                hostname='test',
                agent_url='http://127.0.0.1:' + str(5001 + i),
                last_contact_attempt=time.time()
            )

            agent.save()
        
        for i in range(10):
            task = UrlTask.objects.create(url='http://' + str(i))
            task.save()


    '''
    @patch('control.requests.post')
    def test_control_single_loop(self, mock_post):
        for agent in Agent.objects.all():
            assert agent.agent_state == 'NO_RUNNER'

            # assume agent has downloaded runner
            agent.agent_state = 'IDLE'
            agent.save()

        controller = control.Control()
        controller.loop()

        assert Agent.objects.all()[0].agent_state == 'ASSIGNED'

        for agent in Agent.objects.all()[1:]:
            assert agent.agent_state == 'IDLE'


        assert UrlTask.objects.all()[0].task_state == 'ASSIGNED'

        for task in UrlTask.objects.all()[1:]:
            assert task.task_state == 'QUEUED'
    '''
