# EPS Data Integrity: Provisional Changes and ChangeSet-Driven Workflow System

**Self link:** none
**Visibility**: Public
**Authors**: [Paul Durivage](mailto:durivage@google.com)
**Reviewers:**
  * [Katie Hsu](mailto:katiehsu@google.com)
  * [Kodanda Rama](mailto:kodrama@google.com)
  * [Jimit Rangras](mailto:jimitrangras@google.com)
  * [Ben Chapman](mailto:benchapman@google.com)
**Last major revision**: September 30, 2025
**Technical design document:** None

# Objective

The primary objective of this feature is to introduce a change management system into the Edge Parameter Store (EPS). This system allows users to prepare and group data modifications (creations, updates, deletions) in a provisional or "draft" state without immediately affecting the live system. These grouped changes, referred to as `ChangeSets`, can then be explicitly "committed" by a user, at which point they become live.

This feature aims to solve the following problems:

*   **Immediate impact of changes:** Prevent accidental or incorrect changes from instantly becoming live and potentially impacting edge clusters or dependent processes.
*   **Lack of coordinated updates:** Enable users to make related changes that should only become active together as part of a single, atomic event.

The goals are to:

*   Introduce a staging area for data modifications.
*   Allow grouping of related changes into `ChangeSets`.
*   Provide controlled promotion of changes from `draft` to `committed` state.
*   Ensure data integrity during the change process using a locking mechanism.
*   Improve the user workflow by offering a more controlled and potentially auditable process for making significant changes.
*   Maintain API consistency by ensuring standard queries return only committed (final) data by default.

# Background

The Edge Parameter Store (EPS) serves as a centralized repository for data that was historically managed in disparate CSV files referred to as "Sources of Truth" (SoTs). This data is critical for various downstream tools and processes.

Key consumers of EPS data include:

*   **Cluster Provisioner:** This tool relies on `ClusterIntent` data stored in EPS to carry out the provisioning and initial setup of new edge clusters.
*   **Hydration and Rollout Manager (HRM):** HRM utilizes data from EPS, such as `ClusterData` and `GroupData`, to generate Kubernetes manifests tailored for specific clusters or groups of clusters. These manifests define the desired state of applications and configuration deployed to the edge.

Previously, when this configuration data resided in Git, changes were intrinsically localized. Downstream tools like HRM could detect and act upon these changes immediately after a cohesive, atomic unit of change was committed to the repository.

With the centralization of this data into EPS, the explicit unit of change no longer occurs through a Git pull or merge request. Consequently, a mechanism is required to group, stage, and explicitly introduce data changes. The introduction of `ChangeSets` is designed to bridge this gap, providing a clear workflow to make new data available for consumption by tools like the cluster provisioner and HRM. This will act as the foundation of an evented notification system which acts upon state change within EPS by external systems and tools.

# Definitions

*   `ChangeSet`: A collection of data modifications (creations, updates, or deletions) made by a user or users, staged together. This is the central object for managing changes.
*   States of a `ChangeSet`:
    *   `draft`: The `ChangeSet` is actively being worked on or is ready for commit. Its associated changes are provisional and not yet live. Draft `ChangeSets` can be modified, have more changes added to them, be coalesced into another `draft` `ChangeSet`, or be discarded.
    *   `committed`: The `ChangeSet` has been finalized by a user. All its associated changes are now live in EPS. A `committed` `ChangeSet` is immutable in terms of the changes it represents.
*   Top-level Shared Entity (or Top-level Entity): The primary, independent data entities that are directly managed and versioned within a `ChangeSet`. In the context of EPS, these are `Cluster` and `Group`. These entities have a `shared_entity_id` and can have associated child data that is versioned along with them.
*   `shared_entity_id`: A persistent, unique identifier (i.e. UUID) assigned to a single *top-level shared entity* (a specific `Cluster` or `Group`) when it is first created. All subsequent versions or states (`live`, `draft`, `historical`) of that same shared entity within its table will share this `shared_entity_id`. This ID serves as the stable anchor for that entity.
*   Provisional Data: The state of data entities (both top-level and related child data) in its draft state within an uncommitted `ChangeSet.`
    *   For top-level entities this data is represented by specific rows within their main tables, marked with a `changeset_id` (pointing to the draft `ChangeSet`), `is_live=False`, and the appropriate `shared_entity_id`.
    *   For related child data (e.g., `ClusterData`), draft versions are new rows linked to the *`draft` parent row's `id`*, also marked with `changeset_id` and `is_live=False`.
    *   By default, this data is not visible through standard API queries.
