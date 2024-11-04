#from django.contrib import admin
from django.urls import path
from . import views  # Assuming your views are defined in a file named views.py

urlpatterns = [
#    path("admin/", admin.site.urls),
    path('process_form/', views.process_form, name='process_form'),
]