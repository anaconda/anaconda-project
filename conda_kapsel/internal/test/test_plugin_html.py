# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright © 2016, Continuum Analytics, Inc. All rights reserved.
#
# The full license is in the file LICENSE.txt, distributed with this software.
# ----------------------------------------------------------------------------
from conda_kapsel.internal.plugin_html import cleanup_and_scope_form, html_tag

import pytest


def test_html_tag():
    assert "<div></div>" == html_tag("div", "")
    assert "<li>foo</li>" == html_tag("li", "foo")
    assert "<div>&lt;&amp;&gt;</div>" == html_tag("div", "<&>")


def test_cleanup_and_scope_form_requires_form_tag():
    original = """
<div>
  <input type="text" name="foo"/>
</div>
"""

    with pytest.raises(ValueError) as excinfo:
        cleanup_and_scope_form(original, "prefix.", dict(foo="bar"))

    assert "does not have a root <form>" in repr(excinfo.value)


def test_cleanup_and_scope_form_complains_about_missing_name(capsys):
    original = """
<form>
  <input type="text"/>
</form>
"""

    cleanup_and_scope_form(original, "prefix.", dict(foo="bar"))

    out, err = capsys.readouterr()

    assert err == "No 'name' attribute set on <input type=\"text\"/>\n"
    assert out == ""


def test_cleanup_and_scope_form_text_input():
    original = """
<form>
  <input type="text" name="foo"/>
</form>
"""

    cleaned = cleanup_and_scope_form(original, "prefix.", dict(foo="bar"))

    expected = """
<div>
<input name="prefix.foo" type="text" value="bar"/>
</div>
""".strip()

    assert expected == cleaned


def test_cleanup_and_scope_form_multiple_text_inputs():
    original = """
<form>
  <input type="text" name="foo"/>
  <input type="text" name="bar" value="wrong"/>
  <input type="text" name="baz" value=""/>
</form>
"""

    cleaned = cleanup_and_scope_form(original, "prefix.", dict(foo=1, bar=2, baz=3))

    expected = """
<div>
<input name="prefix.foo" type="text" value="1"/>
<input name="prefix.bar" type="text" value="2"/>
<input name="prefix.baz" type="text" value="3"/>
</div>
""".strip()

    assert expected == cleaned


def test_cleanup_and_scope_form_missing_value():
    original = """
<form>
  <input type="text" name="foo"/>
</form>
"""

    # we don't pass in a value for "foo", so the value attribute
    # should be omitted
    cleaned = cleanup_and_scope_form(original, "prefix.", dict())

    expected = """
<div>
<input name="prefix.foo" type="text"/>
</div>
""".strip()

    assert expected == cleaned


def test_cleanup_and_scope_form_textarea():
    original = """
<form>
  <textarea name="foo"/>
</form>
"""

    cleaned = cleanup_and_scope_form(original, "prefix.", dict(foo="bar"))

    expected = """
<div>
<textarea name="prefix.foo">bar</textarea>
</div>
""".strip()

    assert expected == cleaned


def test_cleanup_and_scope_form_checkbox_not_checked():
    original = """
<form>
  <input type="checkbox" name="foo" value="not_bar"/>
</form>
"""

    cleaned = cleanup_and_scope_form(original, "prefix.", dict(foo="bar"))

    expected = """
<div>
<input name="prefix.foo" type="checkbox" value="not_bar"/>
</div>
""".strip()

    assert expected == cleaned


def test_cleanup_and_scope_form_checkbox_checked():
    original = """
<form>
  <input type="checkbox" name="foo" value="bar"/>
</form>
"""

    cleaned = cleanup_and_scope_form(original, "prefix.", dict(foo="bar"))

    expected = """
<div>
<input checked="" name="prefix.foo" type="checkbox" value="bar"/>
</div>
""".strip()

    assert expected == cleaned


def test_cleanup_and_scope_form_checkbox_checked_bool_value():
    original = """
<form>
  <input type="checkbox" name="foo" value="bar"/>
</form>
"""

    cleaned = cleanup_and_scope_form(original, "prefix.", dict(foo=True))

    expected = """
<div>
<input checked="" name="prefix.foo" type="checkbox" value="bar"/>
</div>
""".strip()

    assert expected == cleaned


def test_cleanup_and_scope_form_radio():
    original = """
<form>
  <input type="radio" name="foo" value="1"/>
  <input type="radio" name="foo" value="2" checked/>
  <input type="radio" name="foo" value="3"/>
</form>
"""

    cleaned = cleanup_and_scope_form(original, "prefix.", dict(foo="1"))

    expected = """
<div>
<input checked="" name="prefix.foo" type="radio" value="1"/>
<input name="prefix.foo" type="radio" value="2"/>
<input name="prefix.foo" type="radio" value="3"/>
</div>
""".strip()

    assert expected == cleaned


def test_cleanup_and_scope_form_select_using_value_attribute():
    original = """
<form>
  <select name="foo">
    <option value="1">One</option>
    <option value="2" selected>Two</option>
    <option value="3">Three</option>
  </select>
</form>
"""

    cleaned = cleanup_and_scope_form(original, "prefix.", dict(foo="1"))

    expected = """
<div>
<select name="prefix.foo">
<option selected="" value="1">One</option>
<option value="2">Two</option>
<option value="3">Three</option>
</select>
</div>
""".strip()

    assert expected == cleaned


def test_cleanup_and_scope_form_select_using_element_text():
    original = """
<form>
  <select name="foo">
    <option>1</option>
    <option selected>2</option>
    <option>3</option>
  </select>
</form>
"""

    cleaned = cleanup_and_scope_form(original, "prefix.", dict(foo="1"))

    expected = """
<div>
<select name="prefix.foo">
<option selected="">1</option>
<option>2</option>
<option>3</option>
</select>
</div>
""".strip()

    assert expected == cleaned


def test_cleanup_and_scope_form_leave_hidden_alone():
    original = """
<form>
  <input type="hidden" name="foo" value="bar"/>
</form>
"""

    cleaned = cleanup_and_scope_form(original, "prefix.", dict(foo="blah"))

    # we should NOT set the value on a hidden
    expected = """
<div>
<input name="prefix.foo" type="hidden" value="bar"/>
</div>
""".strip()

    assert expected == cleaned
