route = 'something'
k3s_token = 'aaa'
from http.server import HTTPServer, BaseHTTPRequestHandler
import os 
import subprocess

def run_install(bind_address):
    print('bootstrap.py token', k3s_token, 'address', bind_address)
    command = 'K3S_CLUSTER_SECRET=' + k3s_token + ' K3S_KUBECONFIG_OUTPUT=/kubeconfig.yaml' +\
        ' INSTALL_K3S_VERSION=v0.6.1 sh /k3s_install.sh --node-label=pymada-role=master'
    print('bootstrap.py running', command)

    subprocess.run(command, shell=True)


class Server(BaseHTTPRequestHandler):
    def do_GET(self):
        self.respond()

    def respond(self):
        status = 200
        content_type = 'text/plain'

        self.send_response(status)
        self.send_header('Content-type', content_type)
        self.end_headers()

        path_elems = self.path.split('/')
        print(path_elems)

        if path_elems[1] == route:

            print('route match')

            run_install(path_elems[2])

            kubeconfig_path = '/kubeconfig.yaml'

            if os.path.exists(kubeconfig_path):
                with open('/kubeconfig.yaml') as conf:
                    self.wfile.write(bytes(conf.read(), 'UTF-8'))
                    self.wfile.close()

                import sys
                sys.exit(0)
            else:
                self.wfile.write(bytes('kube conf doesnt exist', 'utf-8'))
        else:
            self.wfile.write(bytes('', 'utf-8'))

        #httpd.shutdown()

if __name__ == '__main__':
    httpd = HTTPServer(('0.0.0.0', 30200), Server)

    try:
        print('starting server')
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass

    httpd.server_close()
