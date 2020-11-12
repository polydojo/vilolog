ViloLog
======

Simple blogging engine, built atop [Vilo](https://github.com/polydojo/vilo) and [PogoDB](https://github.com/polydojo/pogodb).

Installation
--------------
```
pip install vilolog
```

ViloLog builds a pure WSGI appliation. To run that application, you'll need Gunicorn, Waitress or another WSGI server. Gunicorn is installable via:
```
pip install gunicorn
```

Usage
--------
#### Minimal Setup:
Pass a Postgres connection string to `vilolog.buildApp(.)` to create your blog.

Create module `blog.py`:
```py
import vilolog;
app = vilolog.buildApp("postgres://...dsn..");
wsgi = app.wsgi;
```
Above, `app` is a Vilo app-container, and `wsgi` is the corresponding pure-WSGI callable. To run `wsgi` via Gunicorn:
```
gunicorn blog:wsgi
```

Nascent Stage
------------------
ViloLog is currently in a nascent stage. As work progresses, we'll be adding docs, screenshots, theming, etc.

Licensing
------------
Copyright (c) 2020 Polydojo, Inc.

**Software Licensing:**  
The software is released "AS IS" under the **GNU GPLv3+**, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED. Kindly see [LICENSE.txt](https://github.com/polydojo/vilolog/blob/master/LICENSE.txt) for more details.

**No Trademark Rights:**  
The above software licensing terms **do not** grant any right in the trademarks, service marks, brand names or logos of Polydojo, Inc.
