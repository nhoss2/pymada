from django.urls import path
from master_server import views

urlpatterns = [
    path('urls/', views.UrlList.as_view()),
    path('urls/<int:pk>/', views.UrlSingle.as_view()),
    path('register_agent/', views.RegisterAgent.as_view()),
    path('register_runner/', views.RegisterRunner.as_view()),
    path('runner/<int:pk>/', views.RunnerSingle.as_view()),
    path('log_error/', views.ErrorLogs.as_view()),
    path('stats/', views.GetStats.as_view()),
    path('screenshots/', views.Screenshots.as_view()),
    path('task_screenshots/<int:task_id>/', views.TaskScreenshots.as_view()),
    path('screenshots/<int:screenshot_id>/', views.ScreenshotSingle.as_view())
]