*   Live/Committed/Finalized Data: The state of data entities as reflected in the system, resulting from all `committed` `ChangeSets`.
    *   For top-level entities, this is represented by specific rows within their main tables, marked with `is_live=True`, `changeset_id=NULL`, and the appropriate `shared_entity_id`.
    *   Only one top-level entity with the same `shared_entity_id` may set `is_live=True`.
    *   For related child data, live versions are rows linked to the *live parent row's `id`*, marked with `is_live=True` and `changeset_id=NULL`.
    *   This is the data visible through standard API queries.
*   Historical Data:
    *   For top-level entities, these are rows within their main tables that were previously live, now marked with `is_live=False`, `changeset_id=NULL`, `obsoleted_by_changeset` populated, and the appropriate `shared_entity_id`.
    *   For related child data, these are rows linked to a *historical parent row's `id`*, marked with `is_live=False` and `changeset_id=NULL`.
    *   These are retained to ensure stability of their primary key (`id`) for any internal historical references, but are not considered active or draft.
*   Lock: A mechanism to prevent the `is_live=True` version of a specific top-level shared entity from being concurrently targeted for modification (i.e., having a new draft version created from it) by more than one `draft` `ChangeSet` at a time. This is indicated by an `is_locked=True` flag and the `locked_by_changeset` field on the `is_live=True` row of the top-level entity.
*   Commit: The action a user takes to transition a `ChangeSet` from `draft` to `committed`, thereby applying all its provisional changes to make them the live data state. This involves marking the draft rows (both top-level and child) as live and the previous live rows as historical.
*   Discard: The action of deleting a `draft` `ChangeSet`. This action will also remove all provisional data rows (both top-level and child) associated exclusively with that `ChangeSet`.
*   Coalesce: The action of merging the provisional changes (any draft row) from one or more `draft` `ChangeSet`(s) into another `draft` `ChangeSet`. The source `ChangeSet`(s) is to be discarded after its changes are successfully moved.
    *   `Committed` ChangeSets cannot be coalesced.

# Critical User Journeys

The primary actor for these journeys is the *EPS Data Administrator*, who interacts with the system via the EPS Core UI.

## Initiating Changes and Working with an Active ChangeSet

As an EPS Data Administrator, I need to select an existing draft `ChangeSet` to work on, or create a new `ChangeSet` to group my upcoming modifications.

As an EPS Data Administrator, I need the ability to view all the objects (provisional data rows for top-level entities and their related child data) in scope of my active draft `ChangeSet` including their type (e.g., `Cluster`, `GroupData`), with the ability to click through to edit each individual provisional object.

As an EPS Data Administrator, if I attempt to modify data without an active `ChangeSet`, I need the system to guide me to create or select one, or automatically create one for me.

## Modifying Existing Data

As an EPS Data Administrator, I need to select one or more existing live top-level entities (e.g., `Clusters`, `Groups`) and initiate their modification (create a draft version of the entity and its related data) within my active draft `ChangeSet`.

As an EPS Data Administrator, I need to edit the attributes and related data (e.g., `ClusterData`, `GroupData`) of entities that are part of my active draft `ChangeSet` (i.e., edit their draft row versions).

As an EPS Data Administrator, I need to edit many `Clusters` (or `Groups`) and their related data at once within the context of a single `ChangeSet`.

## Adding New Data

As an EPS Data Administrator, I need to add one or more new `Clusters` (including their associated `ClusterData, Tags, FleetLabels`) as draft versions into my active `draft ChangeSet`.

As an EPS Data Administrator, I need to add new `Groups` (including their `GroupData`) as draft versions into my active `draft ChangeSet`.

As an EPS Data Administrator, I need to add custom data values (new values for `ClusterData` or `GroupData`) to new or existing entities' draft versions within my `ChangeSet` (`CustomDataFields` are always global in scope and are never in a `draft` state).

## Managing ChangeSet Lifecycle

As an EPS Data Administrator, I need to view a clear summary of all provisional changes (new entities, modified entities represented by their draft versions) contained within my active `draft ChangeSet`.

As an EPS Data Administrator, I need to combine (coalesce) multiple `draft ChangeSets` into a single `draft ChangeSet` to consolidate related work.

As an EPS Data Administrator, I need to commit my `draft ChangeSet`, making all its provisional changes live in the system and releasing any locks.

As an EPS Data Administrator, I need to discard a `draft ChangeSet` if the planned changes are no longer needed, ensuring no live data is affected and locks are released.

## Understanding System State

