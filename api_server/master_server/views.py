import time
import os
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, authentication
from rest_framework.authtoken.models import Token
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth.models import User
from django.http import Http404, JsonResponse, HttpResponse
from PIL import Image
from master_server.models import UrlTask, Agent, Runner, ErrorLog, Screenshot
from master_server.serializers import (UrlTaskSerializer, AgentSerializer,
            RunnerSerializer, ErrorLogSerializer, ScreenshotSerializer)


''' 
Custom authentication scheme that is only active if the environment
variable 'PYMADA_TOKEN_AUTH' is set. When the environment variable is set, it
checks that the request header 'pymada_token_auth' matches the environment
variable value and if so authenticates.
'''
class EnvTokenAuth(authentication.BaseAuthentication):
    def authenticate(self, request):
        user = User.objects.get(username='pymadauser')

        if 'PYMADA_TOKEN_AUTH' not in os.environ:
            return (user, None)

        token = request.META.get('HTTP_PYMADA_TOKEN_AUTH')
        if not token:
            return None

        if token != os.environ['PYMADA_TOKEN_AUTH']:
            return None
        
        return (user, None)


class EnvTokenAPIView(APIView):
    authentication_classes = [EnvTokenAuth]
    permission_classes = [IsAuthenticated]

class UrlList(EnvTokenAPIView):

    def get(self, request, format=None):
        if 'min_id' in request.query_params and 'max_id' in request.query_params:
            min_id = request.query_params['min_id']
            max_id = request.query_params['max_id']
            urls = UrlTask.objects.filter(pk__gte=min_id, pk__lte=max_id)
        else:
            urls = UrlTask.objects.all()
        serializer = UrlTaskSerializer(urls, many=True)
        return Response(serializer.data)

    def post(self, request, format=None):
        serializer = UrlTaskSerializer(data=request.data, many=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UrlSingle(EnvTokenAPIView):

    def get_task(self, pk):
        try:
            return UrlTask.objects.get(pk=pk)
        except UrlTask.DoesNotExist:
            raise Http404
    
    def put(self, request, pk, format=None):
        task = self.get_task(pk)

        agent = task.assigned_agent

        serializer = UrlTaskSerializer(task, data=request.data)
        if serializer.is_valid():
            if agent is not None:
                agent.assigned_task = None
                agent.save()
            serializer.save(task_state='COMPLETE', end_time=time.time(), assigned_agent=None)
            return Response(serializer.data, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class UrlListLength(EnvTokenAPIView):

    def get(self, request, format=None):

        url_tasks_len = None
        if 'state' in request.query_params:
            avail_states = [s[1].lower() for s in UrlTask.task_states]
            req_state = request.query_params['state'].lower()

            if req_state in avail_states:
                url_tasks_len = len(UrlTask.objects.filter(task_state=req_state.upper()))
        else:
            url_tasks_len = len(UrlTask.objects.all())

        return JsonResponse({
            'url_tasks': url_tasks_len
        })


class RegisterAgent(EnvTokenAPIView):
    def post(self, request, format=None):
        serializer = AgentSerializer(data=request.data)
        if serializer.is_valid():
            agent_search = Agent.objects.filter(hostname=serializer.validated_data['hostname'],
                agent_url=serializer.validated_data['agent_url'])
            
            if len(agent_search) == 0:
                print('new agent', request.data)
                serializer.save(last_contact_attempt=time.time())
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            
            recorded_agent = agent_search[0]
            print('reconnect agent ' + str(recorded_agent.id))
            recorded_s = AgentSerializer(recorded_agent)
            
            return Response(recorded_s.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ListAgents(EnvTokenAPIView):
    def get(self, request, format=None):
        if 'min_id' in request.query_params and 'max_id' in request.query_params:
            min_id = request.query_params['min_id']
            max_id = request.query_params['max_id']
            agents = Agent.objects.filter(pk__gte=min_id, pk__lte=max_id)
        else:
            agents = Agent.objects.all()
        serializer = AgentSerializer(agents, many=True)
        return Response(serializer.data)

class RegisterRunner(EnvTokenAPIView):
    def get(self, request, format=None):
        runners = Runner.objects.all()
        serializer = RunnerSerializer(runners, many=True)
        return Response(serializer.data)

    def post(self, request, format=None):
        serializer = RunnerSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class RunnerSingle(EnvTokenAPIView):

    def get_runner(self, pk):
        try:
            return Runner.objects.get(pk=pk)
        except Runner.DoesNotExist:
            raise Http404

    def get(self, request, pk, format=None):
        runner = self.get_runner(pk)

        serializer = RunnerSerializer(runner)
        return Response(serializer.data)

    def post(self, request, pk, format=None):
        runner = self.get_runner(pk)

        serializer = RunnerSerializer(runner)
        return Response(serializer.data)


class ErrorLogs(EnvTokenAPIView):
    def get(self, request, format=None):
        errs = ErrorLog.objects.all()
        serializer = ErrorLogSerializer(errs, many=True)
        return Response(serializer.data)

    def post(self, request, format=None):
        serializer = ErrorLogSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class Screenshots(EnvTokenAPIView):
    def get(self, request, format=None):
        if 'min_id' in request.query_params and 'max_id' in request.query_params:
            min_id = request.query_params['min_id']
            max_id = request.query_params['max_id']
            screenshots = Screenshot.objects.filter(pk__gte=min_id, pk__lte=max_id)
        else:
            screenshots = Screenshot.objects.all()
        serializer = ScreenshotSerializer(screenshots, many=True)
        return Response(serializer.data)

    def post(self, request, format=None):
        serializer = ScreenshotSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class TaskScreenshots(EnvTokenAPIView):
    def get(self, request, task_id, format=None):
        result = Screenshot.objects.filter(task=task_id)

        if len(result) == 0:
            raise Http404

        serializer = ScreenshotSerializer(result, many=True)
        return Response(serializer.data)

class ScreenshotSingle(EnvTokenAPIView):

    def get(self, request, screenshot_id, format=None):
        screenshot_data = Screenshot.objects.get(pk=screenshot_id)

        img = screenshot_data.screenshot
        img_extension = img.name.split('.')[-1].lower()
        mime_type = ''

        if img_extension == 'png':
            mime_type = 'image/png'
        elif img_extension in ['jpg', 'jpeg']:
            mime_type = 'image/jpeg'

        return HttpResponse(img, content_type=mime_type)

class GetStats(EnvTokenAPIView):
    def get(self, request, format=None):
        urls = len(UrlTask.objects.all())
        urls_queued = len(UrlTask.objects.filter(task_state='QUEUED'))
        urls_assigned = len(UrlTask.objects.filter(task_state='ASSIGNED'))
        urls_complete = len(UrlTask.objects.filter(task_state='COMPLETE'))
        urls_failed_once = len(UrlTask.objects.filter(fail_num__gte=1))
        registered_agents = len(Agent.objects.all())

        errs = len(ErrorLog.objects.all())
        return JsonResponse({
            'urls': urls,
            'urls_queued': urls_queued,
            'urls_assigned': urls_assigned,
            'urls_complete': urls_complete,
            'urls_failed_min_once': urls_failed_once,
            'errors_logged': errs,
            'registered_agents': registered_agents,
        })
