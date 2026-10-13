from django.urls import path
from .views import *

urlpatterns = [
    path(route='',view=home,name='home'),
]