As an EPS Data Administrator, I need to clearly see if a live top-level entity is locked (i.e. `is_locked=True`) and be prevented from creating another draft version from it until the lock is released.

# Requirements

1.  **Staging of Changes**: The system allows users to stage changes for top-level entities (e.g., `Group, Cluster`) and their related data (e.g., `GroupData, ClusterData, ClusterFleetLabels, ClusterTags`), including the creation of new top-level entities and their associated data, without these changes being immediately live.
    *   Top-level entity draft rows have `is_live=False` and `changeset_id` populated.
    *   Related child data draft rows are linked to the parent draft row's `id` and also have `is_live=False` and `changeset_id` populated.
2.  **`ChangeSet` Entity**: A `ChangeSet` data entity is used to group provisional changes.
3.  **`ChangeSet` States**: `ChangeSets` have at least two states: `draft` and `committed`.
4.  **Discarding `ChangeSets`**: Users can discard (delete) a `draft` `ChangeSet`, which also removes any provisional data rows (both top-level and child, where is_live=False and linked to that ChangeSet) associated exclusively with that `ChangeSet`.
5.  **Automatic `ChangeSet` Creation**: If a user initiates changes on a live top-level entity without an active `ChangeSet` context, a new `ChangeSet` in the `draft` state is automatically created for them.
6.  **Object Locking**: The live version (`is_live=True` row) of a top-level entity that is being modified within a `draft` `ChangeSet` is locked (indicated by `is_locked=True` and `locked_by_changeset` populated) to prevent concurrent draft creations from it by other `ChangeSets` until the `ChangeSet` is committed or discarded.
7.  **Viewing Provisional Changes**: Users can view the provisional changes (draft data rows for top-level entities and their children) associated with a `draft` `ChangeSet`. This includes a summarized list of all entities within the `ChangeSet` and the ability to navigate to edit individual provisional entities.
8.  **Committing `ChangeSets`**: Users can "commit" a `draft` `ChangeSet`. This action transitions the `ChangeSet` to the `committed` state. For each top-level entity and its related data in the `ChangeSet`:
    *   Associated draft rows become the live data state (by updating their `is_live` status to `True` and nullifying `changeset_id`).
    *   Previous live rows are marked as historical (by setting `is_live=False`).
    *   Any locks on the top-level entities are released.
9.  **Coalescing `ChangeSets`**: Users can coalesce multiple `draft` `ChangeSets` into a single `draft` `ChangeSet`.
10. **API Behavior**: Standard read API queries, by default, only return live/final data (rows where `is_live=True` for both top-level entities and their children) and do not include provisional data from `draft` `ChangeSets` or historical data.
11. **Non-Interactive Migrations**: Changes to any existing models do not introduce Django migrations that require user input at migration execution time. All new fields have appropriate `null=True` or `default` values.

# Out of Scope

*   **Notifications:** A notification system is out of scope and will be addressed in a subsequent release.
*   Complex approval or formal review workflows for `ChangeSets`.
*   A direct "revert" feature for a `committed` `ChangeSet`. Changes must be “reverted” by creating a new `ChangeSet`.
*   Physical deletion of historical rows (beyond draft row deletion upon discard).
*   Advanced diffing capabilities in the UI between provisional data and current live data.
*   Specific query mechanisms for external apps/systems to view *provisional* data.
*   Explicit UI features for displaying or restoring historical data.

# Technical Design

## ChangeSet Model

*   A Django model named `ChangeSet` is used to group changes.
*   Fields include: `id`, `name`, `description`, `status`, `created_by`, `created_at`, `updated_at`, `committed_at`, `committed_by`.

## Provisional Data Storage: "Shadow Rows" / "Version Status" in the Same Table

### Strategy

Instead of separate provisional tables, specific fields were added to existing data models to manage different states (live, draft, historical) of a shared entity and its related data within their respective same tables.

### Model Modifications

#### Top-Level Versioned Entities

This applies to the `Cluster` and `Group` models. These models were augmented with the following fields:

