# Programmatic Access to Parameter Store (EPS) with Google Service Accounts

This document outlines how to programmatically access an EPS (Parameter Store) instance hosted on Google Cloud Platform (GCP) and protected by Identity-Aware Proxy (IAP). Access is achieved using a Google Service Account (GSA).

## Overview

EPS relies on IAP for authenticating users and service accounts. When IAP protects an application, it presents a JSON Web Token (JWT) to the application for authenticated entities. EPS uses this JWT to identify the GSA and log it in.

Programmatic access involves your application or script, acting on behalf of a GSA, obtaining an OIDC (OpenID Connect) ID token. This token is then used as a bearer token in HTTP requests to the EPS API.

## Prerequisites

Before your GSA can programmatically access EPS, ensure the following:

1. **Google Service Account (GSA) Exists**:
    * You have a GSA created in your GCP project.
    * **Important**: As noted in the [Users, Personas, and Permissions](./users-and-permissions.md#service-account-authentication) guide, EPS derives a username from the email address (the part before the `@`). Ensure your GSA has a unique name that won't collide with human user accounts accessing EPS. For example, if a user `admin@example.com` exists, avoid a GSA named `admin@your-project.iam.gserviceaccount.com` if both are intended to be distinct entities within EPS.

2. **IAM Permissions for IAP**:
    * The GSA must be granted the `IAP-Secured Web App User` role (`roles/iap.httpsResourceAccessor`) for the IAP-protected EPS application. This allows the GSA to bypass IAP. Refer to the GCP IAP documentation on managing access.
    * This IAM permission *only* allows the GSA to reach the EPS application; it does *not* grant any permissions *within* EPS.

3. **EPS Internal Permissions**:
    * Once the GSA authenticates to EPS (after its first successful connection), it will appear as a user within the EPS admin panel.
    * Like any user, the GSA will have no permissions by default within EPS. An EPS superuser must explicitly grant the GSA necessary roles or add it to groups with the desired permissions (e.g., to read specific parameters, access certain API endpoints, etc.).

4. **IAP OAuth 2.0 Client ID**:
    * You need the OAuth 2.0 Client ID associated with the IAP configuration for your EPS application. This ID is used as the `audience` when generating the OIDC ID token. You can find this in the GCP console under "Security" > "Identity-Aware Proxy".

## Programmatic Access Steps & Python Example

The general flow for programmatic access is:

1. Your application, using the GSA's credentials, requests an OIDC ID token from Google's IAM Credentials API.
2. The `audience` for this ID token request must be the IAP OAuth 2.0 Client ID.
3. The obtained ID token is then included in the `Authorization` header as a `Bearer` token for all HTTP requests to the EPS API.

### Python Example

To run the following Python example, you'll need to install the necessary Google Cloud client libraries:

```bash
pip install google-cloud-iam google-auth
```

The `google-auth` library provides core authentication functionalities and is often installed as a dependency of other Google Cloud libraries (like `google-cloud-iam` which provides the `iam_credentials_v1` module). Listing `google-auth` explicitly ensures it's available and helps manage its version if needed.

This example uses the `google-cloud-iam` (for interacting with IAM credentials) and `google-auth` (for authentication and authorized sessions) Python libraries to demonstrate the process.

```python
from google.cloud import iam_credentials_v1 as iam
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import AuthorizedSession

# --- Configuration ---
# Replace with your GSA email
gsa_email = 'your-service-account@your-project-id.iam.gserviceaccount.com'
# Replace with your EPS instance API URL and desired endpoint
eps_api_url = 'https://your-eps-instance-url.example.com/api/v1/clusters'
# Replace with the OAuth 2.0 Client ID of your IAP-protected EPS application
iap_oauth_client_id = 'your-iap-oauth-client-id.apps.googleusercontent.com'

# Construct the resource name for the service account
gsa_resource_name = f'projects/-/serviceAccounts/{gsa_email}'

# Initialize the IAM Credentials client
# This client will use Application Default Credentials (ADC)
# Ensure the environment where this script runs has credentials for a principal
# that has the "Service Account Token Creator" role on the target GSA (gsa_email).
iam_client = iam.IAMCredentialsClient()

try:
    # Generate an OIDC ID token for the GSA, targeting the IAP audience
    id_token_response = iam_client.generate_id_token(
        name=gsa_resource_name,
        audience=iap_oauth_client_id,
        include_email=True  # Recommended to include email
    )

    # Create credentials object from the obtained ID token
    iap_credentials = Credentials(id_token_response.token)

    # Create an authorized session that will automatically include the token
    authed_session = AuthorizedSession(iap_credentials)

    # Make the request to the EPS API
    print(f"Requesting data from: {eps_api_url}")
    response = authed_session.get(eps_api_url)

    # Check for HTTP errors
    response.raise_for_status()

    print("Successfully accessed EPS API.")
    print("Response:", response.json()) # Or response.text, depending on the API

except Exception as e:
    print(f"An error occurred: {e}")

```

**Explanation of the code:**

1. `gsa_email`, `eps_api_url`, `iap_oauth_client_id`: Configuration variables you must set.
2. `gsa_resource_name`: The unique identifier for the GSA whose identity will be impersonated to generate the token.
3. `iam.IAMCredentialsClient()`: Initializes the client to interact with the IAM Credentials API. This client typically uses Application Default Credentials (ADC). The identity running this script (e.g., another GSA, your user credentials if running locally with `gcloud auth application-default login`) needs the `roles/iam.serviceAccountTokenCreator` permission on the `gsa_email` service account.
4. `iam_client.generate_id_token(...)`: This is the core call. It requests Google to issue an OIDC ID token.
    * `name`: Specifies the GSA for which the token is generated.
    * `audience`: Crucially, this is set to the `iap_oauth_client_id`. IAP will validate that the token was intended for it.
    * `include_email=True`: Ensures the GSA's email is in the token, which EPS might use.
5. `Credentials(id_token_response.token)`: Creates a `google-auth` credentials object using the raw ID token.
6. `AuthorizedSession(iap_credentials)`: Creates an HTTP session object that automatically adds the `Authorization: Bearer <token>` header to requests.
7. `authed_session.get(eps_api_url)`: Makes the actual GET request to your EPS API endpoint.
8. `response.raise_for_status()`: Will raise an exception for HTTP error codes (4xx or 5xx).

### Creating Programmatic Clients in Other Languages

While the example above is in Python, the underlying mechanism is standard OAuth 2.0 and OIDC. For other languages or environments:

1. **Authenticate as the GSA**: Your application needs to authenticate to Google Cloud. This is often done via Application Default Credentials (ADC), which can pick up credentials from a GSA key file (less recommended for GKE/Cloud Run, prefer workload identity) or the GCE metadata server.
2. **Obtain an OIDC ID Token**: Use a Google authentication library for your language to request an OIDC ID token.
    * The key is to specify the **IAP OAuth 2.0 Client ID** as the `audience` (sometimes called `aud`) for the token.
    * You'll typically use a method equivalent to `generateIdToken` from the IAM Credentials API (or a wrapper around it).
3. **Make HTTP Requests**: Include the obtained ID token in the `Authorization` header of your HTTP requests to the EPS API:
    `Authorization: Bearer <OIDC_ID_TOKEN>`

Consult the Google Cloud client libraries for your specific language for details on authenticating and generating OIDC ID tokens. The core principle is to generate an ID token for the service account, with the audience set to your IAP's client ID.
### cURL Example

For quick testing or scripting in shell environments, `curl` combined with the `gcloud` CLI can be used.

**Prerequisites for cURL example:**

1.  **`gcloud` CLI Installed and Authenticated**: Ensure the Google Cloud SDK is installed and you are authenticated (`gcloud auth login`).
2.  **Permissions**: The identity authenticated with `gcloud` must have the `roles/iam.serviceAccountTokenCreator` permission on the target GSA you want to impersonate.

```bash
# Set your environment variables
export CLIENT_ID='your-iap-oauth-client-id.apps.googleusercontent.com'
export GSA='your-service-account@your-project-id.iam.gserviceaccount.com'
export EPS_API_URL='https://your-eps-instance-url.example.com/api/v1/groups' # Example endpoint

# 1. Obtain an OIDC ID token for the GSA, impersonating it
export ID_TOKEN=$(gcloud auth print-identity-token \
    --include-email \
    --audiences="${CLIENT_ID}" \
    --impersonate-service-account="${GSA}")

# Check if ID_TOKEN was successfully obtained
if [ -z "$ID_TOKEN" ]; then
    echo "Failed to obtain ID_TOKEN. Check your GSA, CLIENT_ID, and permissions."
    exit 1
fi

# 2. Make the request to the EPS API using the token
curl -v -H "Authorization: Bearer ${ID_TOKEN}" "${EPS_API_URL}"
```

**Explanation of the `curl` commands:**

1.  `export CLIENT_ID=...`, `export GSA=...`, `export EPS_API_URL=...`: These commands set shell environment variables for your IAP Client ID, the GSA email, and the target EPS API endpoint. **Replace the placeholder values with your actual configuration.**
2.  `gcloud auth print-identity-token ...`: This `gcloud` command generates an OIDC ID token.
    *   `--include-email`: Includes the GSA's email in the token.
    *   `--audiences="${CLIENT_ID}"`: Specifies the IAP OAuth 2.0 Client ID as the audience for the token. This is crucial for IAP to accept the token.
    *   `--impersonate-service-account="${GSA}"`: Instructs `gcloud` to generate the token on behalf of the specified GSA. The currently authenticated `gcloud` user needs permission to do this.
3.  `curl -v -H "Authorization: Bearer ${ID_TOKEN}" "${EPS_API_URL}"`: This `curl` command makes the HTTP GET request.
    *   `-v`: Verbose output, useful for debugging.
    *   `-H "Authorization: Bearer ${ID_TOKEN}"`: Adds the `Authorization` header with the OIDC ID token obtained in the previous step.
    *   `"${EPS_API_URL}"`: The URL of the EPS API endpoint you want to access.

## Important Considerations

* **GSA Naming**: As mentioned in prerequisites, ensure your GSA names (the part before `@your-project.iam.gserviceaccount.com`) do not clash with human usernames if they are meant to be distinct entities within EPS.
* **EPS Permissions**: Remember that authenticating through IAP does not grant permissions *within* EPS. The GSA must be explicitly granted roles/permissions in the EPS admin interface.
* **Token Caching and Expiration**: ID tokens have an expiration time (typically 1 hour). For long-running applications, implement logic to refresh the token before it expires. The `google-auth` library in Python handles some of this automatically when using `AuthorizedSession`.
