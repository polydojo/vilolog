"""
ViloLog: Simple blogging engine, built atop Vilo and PogoDB.

Copyright (c) 2020 Polydojo, Inc.

SOFTWARE LICENSING
------------------
This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.

NO TRADEMARK RIGHTS
-------------------
The above software licensing terms DO NOT grant any right in the
trademarks, service marks, brand names or logos of Polydojo, Inc.
""";

import os;
import uuid;
import time;
import re;
import functools;
import json;
import pprint;

import bcrypt;
import dateutil;

import vilo;
import dotsi;
import pogodb;
import qree;

__version__ = "0.0.1";  # Req'd by flit.
userVersion = 0;
pageVersion = 0;

genId = lambda n=1: "".join(map(lambda i: uuid.uuid4().hex, range(n)));
getNow = lambda: int(time.time());  # Seconds since epoch.
mapli = lambda seq, fn: list(map(fn, seq));
filterli = lambda seq, fn: list(filter(fn, seq));
_b = lambda s, e="utf8": s.encode(e) if type(s) is str else s;
_s = lambda b, e="utf8": b.decode(e) if type(b) is bytes else b;
hashPw = lambda p: _s(bcrypt.hashpw(_b(p), bcrypt.gensalt()));
checkPw = lambda p, h: bcrypt.checkpw(_b(p), _b(h));

############################################################
# Admin Templates: #########################################
############################################################


LAYOUT = r"""
@=# data: {title, bodyHtml}
<!doctype html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/pure/2.0.3/pure-min.css"
        integrity="sha512-FEioxlObRXIskNAQ1/L0byx0SEkfAY+5fO024p9kGEfUQnACGRfCG5Af4bp/7sPNSzKbMtvmcJOWZC7fPX1/FA=="
        crossorigin="anonymous"
    >
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/10.3.2/styles/default.min.css"
        integrity="sha512-kZqGbhf9JTB4bVJ0G8HCkqmaPcRgo88F0dneK30yku5Y/dep7CZfCnNml2Je/sY4lBoqoksXz4PtVXS4GHSUzQ=="
        crossorigin="anonymous"
    >
    <style>
        html, button, input, select, textarea,
        .pure-g [class *= "pure-u"] {
            font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
            font-size: 16px;
        }
        input, textarea { width: 100%; }
        a { text-decoration: none; }
        body {
            max-width: 720px;
            margin: auto;
        }
        blockquote {
            margin: 0;
            padding: 1px 0 1px 16px;
            border-left: 6px solid lightgray;
            color: gray;
            font-size: 18px;
        }
        img { max-width: 100%; }
        
        /* Quick Helpers: */
        .small { font-size: small; }
        .large { font-size: large; }
        .gray { color: gray; }
        .pull-right { float: right; }
        .inlineBlock { display: inline-block; }
        .center { text-align: center; }
        .monaco { font-family: monaco, Consolas, "Lucida Console", monospace; }
        .marginless { margin: 0; }
        .white { color: white; }
        .black { color: black; }
        .red { color: red; }
        .underline { text-decoration: underline; }
        .hidden { display: none; }
        
        .pure-button { border-radius: 4px; }
        .pure-button.thin { padding: 0.25em 0.5em; }
        .pure-button {
            color: black;
            background-color: lightgray;
        }
        .pure-button.pure-button-primary {
            color: white;
            background-color: green;
        }
        
    </style>
    <title>{{: data.title :}}</title>
</head>
<body>

    {{= data.bodyHtml =}}
    
    <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/10.3.2/highlight.min.js" crossorigin="anonymous"
        integrity="sha512-8DnqlIcZT5O7kn55WxWs0PnFyhwCqVEnsDpyHqcadSNtP0eqae406JmIoo2cXT5A42jnlcCw013sdkmK3mEJcQ=="
    ></script>
    <script>hljs.initHighlightingOnLoad();</script>

</body>
</html>
""";

# ----------------------------------------------------------

