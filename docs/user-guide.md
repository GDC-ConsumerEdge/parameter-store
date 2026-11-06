# Parameter Store User Guide

This guide provides an overview of how to manage your data using the **ChangeSet** system.

Think of EPS like a library.
*   **Live Data**: These are the books on the shelves that everyone can access.
*   **ChangeSet**: This is your personal workspace. When you want to add or modify data, you do it here first.
*   **Commit**: This is the action of finalizing your work and publishing it for everyone to see.

---

## Part 1: Using the Admin UI

The Admin UI is the primary interface for browsing and editing data. It includes safeguards to ensure data integrity through the ChangeSet workflow.

### 1. Understanding ChangeSets
A **ChangeSet** groups related modifications—edits, creations, and deletions—into a single unit of work.
*   **Draft**: A ChangeSet in progress. Changes here are visible only to you (and those viewing your specific ChangeSet).
*   **Committed**: A finalized ChangeSet. Its changes have been applied to the "Live" data.

### 2. Creating and Editing Data

When you add or edit a Group or Cluster, the system automatically handles the versioning for you.

#### Adding Clusters
1.  In the left pane, click **Clusters**.
2.  Click the **plus icon (+)** in the upper right to add a new one.
    ![clusters.png](doc_assets/cujs/clusters.png)
3.  Fill out the form. Required fields have a red asterisk (*).
    ![new cluster.png](doc_assets/cujs/new%20cluster.png)
4.  Click **Save**.

**What happens next?**
*   EPS detects a modification.
*   It automatically creates a **Draft** version of your item.
*   This Draft is placed into an **Active ChangeSet**. If you don't have one open, a new one is created for you.
*   You are redirected to your new Draft. Look for the blue badge labeled **Draft in active ChangeSet**.


* ![add.png](doc_assets/user_guide/add.png)


#### Editing Clusters
1.  Click **Clusters** on the left.
2.  Search for the cluster you want to modify and click its name.
3.  Update the necessary fields.
4.  Click **Save**.

Just like adding a cluster, this creates a **Draft** copy. The original "Live" cluster remains unchanged until you Commit.

### 3. Deleting Data
Deleting items is a safe, staged process.

1.  Select the items you want to delete in the list view, or click **Delete** on a specific item page.
2.  Confirm the deletion.

**What happens next?**
*   The item is **not** removed immediately.
*   It is marked as **Staged for Deletion**.
*   It will appear in your ChangeSet with a red **Pending Deletion** badge.
*   If this was a mistake, you can simply delete the *draft*, and the original Live item remains untouched.


![delete.png](doc_assets/user_guide/delete.png)


### 4. Committing Changes
Once you have reviewed your edits, creations, and deletions, you can apply them to the live system.

1.  Go to the **ChangeSets** menu on the left.
2.  Locate your ChangeSet (it will be in `Draft` status).
3.  Select the checkbox next to it.
4.  In the "Actions" dropdown at the top, select **Commit selected ChangeSets**.
5.  Click **Go**.


![commit.png](doc_assets/user_guide/commit.png)


**Success!** All drafts in the ChangeSet are now Live. Previous versions are archived in the history.

### 5. Additional ChangeSet Actions

If a ChangeSet is no longer needed or contains errors, select it and choose _Abandon selected ChangeSets_ (or `POST /api/v1/changeset/{id}/abandon`) to delete all associated drafts and unlock parent live entities.

If multiple ChangeSets should be combined into a single update, select them and choose _Coalesce selected ChangeSets_ (or `POST /api/v1/changeset/{id}/coalesce`). If the source and target ChangeSets contain conflicting draft entity names or unique constraint values (such as duplicate draft `unique_zone_id` values), the coalesce operation rolls back without modifying either ChangeSet and returns `422 Unprocessable Entity` with entity-contextualized error keys.

---

## Part 2: Advanced Features

### Fleet Labels
Fleet labels act as key/value identifiers for your clusters. You can add them when adding or editing a cluster.
![fleet labels.png](doc_assets/cujs/fleet%20labels.png)

### Tags
Tags facilitate filtering and organizing clusters.
1.  Go to **Tags** and click the **plus (+)** icon.
    ![tag table.png](doc_assets/cujs/tag%20table.png)
2.  Enter a name and click **Save**.
    ![create tag.png](doc_assets/cujs/create%20tag.png)
3.  This tag can now be associated with any Cluster.
    ![add tags.png](doc_assets/cujs/add%20tags.png)

### Cluster Intent
Cluster Intent defines the data used to provision clusters automatically.
1.  When editing a cluster, scroll to **Cluster Intent**.
2.  Click **Add another Cluster Intent** (or edit the existing one).
    ![intent add.png](doc_assets/cujs/intent%20add.png)
3.  Complete the form and click **Save**.

### Custom Data
Use Custom Data to store additional, user-defined information.
1.  Go to **Custom Data Fields** and click **plus (+)**.
    ![custom data table.png](doc_assets/cujs/custom%20data%20table.png)
2.  Name your field and click **Save**.
    ![custom data add.png](doc_assets/cujs/custom%20data%20add.png)
3.  Navigate to a Cluster or Group, scroll to **Custom Data**, and enter a value for your new field.
    ![custom field cluster.png](doc_assets/cujs/custom%20field%20cluster.png)

### Data Validators
Validators ensure data integrity by enforcing rules on field values.
1.  Go to **Validators** and click **plus (+)**.
2.  Select a validator type (e.g., `EnumValidator` to restrict values to a list).
3.  Add parameters such as `{"choices": ["north", "south"]}`.
    ![validator create.png](doc_assets/cujs/validator%20create.png)
