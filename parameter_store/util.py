###############################################################################
# Copyright 2024 Google, LLC
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
###############################################################################
import importlib
import inspect
from typing import Callable


def get_class_from_full_path(full_path):
    module_name, class_name = full_path.rsplit('.', 1)
    module = importlib.import_module(module_name)
    cls = getattr(module, class_name)
    return cls


def inspect_callable_signature(callable: Callable):
    """ Extracts and categorizes the parameters of a callable into all parameters
    and required parameters.

    This function uses the `inspect` module to analyze the signature of the
    provided callable and determines which parameters are required versus
    those that are optional. The classification of parameters considers
    their types, defaults, and the nature of the callable.

    Args:
        callable (Callable): The callable whose parameters are to be inspected.

    Returns:
        tuple: A tuple containing two lists:
            - The first list contains all parameters of the callable.
            - The second list contains only the required parameters.
    """
    params = inspect.signature(callable).parameters
    all_params, required_params = [], []
    valid_params = (inspect.Parameter.POSITIONAL_ONLY,
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    inspect.Parameter.KEYWORD_ONLY)
    for name, param in params.items():
        if name != 'self' and param.kind in valid_params:
            all_params.append(name)
            if param.kind == inspect.Parameter.POSITIONAL_ONLY or \
                (param.kind == inspect.Parameter.POSITIONAL_OR_KEYWORD
                 and param.default == inspect.Parameter.empty) or \
                (param.kind == inspect.Parameter.KEYWORD_ONLY
                 and param.default == inspect.Parameter.empty):
                required_params.append(name)

    return all_params, required_params

