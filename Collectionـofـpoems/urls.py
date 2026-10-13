from django.urls import path
from .views import *

urlpatterns = [
    path('',view=list_view,name='poem')
]