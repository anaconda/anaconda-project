# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
"""A requirement for a service."""

from copy import deepcopy
from anaconda_project.requirements_registry.requirement import EnvVarRequirement

from anaconda_project.internal.py2_compat import is_string


class ServiceRequirement(EnvVarRequirement):
    """Abstract base class for a requirement from the services section of the project file."""
    @classmethod
    def _parse(cls, varname, item, problems):
        """Parse an item from the services: section."""
        service_type = None
        if is_string(item):
            service_type = item
            options = dict(type=service_type)
        elif isinstance(item, dict):
            service_type = item.get('type', None)
            if service_type is None:
                problems.append("Service {} doesn't contain a 'type' field.".format(varname))
                return None
            options = deepcopy(item)
        else:
            problems.append(
                "Service {} should have a service type string or a dictionary as its value.".format(varname))
            return None

        if not EnvVarRequirement._parse_default(options, varname, problems):
            return None

        return dict(service_type=service_type, env_var=varname, options=options)

    @property
    def service_type(self):
        """Get service type string."""
        return self.options['type']

    @property
    def ignore_patterns(self):
        """Override superclass with our ignore patterns."""
        return set(['/services/'])