ADMIN_SETUP = """
<h2>ViloLog Setup</h2>
<form method="POST" class="pure-form pure-form-stacked">
    <p>
        <label>Full Name</label>
        <input type="text" name="name" placeholder="Full Name" required>
    </p>
    <p>
        <label>Email Address</label>
        <input type="email" name="email" placeholder="Email Address" class="monaco" required>
    </p>
    <p>
        <label>Password</label>
        <input type="password" name="password" placeholder="Password" required>
    </p>
    <p><button class="pure-button pure-button-primary">Submit</button></p>
</form>
""";

# ----------------------------------------------------------

ADMIN_LOGIN = """
<h2>ViloLog Login</h2>
<form method="POST" class="pure-form pure-form-stacked">
    <p><input type="email" name="email" placeholder="Email Address" class="monaco" required></p>
    <p><input type="password" name="password" placeholder="Password" required></p>
    <p><button class="pure-button pure-button-primary">Submit</button></p>
</form>
""";

# ----------------------------------------------------------

ADMIN_PAGE_LISTER = """
@= import json;
<h2>ViloLog ~ All Pages</h2>
<nav>
    <a href="/_newPage" class="pure-button">+ New Page</a>
    <a href="/_users" class="pure-button">&gt; Users</a>
    <a href="/_logout" class="pure-button">&gt; Logout</a>
</nav>
<hr>
@= pageList = data.pageList;    # Short alias.
@= if not pageList:
@{
        <br><br>
        <p>No pages yet. Click '+ New Page' above to create your first!</p>
@}
@= else:
@{
    <ul>
        @= for page in pageList:
        @{
            <li id="page_id_{{: page._id :}}">
                <h3 class="inlineBlock" style="margin: 5px 0 0 0;">{{: page.meta.title :}}</h3>
                @= if not page.meta.isDraft:
                @{
                    &nbsp; <a href="/{{: page.meta.slug :}}" class="pure-button small thin">VIEW</a>
                @}
                &nbsp; <a href="/_editPage/{{: page._id :}}" class="pure-button small thin">EDIT</a>
                &nbsp; <span onclick="delPage({{: json.dumps(page._id) :}})" class="pure-button small thin">DEL</span>
            </li>
        @}
    </ul>
    <form id="delForm" class="hidden" method="POST" action="/_deletePage" target="_blank">
        <input name="pageId" value=""><br><br>
        <input name="xCsrfToken"><br><br>
        <button>Submit</button>
    </form>
    <script>
        var delForm = document.getElementById("delForm");
        var delPage = function (pageId) {
            var ckMatch = null, liEl;
            if (! confirm("Confirm?")) {
                return null;    // Short ckt.
            }
            // otherwise ...
            delForm.pageId.value = pageId;
            ckMatch = document.cookie.match(/xCsrfToken\=\"(.+?)\"/);
            delForm.xCsrfToken.value = ckMatch ? ckMatch[1] : "";
            delForm.submit();
            liEl = document.getElementById("page_id_" + pageId);
            liEl.innerHTML = "[DELETING ...]";
        };
    </script>
@}
"""

# ----------------------------------------------------------

