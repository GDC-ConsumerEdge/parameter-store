import unfold.admin as uadmin
from django.contrib import admin
from django.contrib.auth.admin import GroupAdmin as BaseGroupAdmin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Group as DjangoGroup
from django.contrib.auth.models import User as DjangoUser

admin.site.unregister(DjangoUser)
admin.site.unregister(DjangoGroup)


@admin.register(DjangoUser)
class UserAdmin(BaseUserAdmin, uadmin.ModelAdmin):
    pass


@admin.register(DjangoGroup)
class GroupAdmin(BaseGroupAdmin, uadmin.ModelAdmin):
    pass
