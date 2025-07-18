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
import ipaddress
from abc import ABC, abstractmethod

from django.core.exceptions import ValidationError
from django.core.validators import (
    EmailValidator,
    MaxValueValidator,
    MinValueValidator,
    RegexValidator,
    validate_ipv4_address,
)


class BaseValidator(ABC):
    """Base class for all validators."""

    def __init__(self, allow_empty=True):
        self.allow_empty = allow_empty

    @abstractmethod
    def validate(self, value):
        """Method to be implemented by each validator child class.

        Args:
            value: The value to be validated.

        Raises:
            ValidationError: If the validation does not pass.
        """
        pass


class IPAddressValidator(BaseValidator):
    """Validate if the value is a valid IP Address."""

    def validate(self, value):
        if self.allow_empty and (value == "" or value is None):
            return

        validate_ipv4_address(value)


class IPv4AddressWithCIDR(BaseValidator):
    """Validator class for checking if a given value is a valid IPv4 address in
    CIDR notation.
    """

    def validate(self, value):
        if self.allow_empty and (value == "" or value is None):
            return

        if "/" not in value:
            raise ValidationError("Expected an explicit CIDR value")

        try:
            # Parse the CIDR notation using ip_network
            ipaddress.IPv4Network(value, strict=False)
        except (ipaddress.AddressValueError, ValueError) as e:
            raise ValidationError(f"Invalid CIDR value: {value}. Error: {e}")


class EmailAddressValidator(BaseValidator):
    """Validate if the value is a valid Email Address."""

    def __init__(self, message=None, code=None, allowlist=None, allow_empty=True):
        super().__init__(allow_empty=allow_empty)
        self.validator = EmailValidator(message=message, code=code, allowlist=allowlist)

    def validate(self, value):
        if self.allow_empty and (value == "" or value is None):
            return

        self.validator(value)


class CommaSeparatedEmailsValidator(BaseValidator):
    """Validator to ensure that a string contains valid email addresses separated
    by a specified separator.
    """

    def __init__(self, separator=",", message=None, code=None, allowlist=None, allow_empty=True):
        super().__init__(allow_empty=allow_empty)
        self.separator = separator
        self.validator = EmailValidator(message=message, code=code, allowlist=allowlist)

    def validate(self, value):
        if self.allow_empty and (value == "" or value is None):
            return

        if isinstance(value, str):
            for item in value.split(self.separator):
                self.validator(item)
        else:
            raise ValidationError(f"Expected a string value, got {type(value)}")


class StringRegexValidator(BaseValidator):
    """Validate if the value matches the provided regular expression."""

    def __init__(self, regex, allow_empty=True):
        super().__init__(allow_empty=allow_empty)
        self.validator = RegexValidator(regex, message=f'Expected to match regex "{regex}"')

    def validate(self, value):
        if self.allow_empty and (value == "" or value is None):
            return
        self.validator(value)


class StringLengthValidator(BaseValidator):
    def __init__(self, min_value, max_value, allow_empty=True):
        super().__init__(allow_empty=allow_empty)
        try:
            self.min_value = int(min_value)
            self.max_value = int(max_value)
        except ValueError as e:
            raise ValueError("min_value and max_value must be integers or integers as strings") from e

    def validate(self, value):
        if self.allow_empty and (value == "" or value is None):
            return

        if not isinstance(value, str):
            raise ValidationError(f"Expected a string value, got {type(value)}")

        length = len(value)
        if self.min_value > len(value):
            raise ValidationError(f"Expected min string length of {self.min_value}, got {length}")
        if length > self.max_value:
            raise ValidationError(f"Expected max string length of {self.max_value}, got {length}")


class IntegerRangeValidator(BaseValidator):
    """Validates if the number is in the defined range.

    Attributes:
        min_value: Minimum allowed integer value.
        max_value: Maximum allowed integer value.
    """

    def __init__(self, min_value, max_value, allow_empty=True):
        super().__init__(allow_empty=allow_empty)
        self.min_val = MinValueValidator(min_value)
        self.max_val = MaxValueValidator(max_value)

    def validate(self, value):
        if self.allow_empty and (value == "" or value is None):
            return
        self.min_val(value)
        self.max_val(value)


class IntegerValueValidator(BaseValidator):
    """
    Validates if the value matches the provided integer.

    Attributes:
        value: The integer value to match.
    """

    def __init__(self, value, allow_empty=True):
        super().__init__(allow_empty=allow_empty)
        self.value = value

    def validate(self, value):
        if not value == self.value:
            raise ValidationError(f"{value} does not match {self.value}")


class EnumValidator(BaseValidator):
    """Validates if the value is in the provided enumerated list.

    Attributes:
        choices: An iterable container of valid choices.
    """

    def __init__(self, choices, allow_empty=True):
        super().__init__(allow_empty=allow_empty)
        self.choices = choices

    def validate(self, value):
        if value not in self.choices:
            raise ValidationError(f"Value must be one of {self.choices}. Got {value}.")


class ExactValueValidator(BaseValidator):
    """Validates if the value matches exactly the specified target value.

    Attributes:
        value: The target value for validation.
    """

    def __init__(self, value, allow_empty=True):
        super().__init__(allow_empty=allow_empty)
        self.value = value

    def validate(self, value):
        if self.allow_empty and (value == "" or value is None):
            return

        if value != self.value:
            raise ValidationError(f"The provided value {value} does not match the required value {self.value}.")