ADMIN_PAGE_EDITOR = r"""
@= import json, dotsi, pprint;
@= page = data.page if (data and data.get("page")) else {};
@= defaultMetaDict = {"title":"Sample Page", "slug":"sample-page", "isoDate":"2020-10-31", "template":"page.html", "isDraft":False};
@= defaultMetaJStr = json.dumps(defaultMetaDict, indent=4);

<h2>ViloLog: Page Composer</h2>
<form id="pageForm" method="POST" class="pure-form pure-form-stacked">
    <p>
        <label>Meta <small class="pull-right">Required props: title, slug, date, template, isDraft</small></label>
        <textarea name="meta" placeholder='{{: defaultMetaJStr :}}' rows="6" class="monaco"
            required>{{: json.dumps(page.meta, indent=4) if page.get("meta") else defaultMetaJStr :}}</textarea>
    </p>
    <p>
        <label>Body</label>
        <textarea name="body" placeholder="Body ..." rows="15" class="monaco" required>{{: page.get("body") or "" :}}</textarea>
    </p>
    <p>
        <input type="hidden" name="xCsrfToken" value="">
        <button class="pure-button pure-button-primary">Save</button>
        &nbsp;<span onclick="openPreview()" class="pure-button small">Preview</span>
        <br><br>
        <a href="javascript:history.back();">&lt; Back</a>
    </p>
</form>
<form id="previewForm" method="POST" action="/_previewPage/{{: page.get("_id") or "" :}}"  class="hidden" target="_blank">
    <textarea name="meta"></textarea><br><br>
    <textarea name="body"></textarea><br><br>
    <input name="xCsrfToken"><br><br>
    <button>Submit</button>
</form>
<script>
    var pageForm = document.getElementById("pageForm");
    var alertErr = function (s) {
        alert("Error: " + s);
        return false;
    };
    var submitHandler = function () {
        var meta = null, ckMatch;
        try {
            meta = JSON.parse(pageForm.meta.value);
        } catch (e) {
            return alertErr("Invalid meta JSON");
        }
        if (! (meta.title && typeof(meta.title) === "string")) {
            return alertErr("Invalid/missing meta.title.");
        }
        if (! (meta.slug && typeof(meta.slug) === "string")) {
            return alertErr("Invalid/missing meta.slug.");
        }
        if (! meta.slug.match(/^[a-zA-Z0-9][a-zA-Z0-9_-]+$/)) {
            return alertErr("Non-word characters in meta.slug.");
        }
        if (! (meta.template && typeof(meta.template) === "string")) {
            return alertErr("Invalid/missing meta.template.");
        }
        if (! meta.isoDate.match(/^\d\d\d\d-\d\d-\d\d$/)) {
            return alertErr("Invalid/mising meta.isoDate.");
        }
        if (! meta.template.endsWith(".html")) {
            return alertErr("meta.template doesn't end in '.html'.");
        }
        if (typeof(meta.isDraft) !== "boolean") {
            return alertErr("Invalid/missing meta.isDraft.");
        }
        ckMatch = document.cookie.match(/xCsrfToken\=\"(.+?)\"/);
        pageForm.xCsrfToken.value = ckMatch ? ckMatch[1] : "";
        return true;
    };
    pageForm.onsubmit = submitHandler;  // Alias.
    
    var previewForm = document.getElementById("previewForm");
    var openPreview = function () {
        if (! submitHandler()) { return null; } // Short ckt.
        previewForm.meta.value = pageForm.meta.value;
        previewForm.body.value = pageForm.body.value;
        previewForm.xCsrfToken.value = pageForm.xCsrfToken.value;
        previewForm.submit();
    }
    
</script>
""";

# ----------------------------------------------------------

ADMIN_USER_LISTER = """
<h2>ViloLog ~ All Users</h2>
<nav>
    <a href="/_newUser" class="pure-button">+ New User</a>
    <a href="/_pages" class="pure-button">&gt; Pages</a>
    <a href="/_logout" class="pure-button">&gt; Logout</a>
</nav>
<hr>
@= userList = data.userList;    # Short alias.
<ul>
    @= for user in userList:
    @{
        <li>
            <h3 class="inlineBlock" style="margin: 5px 0 0 0;">{{: user.name :}}</h3>
            &nbsp; ({{: user.role :}})
            &nbsp; <a href="/_editUser/{{: user._id :}}" class="pure-button small thin">EDIT</a>
        </li>
    @}
</ul>
""";

# ----------------------------------------------------------

ADMIN_USER_EDITOR = r"""
@= import json;
@= thatUser = data.thatUser if (data and data.get("thatUser")) else {};
<h2>ViloLog: User Editor</h2>
<form id="userForm" method="POST" class="pure-form pure-form-stacked">
    <p>
        <label>Name</label>
        <input type="text" name="name" value="{{: thatUser.get('name') or '' :}}" placeholder="Full Name" required>
    </p>
    <p>
        <label>Email</label>
        <input type="email" name="email" value="{{: thatUser.get('email') or '' :}}" placeholder="Email Address" class="monaco"
            {{: 'readonly' if thatUser.get('email') else '' :}} required
        >
    </p>
    <p>
        <label>Password <small>{{: "(Update Optionally)" if thatUser else "" :}}</small></label>
        <input type="password" name="password" placeholder="Password" value="">
    </p>
    <p>
        <label>Role</label>
        <input type="text" name="role" placeholder="Role: admin/author/deactivated" value="{{: thatUser.get('role', '') :}}"
            pattern="admin|author|deactivated" required
        >
    </p>
    <p>
        <input type="hidden" name="xCsrfToken" value="">
        <button class="pure-button pure-button-primary">Save</button>
        <br><br><a href="javascript:history.back();">&lt; Back</a>
    </p>
</form>
<script>
    var form = document.getElementById("userForm");
    form.onsubmit = function () {
        var ckMatch = document.cookie.match(/xCsrfToken\=\"(.+?)\"/);
        form.xCsrfToken.value = ckMatch ? ckMatch[1] : "";
        return true;
    };
</script>
""";

