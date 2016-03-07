"""Common properties between project.yml and meta.yaml."""
from __future__ import absolute_import


class _ProjectMetaCommon(object):
    """Mixin class for common properties across project.yml and meta.yaml."""

    @property
    def name(self):
        """Get the "package: name" field from the file."""
        return self.get_value(['package', 'name'], default=None)

    @name.setter
    def name(self, value):
        """Set the "package: name" field in the file."""
        self.set_value(['package', 'name'], value)

    @property
    def version(self):
        """Get the "package: version" field from the file."""
        return self.get_value(['package', 'version'], default=None)

    @version.setter
    def version(self, value):
        """Set the "package: version" field in the file."""
        return self.set_value(['package', 'version'], value)

    @property
    def app_entry(self):
        """Get the argv to run the app as a string.

        Conda parses this by splitting on whitespace, then
        replacing the string "${PREFIX}" inside each arg with the
        environment prefix, then replacing "argv[0]" with the full
        path. See conda/misc.py::launch().

        Returns:
            None if not found

        """
        return self.get_value(['app', 'entry'], default=None)
