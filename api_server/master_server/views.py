import time
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.http import Http404
from master_server.models import UrlTask, Agent, Runner, ErrorLog
from master_server.serializers import UrlTaskSerializer, AgentSerializer, RunnerSerializer, ErrorLogSerializer

class UrlList(APIView):
    def get(self, request, format=None):
        urls = UrlTask.objects.all()
        serializer = UrlTaskSerializer(urls, many=True)
        return Response(serializer.data)

    def post(self, request, format=None):
        print(request.data)
        serializer = UrlTaskSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    '''
    def put(self, request, format=None):
        serializer = UrlTaskSerializer(data=request.data)
        if serializer.is_valid() and 'id' in serializer.data:
            url_task = UrlTask.objects.get(pk=serializer.data['id'])
            print(url_task, type(url_task))
            update = UrlTaskSerializer(url_task, data=request.data)
            update.is_valid()
            update.save()
            return Response(update.data)
        
        print(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    '''

class UrlSingle(APIView):

    def get_task(self, pk):
        try:
            return UrlTask.objects.get(pk=pk)
        except UrlTask.DoesNotExist:
            raise Http404

    def put(self, request, pk, format=None):
        task = self.get_task(pk)

        serializer = UrlTaskSerializer(task, data=request.data)
        if serializer.is_valid():
            serializer.save(task_state='COMPLETE')
            return Response(serializer.data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class RegisterAgent(APIView):

    def get(self, request, format=None):
        agents = Agent.objects.all()
        serializer = AgentSerializer(agents, many=True)
        return Response(serializer.data)

    def post(self, request, format=None):
        request.data['last_contact'] = int(time.time())
        print('new agent', request.data)
        serializer = AgentSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class RegisterRunner(APIView):
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

class RunnerSingle(APIView):

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
    

class ErrorLogs(APIView):
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