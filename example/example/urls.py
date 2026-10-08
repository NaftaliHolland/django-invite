"""
URL configuration for example project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
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
from django.urls import path
from users.views import invite_user, accept_invitation_view, revoke_invitation_view, expire_invitation_view, invitation_list_view

urlpatterns = [
    path('admin/', admin.site.urls),
    path("invitations/new", invite_user, name="invite_user"),
    path(
        "invitations/accept/<str:token>/",
        accept_invitation_view,
        name="accept_invitation",
    ),
    path(
        "invitations/<str:token>/revoke/",
        revoke_invitation_view,
        name="revoke_invitation",
    ),
    path(
        "invitations/<str:token>/expire/",
        expire_invitation_view,
        name="expire_invitation",
    ),
    path("invitations/", invitation_list_view, name="invitations"),
]
