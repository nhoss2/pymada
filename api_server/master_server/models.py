from django.db import models

class UrlTask(models.Model):
    task_states = (
        ('QUEUED', 'QUEUED'),
        ('ASSIGNED', 'ASSIGNED'),
        ('COMPLETE', 'COMPLETE')
    )

    url = models.TextField()
    json_metadata = models.TextField(null=True)
    task_result = models.TextField(null=True)
    task_state = models.CharField(choices=task_states, max_length=10, default='QUEUED')
    assigned_agent = models.ForeignKey('Agent', on_delete=models.CASCADE, null=True)
    fail_num = models.IntegerField(default=0)
    start_time = models.FloatField(default=0)

class Agent(models.Model):
    agent_states = (
        ('IDLE', 'IDLE'),
        ('RUNNING', 'RUNNING'),
        ('ASSIGNED', 'ASSIGNED'), # assigned task
        ('LOST', 'LOST'),
        ('NO_RUNNER', 'NO_RUNNER')
    )
    
    hostname = models.TextField()
    agent_state = models.CharField(choices=agent_states, max_length=10, default='NO_RUNNER')
    last_contact = models.IntegerField()
    agent_url = models.CharField(max_length=300)
    assigned_runner = models.ForeignKey('Runner', on_delete=models.CASCADE, null=True)

class Runner(models.Model):
    contents = models.TextField()
    file_name = models.CharField(max_length=200)
    file_type = models.CharField(max_length=200)
    custom_executable = models.CharField(max_length=200, null=True)
    dependency_file = models.TextField(null=True)

class ErrorLog(models.Model):
    message = models.TextField()
    reporting_agent = models.ForeignKey('Agent', on_delete=models.CASCADE, null=True)
    runner = models.ForeignKey('Runner', on_delete=models.CASCADE, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)