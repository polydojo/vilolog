ViloLog
======

Simple blogging engine, built atop [Vilo](https://github.com/polydojo/vilo) and [PogoDB](https://github.com/polydojo/pogodb).

Installation
--------------
```
pip install vilolog
```

ViloLog builds a pure WSGI app. To run that ap, you'll need Gunicorn, Waitress or another WSGI server. Gunicorn is installable via:
```
pip install gunicorn
```

Basic Usage
---------------
#### Minimal Setup:
At the very least, just supply a Postgres connection string to `vilolog.buildApp(.)`.

Create `minimal.py`:
```
import vilolog;
app = vilolog.buildApp("postgres://...dsn..");
wsgi = app.wsgi;
```
Run using Gunicorn:
```
gunicorn minimal:wsgi
```

#### Full Setup:
Via `vilolog.buildApp(.)`, you can configure the blog's title, description, footer, redirects etc. (Currently undocumented.)


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
