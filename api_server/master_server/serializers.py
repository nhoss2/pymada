from rest_framework import serializers
from master_server.models import UrlTask, Agent, Runner, ErrorLog, Screenshot

class UrlTaskSerializer(serializers.ModelSerializer):
    task_result = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    task_state = serializers.CharField(required=False, allow_blank=True)
    json_metadata = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    fail_num = serializers.IntegerField(required=False, allow_null=True)
    start_time = serializers.FloatField(required=False, allow_null=True)
    screenshot = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model = UrlTask
        fields = ('id', 'url', 'json_metadata', 'task_state', 'task_result',
                  'assigned_agent', 'fail_num', 'start_time', 'screenshot')

class AgentSerializer(serializers.ModelSerializer):

    agent_state = serializers.CharField(required=False)
    last_contact = serializers.IntegerField(required=False)
    runner_num = serializers.IntegerField(required=False, allow_null=True)

    class Meta:
        model = Agent
        fields = ('id', 'hostname', 'agent_state', 'last_contact', 'agent_url',
                  'runner_num')
    

class RunnerSerializer(serializers.ModelSerializer):
    contents = serializers.CharField(allow_blank=True)
    custom_executable = serializers.CharField(allow_blank=True, required=False)
    dependency_file = serializers.CharField(allow_blank=True, required=False)

    class Meta:
        model = Runner
        fields = ('id', 'contents', 'file_name', 'file_type', 'custom_executable', 'dependency_file')

class ErrorLogSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = ErrorLog
        fields = ('message', 'reporting_agent', 'runner', 'timestamp')

class ScreenshotSerializer(serializers.ModelSerializer):
    screenshot = serializers.ImageField(use_url=True)

    class Meta:
        model = Screenshot
        fields = ('task', 'timestamp', 'screenshot')