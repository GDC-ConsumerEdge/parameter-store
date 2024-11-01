from django.db import models


class Group(models.Model):
    name = models.CharField(max_length=30, null=False)
    description = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return self.name


class Cluster(models.Model):
    name = models.CharField(max_length=30, null=False)
    description = models.CharField(max_length=255, null=True, blank=True)
    group = models.ForeignKey(Group, on_delete=models.CASCADE)

    def __str__(self):
        return self.name


class Tag(models.Model):
    name = models.CharField(max_length=30, null=False)
    description = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return self.name


class ClusterTag(models.Model):
    cluster = models.ForeignKey(Cluster, on_delete=models.CASCADE)
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE)

    def __str__(self):
        return f'{self.cluster.name} - {self.tag.name}'


class ClusterIntent(models.Model):
    cluster = models.ForeignKey(Cluster, on_delete=models.CASCADE)
    zone_id = models.CharField(max_length=30, null=False)
    zone_name = models.CharField(max_length=100, null=True, blank=True)
    machine_project_id = models.CharField(max_length=30, null=False)
    fleet_project_id = models.CharField(max_length=30, null=False)
    location = models.CharField(max_length=30, null=False)
    node_count = models.IntegerField(null=False)
    cluster_ipv4_cidr = models.CharField(max_length=18, null=False)
    services_ipv4_cidr = models.CharField(max_length=18, null=False)
    external_load_balancer_ipv4_address_pools = models.CharField(max_length=18, null=False)
    sync_repo = models.CharField(max_length=128, null=False)
    sync_branch = models.CharField(max_length=50, null=False)
    sync_dir = models.CharField(max_length=50, null=False)
    secrets_project_id = models.CharField(max_length=30, null=False)
    git_token_secrets_manager_name = models.CharField(max_length=255, null=False)
    cluster_version = models.CharField(max_length=30, null=False)
    maintenance_window_start = models.TimeField(null=True, blank=True)
    maintenance_window_end = models.CharField(max_length=30, null=True, blank=True)
    maintenance_window_recurrence = models.CharField(max_length=128, null=True, blank=True)
    subnet_vlans = models.CharField(max_length=128, null=False)
    recreate_on_delete = models.BooleanField(default=False)

    def __str__(self):
        return self.cluster.name


class ClusterFleetLabel(models.Model):
    cluster = models.ForeignKey(Cluster, on_delete=models.CASCADE)
    label = models.CharField(max_length=63, null=False)

    def __str__(self):
        return f'{self.cluster.name} - {self.label}'


class Role(models.Model):
    member = models.CharField(max_length=100, null=False)
    create = models.BooleanField(null=False)
    read = models.BooleanField(null=False)
    update = models.BooleanField(null=False)
    delete = models.BooleanField(null=False)

    class Meta:
        abstract = True


class ClusterRole(Role):
    cluster = models.ForeignKey(Cluster, on_delete=models.CASCADE)


class GroupRole(Role):
    group = models.ForeignKey(Group, on_delete=models.CASCADE)


class GlobalRole(Role):
    pass

# class CustomFields(models.Model):
#     table_id = models.CharField(max_length=50, null=False)
#     name = models.CharField(max_length=50, null=False)
#     type = models.CharField(max_length=50, null=False)
#     length = models.IntegerField(null=True, blank=True)
