# parameter_store

## Local Dev

### Postgres Setup

1. Install Postgres 16
2. Log in to PostgreSQL as a Superuser: Use the psql command-line utility to log in as the postgres user.

```bash
psql -U postgres
```

3. Create a New Database: Create a new database named eps.

```sql
CREATE DATABASE eps;
```

4. Create a New User: Create a new user named eps with a specified password. Replace your_password with a strong password of your choice.

```sql
CREATE USER eps WITH PASSWORD 'your_password';
```

5. Change Ownership of the Database: Alter the ownership of the eps database to the new user eps.

```sql
ALTER DATABASE eps OWNER TO eps;
```

6. Grant Necessary Privileges to the User: Grant the necessary permissions for the eps user to manage objects within the eps database.

```sql
-- Connect to the database named 'eps'
   \c eps
   
   -- Grant usage on the schema 'public' to 'eps'
   GRANT USAGE ON SCHEMA public TO eps;

   -- Grant create privileges on the schema 'public' to 'eps'
   GRANT CREATE ON SCHEMA public TO eps;

   -- Grant all privileges on all tables in the schema 'public' to 'eps'
   GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO eps;

   -- Grant all privileges on all sequences in the schema 'public' to 'eps'
   GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO eps;

   -- Grant privileges to create and manage tables within the 'public' schema
   ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO eps;
   ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO eps;
```

7. 

### Python Setup

1. Install Python 3.12

2. Create virtualenv

```bash
python3 -m venv .venv
```

3. Install dev requirements

```bash
pip3 install -r requirements.txt
pip3 install -r requirements-dev.txt
```

### Django Setup

1. Run Django Migrations

```shell
python manage.py makemigrations
python manage.py migrate
```

2. Create a Superuser: Create a superuser for accessing the Django admin interface:

```shell
python manage.py createsuperuser
```

3. Start the Development Server: Run the Django development server to check if everything is working fine:

```shell
python manage.py runserver
```

## Appendix

### Possible Errors

Sometimes Django doesn't seem to pick up the models for `parameter_store`, so I have to `makemigrations` explicitly for it:

```shell
python3 manage.py makemigrations parameter_store
python3 manage.py migrate
```

If succesful, it looks something like:

```shell
$ python3 manage.py makemigrations parameter_store
Migrations for 'parameter_store':
  parameter_store/migrations/0001_initial.py
    + Create model Cluster
    + Create model GlobalRole
    + Create model Group
    + Create model Tag
    + Create model ClusterFleetLabel
    + Create model ClusterIntent
    + Create model ClusterRole
    + Add field group to cluster
    + Create model GroupRole
    + Create model ClusterTag

$ python3 manage.py migrate
Operations to perform:
  Apply all migrations: admin, auth, contenttypes, parameter_store, sessions
Running migrations:
  Applying parameter_store.0001_initial... OK

```

### Dev Hacks

I have Postgres running on my cloudtop while I dev locally, so I port-forward to psql on the cloudtop:

```shell
ssh -TL 5432:localhost:5432 cloudtop
```
