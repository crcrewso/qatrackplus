from django.urls import include, re_path
from . import views

urlpatterns = [
    re_path(r'^updatecombo/(?P<id>\d+)?$', views.updateCombo, name='updatecombo'),
]