*   `shared_entity_id`: A `UUIDField` that serves as the common ID for all rows in this table that represent different versions or states (e.g., live, draft, historical) of the *same single shared entity*.
*   `is_live`: A `BooleanField` (indexed). For a unique `shared_entity_id`, exactly one row can have `is_live = True`.
*   `is_locked`: A `BooleanField` (`default=False`, indexed). `True` on an `is_live=True` row if it has an active draft.
*   `changeset_id`: A nullable `ForeignKey` to the `ChangeSet` model. Populated if the row is a draft version (`is_live=False`). `NULL` for live (`is_live=True`) or historical (`is_live=False`) rows.
*   `locked_by_changeset`: A nullable `ForeignKey` to the `ChangeSet` model. Populated on an `is_live=True` row to indicate which `ChangeSet` holds its active draft.
*   `obsoleted_by_changeset`: A nullable `ForeignKey` to the `ChangeSet` model. Set on a previously live row when a commit makes it historical, indicating which `ChangeSet` replaced it.
*   `draft_of`: A nullable `ForeignKey` to `self`. This links a draft row back to the live row it was created from.
*   **Foreign Key Relationships**: Foreign keys from other tables (e.g., `Cluster.group`) point to the primary key (`id`) of the top-level entity's specific row. The logic within the `commit_changeset` admin action is responsible for re-pointing these foreign keys from the old live row to the newly promoted draft row to maintain relational integrity.

#### Related Child Entities

This applies to `ClusterData`, `GroupData`, `ClusterFleetLabels`, `ClusterTags`, `ClusterIntent`. These models are versioned in conjunction with their parent.

*   `is_live`: A `BooleanField` (indexed, `default=False`). `True` if this child data row belongs to a live parent version and is itself live.
*   `changeset_id`: A nullable `ForeignKey` to the `ChangeSet` model. Populated if this child data row is part of a draft version of its parent.
*   A `ForeignKey` to the `id` (row primary key) of the parent entity's specific version row (e.g., `cluster_id` FK to `Cluster.id`). This links the child data to a specific version of its parent.
*   These models do **not** have their own `shared_entity_id`. Their versioning identity is derived from their parent version.

## Django Admin Integration Plan

#### `ChangeSet` Management & Active Context

*   A standard `ModelAdmin` for `ChangeSets` allows viewing, and custom actions for **committing**, **discarding**, and **coalescing**.
*   The user's active draft `ChangeSet` is stored in the user's session. This is managed by the `get_or_create_changeset` utility function. If no `ChangeSet` is active, data-modifying actions on live entities will automatically create one.


#### Modifying Live (unlocked) entities (Creating a Draft Version)

*   On live, top-level entity `ModelAdmin` list views, locked entities (where `is_locked=True`) are visually indicated.
*   A custom admin action "Create Draft & Edit" is available for top-level entities.
*   In addition to the admin action, the system also intercepts direct `save` attempts on a live, unlocked entity. The `response_change` method in the `ChangeSetAwareAdminMixin` handles this by automatically creating a draft, saving the user's changes to it, and redirecting them to the new draft's edit page.
*   This action:
    *   Verifies an active `draft` `ChangeSet` context.
    *   Checks the lock status of the live top-level entity.
    *   Creates a new draft row for the top-level entity (copies data, sets `is_live=False`, `changeset_id`, `draft_of`, etc.).
    *   Updates the original live top-level entity row: sets `locked_by_changeset` and `is_locked=True`.
    *   **Deep copies child data:** For each child entity related to the live top-level entity row, a new child draft row is created, linked to the new parent draft row.
    *   Redirects the user to the admin change form for the *top-level draft entity row*.

#### Admin for Draft Rows

*   `ModelAdmin` classes are configured to allow editing of draft rows.
*   Forms for draft top-level entities include inlines for managing their related draft child data.

#### Creating Net-New entities Provisionally

*   A user initiates "add new" for a top-level entity (e.g., `Cluster`) within an active `ChangeSet`.
*   A new row for the top-level entity is created: `is_live = False`, `changeset_id = active_changeset_id`, and a new `shared_entity_id` is generated.
*   The user may then add related child data to this new draft top-level entity.

#### Viewing `ChangeSet` Contents

The `ChangeSet` admin change form includes a section listing all provisional top-level entities associated with it, grouped by type, with links to their respective provisional admin edit pages.

#### Commit Process

When a `ChangeSet` is committed:

*   For each draft top-level entity row (`draft_entity_row`) in the `ChangeSet`:
    *   Get its `shared_entity_id`.
    *   Find the current `is_live=True` row for that `shared_entity_id` (`old_live_entity_row`), if any.
    *   If `old_live_entity_row` exists:
        *   Set `old_live_entity_row.is_live = False`, `is_locked = False`, `locked_by_changeset = None`, and `obsoleted_by_changeset = committed_changeset`.
        *   **Re-point incoming foreign keys.** For example, for a `Group` entity, any `Cluster` records pointing to `old_live_entity_row` are updated to point to the `draft_entity_row`.
    *   Set `draft_entity_row.is_live = True`, `changeset_id = None`, `is_locked = False`, `locked_by_changeset = None`, and `draft_of = None`.
    *   For child data linked to `draft_entity_row` (via its `id`): Set their `is_live = True` and `changeset_id = None`.
