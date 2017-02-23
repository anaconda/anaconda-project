A toy API server using Falcon and gunicorn.

This illustrates how to create a custom web app that accepts the
standard Anaconda project command line options. If a command supports
these options (as indicated by the `supports_http_options: true`
flag in anaconda-project.yml), then it can be deployed generically in the
same way as builtin command types such as Bokeh apps and
notebooks.

To run this example:
```
Anaconda project run quote_api  --anaconda-project-port 8081 --anaconda-project-host localhost:8081 --anaconda-project-no-browser --anaconda-project-url-prefix /foo
```

The options are:

  * `--anaconda-project-port` the port to listen on
  * `--anaconda-project-host` the public hostname that browsers will connect to
  * `--anaconda-project-no-browser` don't open a browser showing the app
  * `--anaconda-project-url-prefix` put this prefix in front of all routes
