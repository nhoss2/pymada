import time
import json
from unittest.mock import patch
from django.test import TestCase
from rest_framework.test import APIRequestFactory, APIClient
from master_server.models import UrlTask, Agent, Runner
import control

class MasterServerTestCase(TestCase):

    def setUp(self):

        default_runner = Runner.objects.create(
            contents="print('hello')",
            file_name="main_runner.py",
        )
        default_runner.save()

        for i in range(3):
            agent = Agent.objects.create(
                hostname='test',
                agent_url='http://127.0.0.1:' + str(5001 + i),
                last_contact=time.time()
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
    
    def test_register_agent(self):
        c = APIClient()
        res = c.post('/register_agent/', {
            'hostname': 'test-req',
            'agent_url': 'http://testagent'
        }, format='json')

        assert res.status_code == 200


class ControlTestCast(TestCase):
    def setUp(self):

        default_runner = Runner.objects.create(
            contents="print('hello')",
            file_name="main_runner.py",
        )
        default_runner.save()

        for i in range(3):
            agent = Agent.objects.create(
                hostname='test',
                agent_url='http://127.0.0.1:' + str(5001 + i),
                last_contact=time.time()
            )

            agent.save()
        
        for i in range(10):
            task = UrlTask.objects.create(url='http://' + str(i))
            task.save()


    @patch('control.requests.post')
    def test_control_assign(self, mock_post):
        for agent in Agent.objects.all():
            assert agent.agent_state == 'IDLE'
        
        controller = control.Control()
        controller.loop()

        assert Agent.objects.all()[0].agent_state == 'ASSIGNED'

        for agent in Agent.objects.all()[1:]:
            assert agent.agent_state == 'IDLE'


        assert UrlTask.objects.all()[0].task_state == 'ASSIGNED'

        for task in UrlTask.objects.all()[1:]:
            assert task.task_state == 'QUEUED'