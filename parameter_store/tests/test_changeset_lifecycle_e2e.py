"""Tests for ChangeSet lifecycle and child entity preservation.

These tests ensure that child entities (Tags, Intent, Custom Data, Fleet Labels)
are correctly preserved, versioned, and transitioned during ChangeSet operations
such as draft creation, committing, and abandoning.
"""

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from parameter_store.models import (
    ChangeSet,
    Cluster,
    ClusterData,
    ClusterFleetLabel,
    ClusterIntent,
    ClusterTag,
    CustomDataField,
    Group,
    GroupData,
    Tag,
)

User = get_user_model()


class ChangeSetLifecycleE2ETest(TestCase):
    """End-to-end tests for ChangeSet lifecycle and child entity preservation."""

    def setUp(self):
        """Set up a superuser and authenticated client for testing."""
        self.user = User.objects.create_superuser("admin", "admin@example.com", "password")
        self.client = Client()
        self.client.login(username="admin", password="password")

    def test_multi_iteration_lifecycle(self):
        """Verifies child entities across multiple changeset iterations and history."""
        tag1 = Tag.objects.create(name="tag1")
        cdf_cluster = CustomDataField.objects.create(name="cluster_field")
        cdf_group = CustomDataField.objects.create(name="group_field")

        cs1 = ChangeSet.objects.create(name="CS1", status=ChangeSet.Status.DRAFT, created_by=self.user)
        group = Group.objects.create(name="group1", changeset_id=cs1)
        GroupData.objects.create(group=group, field=cdf_group, value="gval1", changeset_id=cs1)

        cluster = Cluster.objects.create(name="cluster1", group=group, changeset_id=cs1)
        ClusterIntent.objects.create(
            cluster=cluster,
            unique_zone_id="zone1",
            location="loc1",
            machine_project_id="p1",
            fleet_project_id="p1",
            secrets_project_id="p1",
            cluster_ipv4_cidr="1.2.3.0/24",
            services_ipv4_cidr="1.2.4.0/24",
            external_load_balancer_ipv4_address_pools="1.2.5.0/24",
            sync_repo="repo1",
            git_token_secrets_manager_name="secret1",
            cluster_version="1.0",
            changeset_id=cs1,
        )
        ClusterFleetLabel.objects.create(cluster=cluster, key="env", value="prod", changeset_id=cs1)
        ClusterData.objects.create(cluster=cluster, field=cdf_cluster, value="cval1", changeset_id=cs1)
        ClusterTag.objects.create(cluster=cluster, tag=tag1, changeset_id=cs1)
        cs1.commit(self.user)

        live_cluster = Cluster.objects.get(name="cluster1", is_live=True)
        cs2 = ChangeSet.objects.create(name="CS2", status=ChangeSet.Status.DRAFT, created_by=self.user)
        draft_v2 = live_cluster.create_draft(changeset=cs2)
        draft_v2.description = "V2 description"
        draft_v2.save()
        intent_v2 = draft_v2.intent
        intent_v2.location = "loc2"
        intent_v2.save()
        cs2.commit(self.user)

        live_cluster = Cluster.objects.get(name="cluster1", is_live=True)
        cs3 = ChangeSet.objects.create(name="CS3", status=ChangeSet.Status.DRAFT, created_by=self.user)
        draft_v3 = live_cluster.create_draft(changeset=cs3)
        draft_v3.description = "V3 description"
        draft_v3.save()
        cd_v3 = draft_v3.cluster_data.first()
        cd_v3.value = "cval3"
        cd_v3.save()
        cs3.commit(self.user)

        shared_id = live_cluster.shared_entity_id
        response = self.client.get(f"/api/v1/cluster/id/{shared_id}/history")
        self.assertEqual(response.status_code, 200)
        history_data = response.json()

        # We expect 3 items now: V3 (Live), V2 (Historical), and V1 (Historical)
        self.assertEqual(len(history_data["history"]), 3)

        # Check V3 (Live)
        v3_hist = history_data["history"][0]
        self.assertEqual(v3_hist["entity"]["description"], "V3 description")
        self.assertTrue(v3_hist["metadata"]["is_live"])
        self.assertIsNone(v3_hist["metadata"]["obsoleted_at"])

        # Check V2 (Historical)
        v2_hist = history_data["history"][1]
        self.assertEqual(v2_hist["entity"]["description"], "V2 description")
        self.assertFalse(v2_hist["metadata"]["is_live"])
        self.assertEqual(v2_hist["metadata"]["obsoleted_by_changeset_name"], "CS3")

        # Check V1 (Historical)
        v1_hist = history_data["history"][2]
        self.assertIsNone(v1_hist["entity"]["description"])
        self.assertFalse(v1_hist["metadata"]["is_live"])
        self.assertEqual(v1_hist["metadata"]["obsoleted_by_changeset_name"], "CS2")

    def test_tag_preservation_in_draft(self):
        """Verifies that ClusterTags are correctly preserved when creating a draft."""
        tag1 = Tag.objects.create(name="tag1")
        tag2 = Tag.objects.create(name="tag2")
        cs1 = ChangeSet.objects.create(name="CS1", status=ChangeSet.Status.DRAFT, created_by=self.user)
        group = Group.objects.create(name="group1", changeset_id=cs1)
        cluster = Cluster.objects.create(name="cluster1", group=group, changeset_id=cs1)

        ClusterTag.objects.create(cluster=cluster, tag=tag1, changeset_id=cs1)
        ClusterTag.objects.create(cluster=cluster, tag=tag2, changeset_id=cs1)
        cs1.commit(self.user)

        live_cluster = Cluster.objects.get(name="cluster1", is_live=True)
        self.assertEqual(live_cluster.tags.count(), 2)

        cs2 = ChangeSet.objects.create(name="CS2", status=ChangeSet.Status.DRAFT, created_by=self.user)
        draft_cluster = live_cluster.create_draft(changeset=cs2)

        self.assertEqual(draft_cluster.tags.count(), 2, "Draft cluster lost its tags!")
        ct = ClusterTag.objects.filter(cluster=draft_cluster).first()
        self.assertFalse(ct.is_live, "Draft ClusterTag should not be live")
        self.assertEqual(ct.changeset_id, cs2, "Draft ClusterTag missing changeset_id")

    def test_abandon_lingering_tags(self):
        """Verifies that abandoning a changeset removes draft ClusterTags."""
        tag1 = Tag.objects.create(name="tag1")
        cs1 = ChangeSet.objects.create(name="CS1", status=ChangeSet.Status.DRAFT, created_by=self.user)
        group = Group.objects.create(name="group1", changeset_id=cs1)
        cluster = Cluster.objects.create(name="cluster1", group=group, changeset_id=cs1)
        ClusterTag.objects.create(cluster=cluster, tag=tag1, changeset_id=cs1)
        cs1.commit(self.user)

        live_cluster = Cluster.objects.get(name="cluster1", is_live=True)
        cs2 = ChangeSet.objects.create(name="CS2", status=ChangeSet.Status.DRAFT, created_by=self.user)
        live_cluster.create_draft(changeset=cs2)

        cs2.abandon()

        lingering_tags = ClusterTag.objects.filter(is_live=False)
        self.assertEqual(
            lingering_tags.count(), 0, f"Found {lingering_tags.count()} lingering draft tags after abandon!"
        )

    def test_changeset_visibility(self):
        """Verifies that modifications to child data appear in changeset changes."""
        cdf_cluster = CustomDataField.objects.create(name="cluster_field")
        cs1 = ChangeSet.objects.create(name="CS1", status=ChangeSet.Status.DRAFT, created_by=self.user)
        group = Group.objects.create(name="group1", changeset_id=cs1)
        cluster = Cluster.objects.create(name="cluster1", group=group, changeset_id=cs1)
        ClusterData.objects.create(cluster=cluster, field=cdf_cluster, value="val1", changeset_id=cs1)
        cs1.commit(self.user)

        cs2 = ChangeSet.objects.create(name="CS2", status=ChangeSet.Status.DRAFT, created_by=self.user)
        live_cluster = Cluster.objects.get(name="cluster1", is_live=True)
        draft_cluster = live_cluster.create_draft(changeset=cs2)

        cd = draft_cluster.cluster_data.first()
        cd.value = "val2"
        cd.save()

        response = self.client.get(f"/api/v1/changeset/{cs2.id}/changes")
        self.assertEqual(response.status_code, 200)
        changes = response.json()

        self.assertEqual(len(changes["clusters"]), 1)
        self.assertEqual(changes["clusters"][0]["action"], "update")
        self.assertEqual(changes["clusters"][0]["entity"]["name"], "cluster1")
        self.assertEqual(changes["clusters"][0]["entity"]["data"]["cluster_field"], "val2")

        ClusterFleetLabel.objects.create(cluster=draft_cluster, key="newkey", value="newval", changeset_id=cs2)

        response = self.client.get(f"/api/v1/changeset/{cs2.id}/changes")
        changes = response.json()
        self.assertEqual(changes["clusters"][0]["entity"]["fleet_labels"][0]["key"], "newkey")

    def test_group_history_and_cascade(self):
        """Verifies Group history and child data preservation."""
        cdf_group = CustomDataField.objects.create(name="group_field")
        cs1 = ChangeSet.objects.create(name="CS1", status=ChangeSet.Status.DRAFT, created_by=self.user)
        group = Group.objects.create(name="group1", changeset_id=cs1)
        GroupData.objects.create(group=group, field=cdf_group, value="gval1", changeset_id=cs1)
        cs1.commit(self.user)

        cs2 = ChangeSet.objects.create(name="CS2", status=ChangeSet.Status.DRAFT, created_by=self.user)
        live_group = Group.objects.get(name="group1", is_live=True)
        draft_group = live_group.create_draft(changeset=cs2)
        draft_group.description = "New group desc"
        draft_group.save()
        cs2.commit(self.user)

        shared_id = live_group.shared_entity_id
        response = self.client.get(f"/api/v1/group/id/{shared_id}/history")
        self.assertEqual(response.status_code, 200)
        history_data = response.json()
        # Expect 2: V2 (Live) and V1 (Historical)
        self.assertEqual(len(history_data["history"]), 2)
        self.assertTrue(history_data["history"][0]["metadata"]["is_live"])
        self.assertFalse(history_data["history"][1]["metadata"]["is_live"])
        self.assertEqual(history_data["history"][1]["entity"]["data"]["group_field"], "gval1")
