"""
URL configuration for mysite project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path, include  # Import include for handling app URLs

urlpatterns = [
    path('admin/', admin.site.urls),

    # Include URL patterns from your applications
    path('', include('hello.urls')),  # Assuming hello.urls exists in the 'hello' app
    path('', include('manager.urls')),  # Assuming manager.urls exists in the 'manager' app

    # Other project-level URL patterns (if any)
    # path('some_other_url/', your_view_function, name='some_other_name'),
]

'''
from django.contrib import admin
from django.urls import path
from . import hello_app_views  # Import views from hello application
from . import manager_app_views  # Import views from manager application

urlpatterns = [
    path('admin/', admin.site.urls),

    # Include URL patterns for your applications (without separate urls.py)
    path('hello/', hello_app_views.hello_world, name='hello_world'),
    path('process_form/', manager_app_views.process_form, name='process_form'),

    # Other project-level URL patterns (if any)
]
urlpatterns = [
    path("admin/", admin.site.urls), path('', views.hello_world, name='hello_world'),
    path('process_form/', hello_app_views.process_form, name='process_form'),
]
'''