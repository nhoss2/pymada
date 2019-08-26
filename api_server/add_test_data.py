import os
import requests
import time
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "api_server.settings")
import django
django.setup()
from master_server.models import UrlTask, Agent, Runner


def add_test_data():
    print('adding test data')

    test_script = '''
import time
from client import Client

c = Client()

task = c.get_task()

time.sleep(10)
print('task output')
c.save_result({"test":"result"})
    '''

    #test_runner = Runner(contents=test_script, file_name='test_runner.py', file_type='python')
    #test_runner.save()

    for i in range(49):
        task = UrlTask.objects.create(url='http://testsite.labs.im/#' + str(i+1))
        task.save()
    

if __name__ == '__main__':
    add_test_data()
