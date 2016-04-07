# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
from __future__ import absolute_import, print_function

from bs4 import BeautifulSoup

_FORM_FIELD_ELEMENTS = ['input', 'textarea', 'select']

_BEAUTIFUL_SOUP_BACKEND = "html.parser"


def _set_element_value(element, value):
    assert value is not None
    value_string = str(value)
    if isinstance(value, bool):
        value_bool = value
    elif 'value' in element.attrs and element['value'] == value_string:
        value_bool = (value_string == element['value'])
    else:
        value_bool = False
    if element.name == 'input':
        if element['type'] == 'checkbox':
            if value_bool:
                element['checked'] = ''
            else:
                del element['checked']
        elif element['type'] == 'radio':
            if value_bool:
                element['checked'] = ''
            else:
                del element['checked']
        elif element['type'] == 'hidden':
            # we don't know what to do with these; right now
            # we use them as a hack to go next to checkboxes
            # and be sure we always send a value for checkbox
            # query params
            pass
        else:
            element['value'] = value_string
    elif element.name == 'textarea':
        element.string = value_string
    elif element.name == 'select':
        options = element.find_all('option')
        for option in options:
            if 'value' in option.attrs:
                option_string = option['value']
            else:
                option_string = option.string
            if option_string == value_string:
                option['selected'] = ''
            else:
                del option['selected']


def cleanup_and_scope_form(html, prefix, values):
    # - parse the html
    # - be sure it's a <form> tag and dump anything that isn't
    # - change form input names to have the prefix
    # - set form input current values to the provided ones
    # - remove the surrounding <form> and replace with a <div>
    #   so we can put it in one big form
    soup = BeautifulSoup(html, _BEAUTIFUL_SOUP_BACKEND)
    if soup.form is None:
        raise ValueError("HTML does not have a root <form> element")
    named = []
    for element_name in _FORM_FIELD_ELEMENTS:
        named = named + soup.form.find_all(element_name)
    for element in named:
        if 'name' in element.attrs:
            name = element['name']
            element['name'] = prefix + name
            value = values.get(name, None)
            if value is not None:
                _set_element_value(element, value)
        else:
            import sys
            print("No 'name' attribute set on %r" % (element), file=sys.stderr)

    # note that this will dump anything that was in the input other than the <form>.
    # don't use prettify() it indents <textarea> contents.
    children_html = "".join(list(map(lambda x: str(x), soup.form.children)))
    return "<div>" + children_html + "</div>"


def html_tag(tag, content):
    """Make a string with given tag and escaped content.

    Get rid of this function once we switch to real templating or something.
    """
    soup = BeautifulSoup("<%s></%s>" % (tag, tag), _BEAUTIFUL_SOUP_BACKEND)
    element = soup.find(tag)
    element.string = content
    return str(element)
