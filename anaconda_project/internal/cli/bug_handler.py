# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2016, Anaconda, Inc. All rights reserved.
#
# Licensed under the terms of the BSD 3-Clause License.
# The full license is in the file LICENSE.txt, distributed with this software.
# -----------------------------------------------------------------------------
"""Handles uncaught exceptions."""
from __future__ import absolute_import, print_function

import sys

import anaconda_project.internal.cli.console_utils as console_utils
from anaconda_project.internal.slugify import slugify


def handle_bugs(main_func, program_name, details_dict):
    """Invoke main entry point, handling uncaught exceptions.

    Args:
        main_func (function): a main()-style function returning an exit status
        program_name (str): name of the app
        details_dict (dict): dictionary of stuff to include in the bug report file

    Returns:
        an exit status code from main_func or 1 on uncaught exception
    """
    slugified_program_name = slugify(program_name)

    try:
        return main_func()
    except KeyboardInterrupt:
        # KeyboardInterrupt doesn't derive from Exception, but the default handler
        # prints a stack trace which is sort of ugly, so we replace the default
        # with this.
        print("%s was interrupted." % program_name, file=sys.stderr)
        return 1
    except Exception:
        (exception_type, exception_value, exception_trace) = sys.exc_info()

        try:
            import datetime
            import pprint
            import tempfile
            import traceback

            print("An unexpected error occurred, most likely a bug in %s." % program_name, file=sys.stderr)
            print("    (The error was: %s: %s)" % (exception_type.__name__, str(exception_value)), file=sys.stderr)

            # so batch jobs have the details in their logs
            output_to_console = not console_utils.stdin_is_interactive()

            when = datetime.date.today().isoformat()
            prefix = "bug_details_%s_%s_" % (slugified_program_name, when)
            with tempfile.NamedTemporaryFile(prefix=prefix, suffix=".txt", delete=False) as bugfile:
                report_name = bugfile.name

                def output(s):
                    bugfile.write(s.encode('utf-8'))
                    bugfile.write("\n".encode('utf-8'))
                    if output_to_console:
                        print(s, file=sys.stderr)

                output("Bug details for %s error on %s" % (program_name, when))
                output("")
                output("sys.argv: %r" % sys.argv)
                output("")
                output(pprint.pformat(details_dict))
                output("")
                output("\n".join(traceback.format_exception(exception_type, exception_value, exception_trace)))

            if output_to_console:
                print("Above details were also saved to %s" % report_name, file=sys.stderr)
            else:
                print("Details about the error were saved to %s" % report_name, file=sys.stderr)
        except Exception:
            # re-raise the original exception, which is probably more useful
            # than reporting whatever was broken about our bug handling code
            # above.
            raise exception_value

        # exit code
        return 1
