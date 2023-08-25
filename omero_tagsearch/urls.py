from django.urls import re_path
from . import views

urlpatterns = [
    # index 'home page' of the webtagging app
    re_path(r"^$", views.index, name="tagsearch"),
    # index 'home page' of the webtagging app
    re_path(r"^images$", views.tag_image_search, name="wtsimages"),
]
