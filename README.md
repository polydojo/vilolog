ViloLog
======

Simple blogging platform. Built with Python, atop [Vilo (framework)](https://github.com/polydojo/vilo) and [PogoDB (nosql)](https://github.com/polydojo/pogodb).

ViloLog is a bit like Jekyll, but backed by a database, not the file system.

Installation
--------------
Install via pip:
```
pip install vilolog
```

ViloLog builds a pure WSGI application. To run that application, you'll need Waitress, Gunicorn or another WSGI server. We recommend using Waitress, with Hupper for development:
```
pip install waitress hupper
```

Quickstart
-------------
Pass a Postgres connection string to `vilolog.buildApp(.)` to create your blog.

Create module `blog.py`:
```py
import vilolog;
app = vilolog.buildApp("postgres://...dsn..");
wsgi = app.wsgi;
```
Above, `app` is a Vilo app-container, and `wsgi` is the corresponding pure-WSGI callable. To run `wsgi` via Waitress atop Hupper:
```
hupper -m waitress blog:wsgi
```
Or without Hupper:
```
python -m waitress blog:wsgi
```
Hupper is useful for development and testing, but needn't be used in production.

#### Completing Setup
Once running, [visit `localhost:8080/_setup`](https://localhost:8000/_setup) in your preferred browser to complete setup.

#### Logging In
After completing setup, you should be able to login to your blog. By default, you can log in by visiting `/_login`; but this can be configured via `.buildApp(.)`'s `loginSlug` parameter, documented blow.

Options
----------

`vilolog.buildApp(.)` accepts a number of parameters, only the first of which is required:
- `pgUrl` (*required*, str): Postgres connection string.
- `blogId` (optional, str): Useful if you have multiple blogs.
- `blogTitle` (optional, str): Self explanatory.
- `blogDescription` (optional, str): Self explanatory.
- `footerLine` (optional, str): Footer attribution line.
- `cookieSecret`  (***recommended***, str): Secret for signing (authentication) cookie.
- `antiCsrfSecret` (***recommended***, str): Secret for signing anti-CSRF token.
- `blogThemeDir` (optional, str): Path to custom theme directory. (More on this later.)
- `_adminThemeDir` (*Non-recommended*, str): Path to custom theme directory for the backend-admin UX.
- `devMode` (optional, bool, default:`False`): Enable during development to prevent caching etc.
- `redirectMap` (optional, dict): Mapping from source path to target path.
- `loginSlug` (***recommended***, str, default:`"_login"`): The URL-slug for the login-page for admins. Must begin with `"_login"` and may only contain word  characters, matching `r'\w+'`.
- `disableRemoteLogin`(***recommended***, bool, default:`False`): If truthy, admins must login via localhost only.
- `remoteNetlocList`: (optional, list of str): List of valid remote netlocs that the blog expects to run at. (Doesn't affect localhost.)
- `remoteHttpsOnly` (***recommended***, bool, default:`False`): If truthy, HTTPS will be enforced, except on loclhost.

**Note:** While only `pgUrl` is required, we recommend *explicitly* passing each parameter that's labelled as 'recommended' above, even for picking default values.


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
