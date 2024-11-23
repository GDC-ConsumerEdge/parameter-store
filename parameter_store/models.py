from django.db import models


class Group(models.Model):
    name = models.CharField(max_length=30, blank=False, unique=True, null=False)
    description = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return self.name


class Cluster(models.Model):
    name = models.CharField(max_length=30, blank=False, unique=True, null=False)
    description = models.CharField(max_length=255, null=True, blank=True)
    group = models.ForeignKey(Group, on_delete=models.DO_NOTHING)
    data = models.JSONField(null=True, blank=True, default=dict)
    tags = models.ManyToManyField(
        'Tag',
        through='ClusterTag',
        related_name='clusters',
    )

    def __str__(self):
        return self.name


class Tag(models.Model):
    name = models.CharField(max_length=30, blank=False, unique=True, null=False,
                            verbose_name='tag name')
    description = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return self.name


class ClusterTag(models.Model):
    cluster = models.ForeignKey(Cluster, on_delete=models.CASCADE)
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE)

    def __str__(self):
        return f'{self.cluster.name} - {self.tag.name}'

    class Meta:
        verbose_name = 'Cluster Tag'
        verbose_name_plural = 'Cluster Tags'


class ClusterIntent(models.Model):
    cluster = models.OneToOneField(Cluster, on_delete=models.CASCADE)
    zone_id = models.CharField(max_length=30, null=False, verbose_name='Zone ID')
    zone_name = models.CharField(max_length=100, null=True, blank=True, )
    location = models.CharField(max_length=30, null=False)
    machine_project_id = models.CharField(max_length=30, null=False,
                                          verbose_name='Machine Project ID')
    fleet_project_id = models.CharField(max_length=30, null=False, verbose_name='Fleet Project ID')
    secrets_project_id = models.CharField(max_length=30, null=False)
    node_count = models.IntegerField(null=False, default=3)
    cluster_ipv4_cidr = models.CharField(max_length=18, null=False,
                                         verbose_name='Cluster IPv4 CIDR')
    services_ipv4_cidr = models.CharField(max_length=18, null=False,
                                          verbose_name='Services IPv4 CIDR')
    external_load_balancer_ipv4_address_pools = models.CharField(
        max_length=180, null=False, verbose_name='External Load Balancer IPv4 Address Pools')
    sync_repo = models.CharField(max_length=128, null=False, help_text='This is the full URL to a '
                                                                       'Git repository')
    sync_branch = models.CharField(max_length=50, null=False, default='main',
                                   help_text='For; example: "main" or "master"')
    sync_dir = models.CharField(max_length=50, null=False,
                                default=f'hydrated/clusters/{cluster.name}', )
    git_token_secret_manager_name = models.CharField(max_length=255, null=False)
    cluster_version = models.CharField(max_length=30, null=False,
                                       help_text='This is the GDCC control plane version, '
                                                 'i.e. "1.7.1"')
    maintenance_window_start = models.DateTimeField(null=True, blank=True)
    maintenance_window_end = models.DateTimeField(null=True, blank=True)
    maintenance_window_recurrence = models.CharField(max_length=128, null=True, blank=True)
    subnet_vlans = models.CharField(max_length=128, null=True)
    recreate_on_delete = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Cluster Intent Data'
        verbose_name_plural = 'Cluster Intent Data'

    def __str__(self):
        return self.cluster.name


class ClusterFleetLabel(models.Model):
    cluster = models.ForeignKey(Cluster, on_delete=models.CASCADE)
    key = models.CharField(max_length=63, blank=False, null=False)
    value = models.CharField(max_length=63, blank=False, null=False)

    class Meta:
        verbose_name = 'Cluster Fleet Label'
        verbose_name_plural = 'Cluster Fleet Labels'

        constraints = [
            models.UniqueConstraint(fields=['cluster', 'key'], name='unique_cluster_key')
        ]

    def __str__(self):
        return f'{self.cluster.name} - "{self.key}" = "{self.value}"'

# class Role(models.Model):
#     member = models.CharField(max_length=100, null=False)
#     create = models.BooleanField(null=False)
#     read = models.BooleanField(null=False)
#     update = models.BooleanField(null=False)
#     delete = models.BooleanField(null=False)
#
#     class Meta:
#         abstract = True
#
#
# class ClusterRole(Role):
#     cluster = models.ForeignKey(Cluster, on_delete=models.CASCADE)
#
#
# class GroupRole(Role):
#     group = models.ForeignKey(Group, on_delete=models.CASCADE)
#
#
# class GlobalRole(Role):
#     pass

# class CustomFields(models.Model):
#     table_id = models.CharField(max_length=50, null=False)
#     name = models.CharField(max_length=50, null=False)
#     type = models.CharField(max_length=50, null=False)
#     length = models.IntegerField(null=True, blank=True)
