import requests
import os

class Client(object):

    def __init__(self, host_url=None):
        if host_url is not None:
            self.host = host_url
            return

        if 'AGENT_PORT' in os.environ:
            self.host = 'http://localhost:' + os.environ['AGENT_PORT']

        self.host = 'http://localhost:5001'

    def get_task(self):
        req_url = self.host + '/get_task'
        r = requests.post(req_url)
        return r.json()
    
    def save_result(self, result):
        req_url = self.host + '/save_results'
        r = requests.post(req_url, json=result)
        return r.json()

    def add_url(self, url, json_metadata=None):
        req_url = self.host + '/add_url'
        r = requests.post(req_url, json={'url': url, 'json_metadata': json_metadata})
        return r.json()