4.  **Associate** the validator with a field using **Validator Assignments**.
    ![validator assignment.png](doc_assets/cujs/validator%20assignment.png)
5.  If a user attempts to save an invalid value, EPS will reject the input.
    ![validator rejection.png](doc_assets/cujs/validator%20rejection.png)

---

## Part 3: Using the API

The API provides programmatic access to EPS functionality, suitable for scripts and automation.

**Authentication Required**:
*   **Production/Staging (IAP)**: Uses Google Service Accounts and OIDC tokens.
*   **Local Development**: Uses your browser's session ID (cookie).

For detailed authentication instructions and scripts, see the **[Programmatic Access Cheat Sheet](programmatic-access.md)**.

### Constraint: Live Data is Read-Only
**You cannot modify Live data directly.**
Every `POST` (create), `PUT` (update), or `DELETE` operation **MUST** include a `changeset_id` to ensure changes are tracked and versioned.

### Working with Entity IDs
*   **`id` (UUID)**: This is the **Shared Entity ID**. It is a unique identifier (e.g., `a1b2c3d4...`) that persists across all versions (Live, Draft, History) of an object. **Use this ID for all API operations.**
*   **`record_id` (Integer)**: This is the specific database row ID for a single version. It changes with every new draft and is primarily used for internal debugging.

### Workflow Example (Local Development)

**Prerequisite**: [Obtain your session ID](programmatic-access.md#part-2-local-development-browser-session) from your browser cookies.
```bash
export SESSION_ID='your_session_id_here'
```

#### Step 1: Create a ChangeSet
Create a new workspace for your changes.
```bash
curl -X POST "http://localhost:8000/api/v1/changeset" \
     --cookie "sessionid=${SESSION_ID}" \
     -H "Content-Type: application/json" \
     -d '{"name": "my-api-update", "description": "Updating clusters via script"}'
```
**Response:**
```json
{ "id": 42, "status": "draft", ... }
```
Note the ChangeSet ID (`42`) for subsequent requests.

#### Step 2: Create or Update a Group or Cluster
When creating or updating Groups (`/api/v1/group`, `/api/v1/group/{name}`, `/api/v1/group/id/{uuid}`) and Clusters (`/api/v1/cluster`, `/api/v1/cluster/{name}`, `/api/v1/cluster/id/{uuid}`), you can manage associated parameters and relations directly in the request payload:

- Custom data (`data` on Groups and Clusters) and fleet labels (`fleet_labels` on Clusters) follow consistent key-value update semantics: providing a key creates or updates that key, omitting a key leaves its existing value untouched, setting a key's value to `null` removes that key, and passing an empty collection (`{}` or `[]`) removes all keys in that collection. Custom data keys must reference registered `CustomDataField` names (`/api/v1/data-fields`).
- Tags (`tags`) and secondary groups (`secondary_groups`) on Clusters accept a list of names. Omitting the field leaves existing associations untouched, providing a list replaces the set of associations, and passing `[]` clears all associations. Tags must reference registered `Tag` names (`/api/v1/tags`).
- Cluster intent (`intent`) accepts the full specification when creating an intent or a partial object when updating an existing intent. The optional `subnet_vlans` field accepts a comma-separated string (`"500,2100"`) or list of VLAN IDs (`[500, 2100]`); omitting it on creation, setting it to `null`, or passing `""` or `[]` stores `null`.

```bash
curl -X PUT "http://localhost:8000/api/v1/cluster/id/a1b2c3d4-..." \
     --cookie "sessionid=${SESSION_ID}" \
     -H "Content-Type: application/json" \
     -d '{
           "description": "Updated via API",
           "secondary_groups": ["secondary-group-a"],
           "tags": ["edge-tag"],
           "fleet_labels": {"environment": "prod", "deprecated_label": null},
           "data": {"manifest_version": "v1.2.0", "obsolete_field": null},
           "intent": {"node_count": 5, "subnet_vlans": [500, 2100]},
           "changeset_id": 42
         }'
```
This action creates or updates the draft of the cluster within ChangeSet 42. Note that an entity already staged for deletion (`DELETE /api/v1/group/...` or `DELETE /api/v1/cluster/...`) in a ChangeSet cannot be updated or assigned to a cluster in that same ChangeSet; attempting to do so returns `409 Conflict`.

#### Step 3: Review Changes
Retrieve a summary of all pending changes in the ChangeSet.

```bash
curl -X GET "http://localhost:8000/api/v1/changeset/42/changes" \
     --cookie "sessionid=${SESSION_ID}"
```
**Response:**
```json
{
  "groups": [],
  "clusters": [
    {
      "action": "update",
      "entity": { "name": "my-cluster", "description": "Updated via API", ... }
    }
  ]
}
```

#### Step 4: Commit
Apply the changes to the live environment.

```bash
curl -X POST "http://localhost:8000/api/v1/changeset/42/commit" \
     --cookie "sessionid=${SESSION_ID}"
```

### Viewing History
Retrieve the version history of a cluster.

```bash
curl -X GET "http://localhost:8000/api/v1/cluster/my-cluster/history" \
     --cookie "sessionid=${SESSION_ID}"
```
This returns a chronological list of previous versions, including metadata on who made the changes and when.

---

## Glossary

*   **ChangeSet**: A logical grouping of staged changes (creations, updates, deletions).
*   **Draft**: A pending version of an entity (Cluster or Group) that has not yet been applied to the live environment.
*   **Live**: The currently active, approved version of an entity.
*   **Shared Entity ID (UUID)**: The persistent unique identifier that connects all versions (Live, Draft, History) of a single logical object.
