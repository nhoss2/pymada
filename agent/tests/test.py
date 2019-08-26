import unittest
from unittest.mock import Mock, patch
import agent_server
import os
import time

class AgentTest(unittest.TestCase):

    @patch('agent_server.requests.post')
    def setUp(self, mock_post):
        mock_post.return_value.json.return_value = {
            "contents":"print('test')",
            "file_name":"test_run_script.py",
            "file_type":"python",
            "custom_executable":None
        }

        file_dir = os.path.dirname(os.path.realpath(__file__))
        self.runner_path = os.path.join(file_dir, 'test_run_script.py')

        if os.path.exists(self.runner_path):
            os.remove(self.runner_path)

        self.agent = agent_server.Agent(
            'http://127.0.0.1:8000', runner_write_path=self.runner_path)

    @patch('agent_server.requests.post')
    def test_agent_get_task(self, mock_post):
        mock_post.return_value.json.return_value = {"url":"something"}
        self.agent.get_task_from_master()

        assert type(self.agent.task) is dict
    
    def test_agent_register(self):
        assert self.agent.runner is not None
    
    def test_write_runner_file(self):
        assert os.path.exists(self.runner_path)

    def tearDown(self):
        if os.path.exists(self.runner_path):
            os.remove(self.runner_path)

class RunnerTest(unittest.TestCase):

    def setUp(self):
        self.base_dir = os.path.dirname(os.path.realpath(__file__))
        self.states = agent_server.Runner.states

    def test_run(self):
        run_script = os.path.join(self.base_dir, 'fake_runner.py')
        runner = agent_server.Runner(run_script)
        runner.run()
        seconds = 0.0
        while runner.get_status() == self.states.RUNNING:
            time.sleep(0.5)
            seconds += 0.5
            if seconds > 2:
                self.fail('fake runner took more than 2 seconds')
        
    def test_kill(self):
        run_script = os.path.join(self.base_dir, 'fake_runner_long.py')
        runner = agent_server.Runner(run_script)
        runner.run()
        runner.kill()

        seconds = 0.0
        while runner.get_status() == self.states.RUNNING:
            time.sleep(0.2)
            seconds += 0.2
            if seconds > 2:
                self.fail('fake runner long took more than 2 seconds to kill')

        assert runner.get_status() is self.states.IDLE
        assert runner.last_run_code is not None
    
    def test_multiple_runs(self):
        run_script = os.path.join(self.base_dir, 'fake_runner.py')
        runner = agent_server.Runner(run_script)
        runner.run()
        seconds = 0.0
        while runner.get_status() == self.states.RUNNING:
            time.sleep(0.2)
            seconds += 0.2
            if seconds > 2:
                self.fail('fake runner took more than 2 seconds')
        
        assert runner.last_run_code == 0
        seconds = 0.0
        runner.run()

        while runner.get_status() == self.states.RUNNING:
            time.sleep(0.2)
            seconds += 0.2
            if seconds > 2:
                self.fail('fake runner took more than 2 seconds')
    