############################################################
# Default (Public) Templates: ##############################
############################################################

DEFAULT_HEADER = """
@=# data: {blogTitle, blogDescription}
<header style="border-bottom: 1px solid gray;">
    <h2 style="margin-bottom: 0;"><a href="/" class="gray">{{: data.blogTitle :}}</a></h2>
    <p class="small gray" style="margin-top: 2px;">{{: data.blogDescription :}}</p>
</header>
<br>
""";

DEFAULT_FOOTER = """
@=# data: {footerLine}
<br>
<footer style="border-top: 1px solid gray;">
    <p class="small gray">{{: data.footerLine :}}</p>
</footer>
""";

# ----------------------------------------------------------

DEFAULT_HOME = (DEFAULT_HEADER + """
@=# data: {req, res, pageList, blogTitle}
@= if not data.pageList:
@{
        <br><br><br>
        <p>Nothing here, yet.</p>
@}

@= for page in data.pageList:
@{
    <h3>
        <a href="/{{: page.meta.slug :}}">
            {{: page.meta.title :}}
        </a>
    </h3>
@}
""" + DEFAULT_FOOTER);

# ----------------------------------------------------------

DEFAULT_PAGE = (DEFAULT_HEADER + """
@= import markdown;
{{= "<h1 class='red'>[PREVIEW]</h1>" if data.isPreview else "" =}}
<div class="main">
{{= markdown.markdown(data.currentPage.body, extensions=['fenced_code']) =}}
</div>
""" + DEFAULT_FOOTER);

# ----------------------------------------------------------

DEFAULT_404 = (DEFAULT_HEADER + """
<p class="small gray marginless">404 Not Found</p>
<h1>Oops! That page can't be found!</h1>
<p class="large">
    The page you're looking for is nowhere to be found.
    A search party should soon be dispatched to find it.
</p>
<p>
    <a class="pure-button pure-button-primary large" href="/">Visit Homepage</a>
    &nbsp;<code>OR</code>&nbsp;
    <a class="pure-button large" href="javascript:history.back();">Go Back</a>
</p>
""" + DEFAULT_FOOTER);


############################################################
# Build: ###################################################
############################################################

