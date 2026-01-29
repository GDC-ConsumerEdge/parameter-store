# Verification Walkthrough

This document provides a step-by-step guide to demonstrating and verifying the new **ChangeSet API** capabilities.

We will use `httpie` for API requests.

## Prerequisites

### 1. Setup Tools & Environment

First, let's install `httpie` using `uv`.
```bash
uv tool install httpie
```

**CRITICAL STEP:** Clear old httpie sessions to avoid confusion.
```bash
rm -rf ~/.config/httpie/sessions/localhost_8000/admin.json
```

Now, let's clear the database to start fresh. **WARNING: This deletes all data.**
```bash
uv run python manage.py flush --no-input
uv run python manage.py migrate
```

Create a superuser. **Run this exact command to ensure the password is 'password'.**
```bash
echo "from django.contrib.auth import get_user_model; User=get_user_model(); u=User.objects.create_superuser('admin', 'admin@example.com', 'password');" | uv run python manage.py shell
```

### 2. Start the Server
Open a **new terminal** window/tab and run:
```bash
# Ensure you are in the project root
uv run python manage.py runserver 0.0.0.0:8000
```

### 3. Authentication
The API uses Django Session authentication. We need a valid session ID.

#### Option 1: Browser
1.  Open your browser and go to [http://localhost:8000/admin/](http://localhost:8000/admin/).
2.  Log in with `admin` / `password`.
3.  Open Developer Tools -> Application/Storage -> Cookies.
4.  Copy the value of `sessionid`.

#### Option 2: CLI (Recommended)
Run this command to log in programmatically and capture the session ID.
**It also prints the DB name to stderr. Verify it matches your server's DB.**

```bash
export SESSION_ID=$(uv run python -c "import os; import sys; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'parameter_store.settings'); import django; django.setup(); from django.conf import settings; print(f'DEBUG: Using DB: {settings.DATABASES[\"default\"][\"NAME\"]}', file=sys.stderr); from django.test import Client; c = Client(); c.login(username='admin', password='password'); print(c.session.session_key)")
echo "Session ID: $SESSION_ID"
```

**Initialize your httpie session:**

```bash
# If you used Option 1, replace <your_session_id> with the value you copied.
# If you used Option 2, SESSION_ID is already set!
# export SESSION_ID="<your_session_id>"

export HOST="http://localhost:8000/api/v1"

# This command initializes a session named 'admin' with the cookie.
# We explicitly pass the cookie to force httpie to save it for future requests.
http --session=admin GET "$HOST/ping" "Cookie:sessionid=$SESSION_ID"
```
*If you see `{"status": "ok"}`, you are authenticated.*

---

## Scenario 1: The "Happy Path" (Create & Commit)

**Goal:** Create a ChangeSet, define a new Group and Cluster together, and commit them.

**1. Create a ChangeSet**
```bash
http --session=admin POST "$HOST/changeset" name="Initial Setup"
```
*Take note of the `id` (likely `1`).*
```bash
export CS_ID=1
```

**2. Create a Group (Draft)**
```bash
http --session=admin POST "$HOST/group" \
    name="prod-group" \
    description="Production Environment" \
    changeset_id=$CS_ID
```

**3. Create a Cluster (Draft)**
Note that we can reference the `prod-group` even though it isn't live yet!
```bash
http --session=admin POST "$HOST/cluster" \
    name="cluster-01" \
    group="prod-group" \
    description="Primary Cluster" \
    changeset_id=$CS_ID
```
*Copy the `id` (UUID) from the response.*
```bash
export CLUSTER_UUID="<paste_cluster_uuid_here>"
```

**4. Verify Changes**
```bash
http --session=admin GET "$HOST/changeset/$CS_ID/changes"
```

**5. Commit**
```bash
http --session=admin POST "$HOST/changeset/$CS_ID/commit"
```

**6. Verify Live Data**
```bash
http --session=admin GET "$HOST/cluster/cluster-01"
```

---

## Scenario 2: The "Update" Cycle

**Goal:** Modify the live cluster and verify the history trail.

**1. Create a New ChangeSet**
```bash
http --session=admin POST "$HOST/changeset" name="Update Cluster"
```
```bash
export CS_ID=2
```

**2. Update the Cluster**
We use the UUID (`id`) and pass the new ChangeSet ID.
```bash
http --session=admin PUT "$HOST/cluster/id/$CLUSTER_UUID" \
    description="Primary Cluster v2" \
    changeset_id=$CS_ID
```

**3. Verify Isolation**
*   **Draft View**: `http --session=admin GET "$HOST/changeset/$CS_ID/changes"` (Shows V2)
*   **Live View**: `http --session=admin GET "$HOST/cluster/cluster-01"` (Shows V1)

**4. Commit**
```bash
http --session=admin POST "$HOST/changeset/$CS_ID/commit"
```

**5. Verify History**
```bash
http --session=admin GET "$HOST/cluster/cluster-01/history"
```
*Expect to see the historical V1 entry in the list.*

---

## Scenario 3: The "Abandon" Path

**Goal:** Stage a change and discard it.

**1. Create ChangeSet**
```bash
http --session=admin POST "$HOST/changeset" name="Abandon Test"
```
```bash
export CS_ID=3
```

**2. Create a "Mistake" Group**
```bash
http --session=admin POST "$HOST/group" name="bad-group" changeset_id=$CS_ID
```

**3. Abandon ChangeSet**
```bash
http --session=admin POST "$HOST/changeset/$CS_ID/abandon"
```

**4. Verify Disappearance**
```bash
http --session=admin GET "$HOST/group/bad-group"
# Expected: 404 Not Found
```

---

## Scenario 4: The "Delete" Cycle

**Goal:** Safely delete the cluster while preserving its history.

**1. Create ChangeSet**
```bash
http --session=admin POST "$HOST/changeset" name="Delete Cluster"
```
```bash
export CS_ID=4
```

**2. Stage Deletion**
```bash
http --session=admin DELETE "$HOST/cluster/id/$CLUSTER_UUID" changeset_id==$CS_ID
```

**3. Verify Staging**
```bash
# Action should be 'delete'
http --session=admin GET "$HOST/changeset/$CS_ID/changes"
```

**4. Commit**
```bash
http --session=admin POST "$HOST/changeset/$CS_ID/commit"
```

**5. Verify Gone & History**
*   **Live**: `http --session=admin GET "$HOST/cluster/cluster-01"` (404 Not Found)
*   **History**: `http --session=admin GET "$HOST/cluster/id/$CLUSTER_UUID/history"`
