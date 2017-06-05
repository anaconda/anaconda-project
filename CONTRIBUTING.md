# Mechanics

Here's how to work on the code:

 * `python setup.py test` is configured to run all the checks that
   have to pass before you commit or push. It also reformats the
   code with yapf if necessary. Continuous integration runs this
   command so you should run it and make it pass before you push
   to the repo.
 * To only run the formatter and linter, use `python setup.py test
   --format-only`.
 * If you have added but uncommitted changes, you can use use `python setup.py test
   --format-only --git-staged-only` to lint only the added files.
 * To only run the tests, use `python -m pytest -vv anaconda_project`
 * To only run a single file of tests use `python -m pytest
   -vv anaconda_project/test/test_foo.py`
 * To only run a single test function `python -m pytest
   -vv anaconda_project/test/test_foo.py::test_something`
 * To run only "fast" tests, use `python -m pytest -vv -k-slow
   anaconda_project` which skips slow tests. Slow tests have to
   pass in CI, but often it's helfpul to get all the fast tests
   working before debugging the slow ones.
 * There's a script `build_and_upload.sh` that should be used to
   manually make a release. The checked-out revision should have
   a version tag prior to running the script.
