# Copyright 2025 Google, LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#


###
# A simple script to indiscriminantly upgrade and re-pin all packages defined in pyproject.toml
# https://github.com/astral-sh/uv/issues/6794 tracks the FR to implement this functionality
# in UV.
###

PYPROJECT_TOML="../pyproject.toml"

which uv > /dev/null 2>&1 || { echo "UV command is missing - exiting."; exit 5; }

# Strip the existing package pins, otherwise uv will not update past the pinned version
# "click==8.2.1",  ->  "click",
perl -pi -e 's/==.*(",)/$1/g' ${PYPROJECT_TOML}

# Update uv.lock and install updated package
uv lock --upgrade && \
uv sync

# Now re-pin package versions
for updated_package in $(uv pip freeze); do
  package_name=$(echo ${updated_package} |cut -d= -f1 )

  # "click",  -> "click==8.2.1",
  perl -pi -e "s/\"${package_name}\"/\"${updated_package}\"/g" ${PYPROJECT_TOML}
done
