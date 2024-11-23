import os
import base64
from dataclasses import dataclass
import gitlab
from github import Github, Auth
from google.cloud import secretmanager
import google_crc32c
from urllib.parse import urlparse
import logging

# Get an instance of a logger
logger = logging.getLogger(__name__)


@dataclass
class SotCsvIntegration:

    proj_id: str = os.environ.get("GOOGLE_CLOUD_PROJECT")
    region: str = os.environ.get("REGION")
    secrets_project: str = os.environ.get("PROJECT_ID_SECRETS")
    git_secret_id: str = os.environ.get("GIT_SECRET_ID")
    source_of_truth_repo: str = os.environ.get("SOURCE_OF_TRUTH_REPO").lower()
    source_of_truth_branch: str = os.environ.get("SOURCE_OF_TRUTH_BRANCH")
    source_of_truth_path: str = os.environ.get("SOURCE_OF_TRUTH_PATH")
    source_of_truth_repo_token: str = ""

    def get_git_token_from_secrets_manager(self, version_id="latest"):

        # Create the Secret Manager client.
        client = secretmanager.SecretManagerServiceClient()

        # Build the resource name of the secret.
        name = f"projects/{self.secrets_project}/secrets/{self.git_secret_id}/versions/{version_id}"

        response = client.access_secret_version(request={"name": name})

        crc32c = google_crc32c.Checksum()
        crc32c.update(response.payload.data)
        if response.payload.data_crc32c != int(crc32c.hexdigest(), 16):
            logger.critical("Git token corruption detected (Secret Manager).")
            return

        self.source_of_truth_repo_token = response.payload.data.decode("UTF-8")

    def retrieve_source_of_truth(self) -> bytes:
        parsed_result = urlparse(f"https://{self.source_of_truth_repo}")
        project_path = parsed_result.path.strip('/').rstrip('.git')
        if parsed_result.netloc == "github.com":
            gh = Github(auth=Auth.Token(self.source_of_truth_repo_token))
            repo = gh.get_repo(project_path)
            f = repo.get_contents(path=self.source_of_truth_path, ref=self.source_of_truth_branch)
            return f.decoded_content
        elif parsed_result.netloc == "gitlab.com":
            gl = gitlab.Gitlab(url='https://gitlab.com', private_token=self.source_of_truth_repo_token)
            project = gl.projects.get(project_path)
            f = project.files.get(file_path=self.source_of_truth_path, ref=self.source_of_truth_branch)
            return base64.b64decode(f.content)
        else:
            logger.error(f"Unsupported git provider {self.source_of_truth_repo}")

    def update_source_of_truth(self, content: bytes):
        parsed_result = urlparse(f"https://{self.source_of_truth_repo}")
        project_path = parsed_result.path.strip('/').rstrip('.git')
        if parsed_result.netloc == "github.com":
            gh = Github(auth=Auth.Token(self.source_of_truth_repo_token))
            repo = gh.get_repo(project_path)
            try:
                contents = repo.get_contents(self.source_of_truth_path, ref=self.source_of_truth_branch)
                repo.update_file(contents.path, 'updated by eps', content.decode("utf-8"), contents.sha, branch=self.source_of_truth_branch)
                logger.info(f"File '{self.source_of_truth_path}' updated successfully!")
            except Exception as e:  # Use a more specific exception if possible
                if "not found" in str(e).lower():  # Check if file not found error
                    repo.create_file(self.source_of_truth_path, 'created by eps', content, branch=self.source_of_truth_branch)
                    logger.info(f"File '{self.source_of_truth_path}' created successfully!")
                else:
                    raise e
        elif parsed_result.netloc == "gitlab.com":
            gl = gitlab.Gitlab(url='https://gitlab.com', private_token=self.source_of_truth_repo_token)
            project = gl.projects.get(project_path)
            try:
                f = project.files.get(file_path=self.source_of_truth_path, ref=self.source_of_truth_branch)
                f.content = content.decode("utf-8")
                f.save(branch=self.source_of_truth_branch, commit_message='updated by eps')
                logger.info(f"File '{self.source_of_truth_path}' updated successfully!")
            except gitlab.exceptions.GitlabGetError as e:
                if e.response_code == 404:  # File not found
                    # Create the file
                    project.files.create({
                        'file_path': self.source_of_truth_path,
                        'branch': self.source_of_truth_branch,
                        'content': content.decode("utf-8"),
                        'commit_message': 'created by eps'
                    })
                    logger.info(f"File '{self.source_of_truth_path}' created successfully!")
                else:
                    raise e
        else:
            raise Exception(f"Unsupported git provider {self.source_of_truth_repo}")