*   Update the `ChangeSet` status to `committed`.

#### Discard Process

When a `draft` `ChangeSet` is discarded:

*   For each live top-level entity row locked by this `ChangeSet`: Clear its `is_locked` and `locked_by_changeset` fields.
*   Delete all draft rows (top-level and child) where `changeset_id = discarded_changeset_id`.
*   Delete the `ChangeSet` entity itself.

# Other Ideas Considered

This section details alternative approaches that were evaluated for managing provisional data before selecting the "Shadow Rows / Version Status in the Same Table" strategy.

## Provisional Tables (Separate Tables for Drafts)

*   **Idea**: This approach proposed creating a distinct "provisional" or "draft" database table for every existing data model that needed to be versioned (e.g., a `ProvisionalCluster` table alongside the `Cluster` table).
*   **Reason for Not Choosing**:
    *   **Schema Duplication and Maintenance**: This doubles the schema maintenance effort and increases the risk of inconsistencies if migrations are not perfectly synchronized.
    *   **Querying Across States**: Retrieving a consolidated view of an entity would require querying across two separate tables, complicating logic and potentially harming performance.
    *   **Complex Data Copy Operations**: The commit process would involve complex logic to copy data from many provisional tables back to their live counterparts.
    *   While this offers clear physical separation, the "Shadow Rows" approach was favored to keep all states of a shared entity co-located, simplifying model management and reducing schema maintenance overhead.

## Using Django History Plugins for Provisional Data

*   **Idea**: This alternative explored leveraging existing Django plugins designed for auditing and versioning (like *django-simple-history*) to manage the `draft` state, treating the latest historical record as the "active draft".
*   **Reason for Not Choosing**:
    *   **Mismatch with Primary Design Goal**: These plugins are architected for recording *committed history*, not for managing an *active, mutable, and separate draft workspace* that exists concurrently with a stable live version.
    *   **Complexity in Isolating and Managing Drafts**: It would require significant custom logic to reliably identify and manage the "current draft" version from all other historical records.
    *   **Deviation from Intended Use**: It would be repurposing these tools for a task they weren't built for, likely leading to a less clean and more error-prone implementation compared to a solution that explicitly models the draft state.

## No Provisional State (Direct Edits with Delayed Notification)

*   **Idea**: This was the simplest alternative. It proposed allowing users to continue editing live data directly, but batching or holding notifications to downstream systems until a user manually triggers a "Publish Changes" event.
*   **Reason for Not Choosing**:
    *   **Fails Core Staging Requirement**: This fundamentally fails to meet the primary objective of introducing a staging area. Modifications would still be live and impact the system instantly.
    *   **No Prevention of Accidental Live Updates**: Users could still make errors that immediately become the source of truth.
    *   **Lack of Atomic Grouped Changes**: It wouldn't allow for several related changes to be grouped and made live together as a single, atomic unit.
    *   This idea was quickly dismissed as it did not address the core problems of immediate impact and the need for coordinated, staged updates.

# Appendix

## Deprioritized Items

The following items were part of the initial design but were deprioritized or scoped out of the initial implementation.

### Notification System

A pluggable notification system was originally planned to alert downstream systems when a `ChangeSet` was committed.

*   **`NotificationEndpoint`**: A configured destination for receiving notifications about committed `ChangeSets`. Each endpoint would have a type (e.g., Pub/Sub, GitHub Action Webhook) and associated details (e.g., topic name, webhook URL).
*   **Notification Payload**: The message sent to a `NotificationEndpoint`. For this feature, it would be a summary list of top-level shared entities (name and type) that were included as part of the Committed `ChangeSet`.
*   **User Journeys**:
    *   As an EPS System Administrator, I need to create new `NotificationEndpoints` (subscribers) for downstream systems (e.g., Pub/Sub, GitHub Actions).
    *   As an EPS System Administrator, I need to view and modify the configuration of existing `NotificationEndpoints`.
    *   As an EPS System Administrator, I need to activate or deactivate `NotificationEndpoints`.
*   **Technical Design**:
    *   A new Django model `NotificationEndpoint` would store subscriber configurations.
    *   A notifier service architecture with a base class and concrete implementations for different notification types (e.g., `PubSubNotifier`).
    *   Asynchronous notification processing using a system like Cloud Tasks to avoid blocking the commit operation.
