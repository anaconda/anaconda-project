A toy API server using Falcon and gunicorn.

This illustrates how to create a custom web app that accepts the
standard conda kapsel command line options. If a command supports
these options (as indicated by the `supports_http_options: true`
flag in kapsel.yml), then it can be deployed generically in the
same way as builtin command types such as Bokeh apps and
notebooks.

To run this example:
```
conda kapsel run quote_api  --kapsel-port 8081 --kapsel-host example.com --kapsel-no-browser --kapsel-url-prefix /foo
```

The options are:

  * `--kapsel-port` the port to listen on
  * `--kapsel-host` the public hostname that browsers will connect to
  * `--kapsel-no-browser` don't open a browser showing the app
  * `--kapsel-url-prefix` put this prefix in front of all routes