def buildApp (
        pgUrl,
        blogTitle = "My ViloLog",
        blogDescription = "Yet another ViloLog blog.",
        footerLine = "Powered by ViloLog.",
        cookieSecret = genId(3),
        antiCsrfSecret = genId(3),
        themeDir = None,
    ):
    app = vilo.buildApp();
    wsgi = app.wsgi;
    dbful = pogodb.makeConnector(pgUrl);

    def defaultTpl (innerTpl, data=None):
        data = dotsi.defaults(dotsi.fy({}), data or {}, {
            "blogTitle": blogTitle,
            "blogDescription": blogDescription,
            "title": blogTitle,
            "footerLine": footerLine,
        });
        bodyHtml = qree.renderStr(innerTpl, data=data);
        return qree.renderStr(LAYOUT, dotsi.fy({
            "title": data.title, "bodyHtml": bodyHtml,
        }));

    def oneline (sentence):
        spPaths = re.findall(r"\s/_\w+", sentence);
        # ^ Pattern: <space> <slash> <underscore> <onePlusWordChars>
        for spPath in spPaths:
            path = spPath.strip();
            link = "<a href='%s'><code>%s</code></a>" % (path, path);
            sentence = sentence.replace(path, link, 1);
        sentence = "<br><br>" + sentence + """<br><br>
            <a href='javascript:history.back();'>&lt; Back</a>
        """;
        return qree.renderStr(LAYOUT, data=dotsi.fy({
            "title": blogTitle,
            "bodyHtml": sentence,
        }));
    
    def customTpl (filename, req, res, data=None):
        data = dotsi.defaults(dotsi.fy({}), data or {}, {
            "blogTitle": blogTitle,
            "blogDescription": blogDescription,
            "req": req, "res": res,
        });
        path = os.path.join(themeDir, filename);
        return qree.renderPath(path, data=data);
    
    def autoTpl (filename, innerTpl, req, res, data=None):
        if not themeDir:
            return defaultTpl(innerTpl, data);
        # otherwise ...
        return customTpl(filename, req, res, data);
        

    ########################################################
    # Authentication Helpers: ##############################
    ########################################################

    def startLoginSession (user, res):
        res.setCookie("userId", user._id, cookieSecret);
        xCsrfToken = vilo.signWrap(user._id, antiCsrfSecret);
        res.setUnsignedCookie("xCsrfToken", xCsrfToken, {"httponly": False});
        return res;

    def clearLoginSession (res):
        res.setCookie("userId", "");
        res.setCookie("xCsrfToken", "");

    def getCurrentUser (db, req):
        errLine = "Session expired. Please /_logout and then /_login again.";
        userId = req.getCookie("userId", cookieSecret);
        #print("userId =", userId);
        if not userId:
            raise vilo.error(oneline(errLine));
        if req.getVerb() != "GET":
            xCsrfToken = req.fdata.get("xCsrfToken") or "";
            xUserId = vilo.signUnwrap(xCsrfToken, antiCsrfSecret);
            #print("repr xUserId = ", repr(xUserId));
            if userId != xUserId:
                raise vilo.error(oneline("CSRF invalid. " + errLine));
        # otherwise ...
        user = db.findOne(userId);
        #print("user =", user);
        if not (user and user.type == "user"):
            raise vilo.error(oneline(errLine));
        if user.role == "deactivated":
            raise vilo.error(oneline("Access deactivated."));
        return user;

    def authful (oFunc):
        @dbful
        def nFunc(req, res, db, *args, **kwargs):
            user = getCurrentUser(db, req);
            return oFunc(req, res, db=db, user=user, *args, **kwargs);
        return functools.update_wrapper(nFunc, oFunc);
    
    def validatePageEditDelRole (user, page):
        assert user.role != "deactivated";
        if user.role == "admin":
            return True;
        if user.role == "author" and user._id == page.authorId:
            return True;
        raise vilo.error(oneline("""Access denied.
            Only admins and authors can edit/delete pages.
        """));
        

    ########################################################
    # Setup: ###############################################
    ########################################################

    @app.route("GET", "/_hello")
    def get_hello (req, res):
        return oneline("Hello, I'm the /_hello route! Try: /_setup");
    
    @app.route("GET", "/_setup")
    @dbful
    def get_setup (req, res, db):
        anyUser = db.findOne({"type": "user"});
        if anyUser:
            return oneline("Setup previously completed. Visit: /_login");
        return defaultTpl(ADMIN_SETUP);

    def validateUser (user):
        assert type(user) in [dict, dotsi.Dict];
        user = dotsi.fy(user);
        assert user._id and type(user._id) is str;
        assert type(user.version) is int;
        assert user.type == "user";
        assert user.name and type(user.name) is str;
        assert user.email and type(user.email) is str;
        assert re.match(r"^\S+@\S+\.\S+$", user.email);
        assert user.hpw and type(user.hpw) is str;
        assert user.createdAt and type(user.createdAt) is int;
        assert user.role in ["admin", "author", "deactivated"];
        return True;
    
    def buildUser (name, email, password, role):
        user = dotsi.fy({
            "_id": genId(),
            "version": userVersion,
            "type": "user",
            "name": name,
            "email": email,
            "hpw": hashPw(password),
            "createdAt": getNow(),
            "role": role,
        });
        assert validateUser(user);
        return user;

    @app.route("POST", "/_setup")
    @dbful
    def post_setup (req, res, db):
        anyUser = db.findOne({"type": "user"});
        if anyUser:
            return oneline("Setup previously completed. Visit: /_login");
        d = req.fdata;
        user = buildUser(d.name, d.email, d.password, role="admin");
        db.insertOne(user);
        return oneline("Done! Setup complete. Proceed to: /_login");


    @app.route("GET", "/_resetAll")
    @authful
    def get_reset (req, res, user, db):
        assert user.role == "admin";
        sure = req.qdata.get("sure") or "no";
        if sure != "True":
            return oneline("Aborted. Pass ?sure=True if you're really sure.");
        db.clearTable(sure=True);
        return oneline("Done! Proceed to: /_setup");

    @app.route("GET", "/_resetPages")
    @authful
    def get_reset (req, res, user, db):
        assert user.role == "admin";
        sure = req.qdata.get("sure") or "no";
        if sure != "True":
            return oneline("Aborted. Pass ?sure=True if you're really sure.");
        pageList = getPageList(db, inclDrafts=True);
        for page in pageList:
            db.deleteOne(page._id);
        return oneline(vilo.escfmt(
            "Done! Deleted %s pages. See: /pages", len(pageList),
        ));

    ########################################################
    # Login/logout: ########################################
    ########################################################

    @app.route("GET", "/_login")
    def get_login (req, res):
        return defaultTpl(ADMIN_LOGIN);

    @app.route("POST", "/_login")
    @dbful
    def post_login (req, res, db):
        d = req.fdata;
        user = db.findOne({"type": "user", "email": d.email});
        if not user:
            return oneline("Email not recognized.");
        if not checkPw(d.password, user.hpw):
            return oneline("Email/password mismatch.");
        if user.role == "deactivated":
            return oneline("Access deactivated.");
        startLoginSession(user, res);
        return oneline("Done! Proceed to: /_pages");

    @app.route("GET", "/_logout")
    def get_logout (req, res):
        clearLoginSession(res);
        return oneline("You've logged out. Visit /_login to log back in.");

    ########################################################
    # Page Management: #####################################
    ########################################################
    
    def getPageList (db, inclDrafts):
        assert type(inclDrafts) is bool;
        # TODO: Some sort of caching.
        if inclDrafts:
            return db.find({"type": "page"});
        # otherwise ...
        return db.find({"type": "page", "meta": {"isDraft": False}});
    
    @app.route("GET", "/_pages")
    @authful
    def get_pages (req, res, db, user):
        pageList = getPageList(db, inclDrafts=True);
        return defaultTpl(ADMIN_PAGE_LISTER, data={
            "pageList": pageList,
        });

    @app.route("GET", "/_newPage")
    @authful
    def get_newPage (req, res, db, user):
        return defaultTpl(ADMIN_PAGE_EDITOR);

    def validatePage (page):
        "Validates `page` schema.";
        assert type(page) in [dict, dotsi.Dict];
        page = dotsi.fy(page);
        assert page._id and type(page._id) is str;
        assert type(page.version) is int;
        assert page.type == "page";
        # Meta Starts:
        assert type(page.meta) == dotsi.Dict;
        meta = page.meta;
        assert meta.title and type(meta.title) is str;
        assert meta.slug and type(meta.slug) is str;
        assert re.match(r"^[a-zA-Z0-9][a-zA-Z0-9_-]+$", meta.slug);
        assert meta.isoDate and type(meta.isoDate) is str;
        assert re.match(r"^\d\d\d\d-\d\d-\d\d$", meta.isoDate);
        assert meta.template and type(meta.template) is str;
        assert meta.template.endswith(".html");
        assert type(meta.isDraft) is bool;
        # Meta Ends;
        assert page.body and type(page.body) is str;
        assert page.authorId and type(page.authorId) is str;
        assert page.createdAt and type(page.createdAt) is int;
        return True;
    
    def buildPage (meta, body, author, _id=None):
        page = dotsi.fy({
            "_id": _id or genId(),
            "version": pageVersion,
            "type": "page",
            "meta": meta,
            "body": body,
            "authorId": author._id,
            "createdAt": getNow(),
        });
        assert validatePage(page);
        return page;

    @app.route("POST", "/_newPage")
    @authful
    def post_newPage (req, res, db, user):
        d = req.fdata;
        assert d.body and d.meta;
        meta = dotsi.fy(json.loads(d.meta));
        #pprint.pprint(d);
        page = buildPage(meta=meta, body=d.body, author=user);
        #pprint.pprint(page);
        db.insertOne(page);
        return oneline(vilo.escfmt(
            "Done! <a href='/%s'>View page</a> or proceed to: /_pages", page.meta.slug,
        ));

    @app.route("GET", "/_editPage/*")
    @authful
    def get_edit_byId (req, res, db, user):
        pageId = req.wildcards[0];
        page = db.findOne(pageId);
        if not (page and page.type == "page"):
            raise vilo.error(oneline("No such page."));
        assert validatePageEditDelRole(user, page);
        return defaultTpl(ADMIN_PAGE_EDITOR, data={
            "page": page,
        });

    @app.route("POST", "/_editPage/*")
    @authful
    def post_edit_byId (req, res, db, user):
        pageId = req.wildcards[0];
        page = db.findOne(pageId);
        if not (page and page.type == "page"):
            raise vilo.error(oneline("No such page."));
        assert validatePageEditDelRole(user, page);
        d = req.fdata;
        meta = dotsi.fy(json.loads(d.meta));
        page.update({"meta": meta, "body": d.body});
        assert validatePage(page);
        db.replaceOne(page);
        return oneline(vilo.escfmt(
            "Done! <a href='/%s'>View page,</a> <a href=''>re-edit it</a>, or proceed to: /_pages", meta.slug,
        ));

    @app.route("POST", "/_previewPage/")                    # Very similar to the publicly-accessible "/*" route.
    @app.route("POST", "/_previewPage/*")                   # <-^ 
    @authful
    def post_pagePreview (req, res, db, user):
        pageId = req.wildcards[0] if req.wildcards else None;
        pageList = getPageList(db, inclDrafts=True);
        cPgList = filterli(pageList, lambda p: p._id == pageId);
        assert len(cPgList) <= 1;
        f = req.fdata;
        meta = dotsi.fy(json.loads(f.meta));
        currentPage = cPgList[0] if cPgList else buildPage(
            meta=meta, body=f.body, author=user,
        );
        currentPage.update({"meta": meta, "body": f.body});
        return autoTpl(currentPage.meta.template or "page.html",
            DEFAULT_PAGE, req, res, data={
                "pageList": pageList,
                "currentPage": currentPage,
                "title": currentPage.meta.title + " // " + blogTitle,
                "isPreview": True,
            },
        );
    
    @app.route("POST", "/_deletePage")
    @authful
    def post_deletePage (req, res, db, user):
        pageId = req.fdata.pageId;
        page = db.findOne(pageId);
        if not (page and page.type == "page"):
            raise vilo.error(oneline("No such page."));
        # otherwise ...
        assert validatePageEditDelRole(user, page);
        db.deleteOne(page._id);
        return oneline(vilo.escfmt("""Page deleted.
            <a href="javascript:window.close();">Close window</a>
            or proceed to: /_pages
            <script>
                var oDoc = window.opener.document;
                var oElm = oDoc.getElementById("page_id_%s");
                oElm.innerHTML = "[DELETED]";
            </script>
        """, page._id));

    ########################################################
    # User Management: #####################################
    ########################################################

    @app.route("GET", "/_users")
    @authful
    def get_users (req, res, db, user):
        userList = db.find({"type": "user"});
        return defaultTpl(ADMIN_USER_LISTER, data={
            "userList": userList,
        });

    @app.route("GET", "/_newUser")
    @authful
    def get_newUser (req, res, db, user):
        currentUser = user;
        del user;
        if currentUser.role != "admin":
            return oneline("Access denied. Only admins can add users.");
        # otherwise ...
        return defaultTpl(ADMIN_USER_EDITOR);

    @app.route("POST", "/_newUser")
    @authful
    def post_newUser(req, res, db, user):
        currentUser = user; # Alias.
        del user;           # Remove default alias from memory.
        if currentUser.role != "admin":
            return "Access denied. Only admins can add users.";
        # otherwise ...
        d = req.fdata;
        existingUser = db.findOne({"type": "user", "email": d.email});
        if existingUser:
            return "Error: Email address already registered.";
        # otherwise ...
        newUser = buildUser(d.name, d.email, d.password, d.role);
        db.insertOne(newUser);
        return oneline("Done! New user created. Visit: /_users");

    @app.route("GET", "/_editUser/*")
    @authful
    def get_editUser (req, res, db, user):
        thatUserId = req.wildcards[0];
        currentUser = user;
        del user;
        if currentUser.role != "admin":
            return oneline("Access denied. Only admins can edit users.");
        # otherwise ...
        thatUser = db.findOne(thatUserId);
        assert thatUser and thatUser.type == "user";
        return defaultTpl(ADMIN_USER_EDITOR, data={
            "thatUser": thatUser,
        });

    @app.route("POST", "/_editUser/*")
    @authful
    def post_editUser(req, res, db, user):
        thatUserId = req.wildcards[0];
        currentUser = user;
        del user;
        if currentUser.role != "admin":
            return oneline("Access denied. Only admins can edit users.");
        # otherwise ...
        thatUser = db.findOne(thatUserId);
        if not (thatUser and thatUser.type == "user"):
            return oneline("No such user. See: /_users");
        # otherwise ...
        f = req.fdata;
        thatUser.update({"name": f.name, "role": f.role});  # TODO: Allow email update?
        if f.password:
            thatUser.update({"hpw": hashPw(f.password)});
        assert validateUser(thatUser);
        db.replaceOne(thatUser);
        return oneline("Done! User upated. See: /_users");

    ########################################################
    # Serving Content: #####################################
    ########################################################

    @app.route("GET", "/")
    @dbful
    def get_homepage (req, res, db):
        pageList = getPageList(db, inclDrafts=False);
        return autoTpl("home.html", DEFAULT_HOME, req, res, data={
            "pageList": pageList,
        });
    
    #TODO/Consider:
    #@app.route("GET", "/robots.txt")
    #def get_robotsTxt (req, res):
    #    res.contentType = "text/plain";
    #    return "";

    @app.route("GET", "/sitemap.txt")
    @dbful
    def get_sitemapTxt (req, res, db):
        pageList = getPageList(db, inclDrafts=False);
        schHost = req.splitUrl.scheme + "://" + req.splitUrl.netloc;
        # ^ Scheme w/ netloc. (Netloc includes port.)
        pageUrlList = mapli(pageList, lambda p: schHost + "/" + p.meta.slug);
        res.contentType = "text/plain";
        return "\n".join(pageUrlList);
    
    @app.route("GET", "/*")
    @dbful
    def get_pageBySlug (req, res, db):
        slug = req.wildcards[0];
        pageList = getPageList(db, inclDrafts=False);
        slugPageList = filterli(pageList,
            lambda page: page.meta.slug == slug,
        ); 
        if len(slugPageList) > 1:
            raise vilo.error(oneline("<h2>Slug Overloaded!</h2>"));
        if not slugPageList:
            raise vilo.error(autoTpl("404.html", DEFAULT_404, req, res, data={
                "pageList": pageList,
            }));
        # otherwise ...
        assert len(slugPageList) == 1;
        currentPage = slugPageList[0];
        if currentPage.meta.isDraft:
            raise vilo.error(autoTpl("404.html", DEFAULT_404, req, res, data={
                "pageList": pageList,
            }));
        # otherwise ...
        return autoTpl(currentPage.meta.template or "page.html",
            DEFAULT_PAGE, req, res, data={
                "pageList": pageList,
                "currentPage": currentPage,
                "title": currentPage.meta.title + " // " + blogTitle,
                "isPreview": False,
            },
        );
        
    # TODO: Consider using `if themeDir` guard.
    @app.route("GET", "/static/**")
    def get_static (req, res):
        relPath = req.wildcards[0];
        path = oos.path.join(themeDir, "static/" + relPath);
        return res.staticFile();

    ########################################################
    # Return built `app`: ##################################
    ########################################################
    return app;

# End ######################################################
