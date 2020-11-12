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
import traceback;

import bcrypt;
import dateutil;

import vilo;
import dotsi;
import pogodb;
import qree;

__version__ = "0.0.3";  # Req'd by flit.
USER_VERSION = 0;
PAGE_VERSION = 0;

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
        code { background-color: lightgray; }
        
        /* Quick Helpers: */
        .small { font-size: small; }
        .large { font-size: large; }
        .gray { color: gray; }
        .pull-right { float: right; }
        .inlineBlock { display: inline-block; }
        .center { text-align: center; }
        .monaco, pre, code { font-family: monaco, Consolas, "Lucida Console", monospace; }
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
    <script>
        var getXCsrfToken = function () {
            var ckMatch = document.cookie.match(/xCsrfToken\=\"(.+?)\"/);
            return ckMatch ? ckMatch[1] : "";
        };
    </script>
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

ADMIN_RESET = r"""
<h1>Danger Zone!</h1>
<form id="resetForm" method="POST" class="hidden">
    <input type="hidden" name="xCsrfToken">
</form>
<p>
    To delete all the data, click the button below.<br>
    <span class="pure-button" onclick="resetClickHandler('/_resetFull');">Reset All</span>
</p>
<p>
    To delete all pages, click the button below.<br>
    <span class="pure-button" onclick="resetClickHandler('/_resetPages');">Reset Pages</span>
</p>
<script>
    var resetForm = document.getElementById("resetForm");
    var resetClickHandler = function (actionTgt) {
        if (! confirm("Are you sure?")) { return null; }
        resetForm.xCsrfToken.value = getXCsrfToken();
        resetForm.setAttribute("action", actionTgt);
        resetForm.submit();
    };
</script>
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
    <form id="delForm" class="hidden" method="POST" action="/_deletePage" data-not-target="_blank">
        <input name="pageId" value=""><br><br>
        <input name="xCsrfToken"><br><br>
        <button>Submit</button>
    </form>
    <script>
        var delForm = document.getElementById("delForm");
        var delPage = function (pageId) {
            var pageElm = null;
            if (! confirm("Confirm?")) {
                return null;    // Short ckt.
            }
            // otherwise ...
            delForm.pageId.value = pageId;
            delForm.xCsrfToken.value = getXCsrfToken();
            delForm.submit();
            pageElm = document.getElementById("page_id_" + pageId);
            pageElm.innerHTML = "[DELETING ... ]";
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
        var meta = null;
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
        pageForm.xCsrfToken.value = getXCsrfToken();
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
        form.xCsrfToken.value = getXCsrfToken();
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
        <br><br>
        <p>Nothing here, yet.</p>
        <br><br>
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
<br>
<div>
    @= if data.nextPage:
    @{
        <div>Next: <a href="/{{: data.nextPage.meta.slug :}}">{{: data.nextPage.meta.title :}}</a></div>
    @}
    @= if data.prevPage:
    @{
        <div>Previous: <a href="/{{: data.prevPage.meta.slug :}}">{{: data.prevPage.meta.title :}}</a></div>
    @}
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
# User Model: ##############################################
############################################################

def validateUser (user):
    assert type(user) in [dict, dotsi.Dict];
    user = dotsi.fy(user);
    assert user._id and type(user._id) is str;
    assert user.version == USER_VERSION;
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
        "version": USER_VERSION,
        "type": "user",
        "name": name,
        "email": email,
        "hpw": hashPw(password),
        "createdAt": getNow(),
        "role": role,
    });
    assert validateUser(user);
    return user;

def adaptUser (db, user):
    assert user.version == USER_VERSION;
    return user;

def getUser (db, subdoc):
    if type(subdoc) is str:
        subdoc = {"_id": subdoc};
    user.update({"type": "user"});
    user = db.findOne(subdoc);
    if not user: return None;
    return adaptUser(db, version);

def getUserList (db, subdoc):
    subdoc.update({"type": "user"});
    userList = db.find(subdoc);
    return mapli(userList, lambda user: adaptPage(db, user));

############################################################
# Page Model: ##############################################
############################################################

def validatePage (page):
    "Validates `page` schema.";
    assert type(page) in [dict, dotsi.Dict];
    page = dotsi.fy(page);
    assert page._id and type(page._id) is str;
    assert page.version == PAGE_VERSION;
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
        "version": PAGE_VERSION,
        "type": "page",
        "meta": meta,
        "body": body,
        "authorId": author._id,
        "createdAt": getNow(),
    });
    assert validatePage(page);
    return page;

def adaptPage (db, page):
    assert page.version == PAGE_VERSION;
    return page;

def getPage (db, subdoc):
    if type(subdoc) is str:
        subdoc = {"_id": subdoc};
    subdoc.update({"type": "page"});
    page = db.findOne(subdoc);
    if not page: return None;
    return adaptPage(db, page);

def getNextAndPrevPages (db, page):
    subdoc = {"meta": {"template": page.meta.template}};
    nextPage = db.findOne(subdoc, whereEtc="""
        AND doc->'meta'->>'isoDate' > %s
        ORDER BY doc->'meta'->>'isoDate' ASC
    """, argsEtc=[page.meta.isoDate]);
    prevPage = db.findOne(subdoc, whereEtc="""
        AND doc->'meta'->>'isoDate' < %s
        ORDER BY doc->'meta'->>'isoDate' DESC
    """, argsEtc=[page.meta.isoDate]);
    if nextPage:
        nextPage = adaptPage(db, nextPage);
    if prevPage:
        prevPage = adaptPage(db, prevPage);
    return [nextPage, prevPage];

def getPageList (db, subdoc):
    subdoc.update({"type": "page"});
    pageList = db.find(subdoc);
    pageList = mapli(pageList, lambda p: adaptPage(db, p));
    pageList.sort(key=lambda p: p.meta.isoDate, reverse=True);
    return pageList;

def getAllPages_inclDrafts (db):
    return getPageList(db, {});
def getAllPages_exclDrafts (db):
    return getPageList(db, {"meta": {"isDraft": False}});


############################################################
# Build: ###################################################
############################################################

def buildApp (
        pgUrl, # 1st positional param
        blogTitle = "My ViloLog Blog",
        blogDescription = "Yet another ViloLog blog.",
        footerLine = "Powered by ViloLog.",
        cookieSecret = genId(3),
        antiCsrfSecret = genId(3),
        themeDir = None,
        devMode = False,
        redirectMap = None,
    ):
    redirectMap = redirectMap or {};
    app = vilo.buildApp();
    wsgi = app.wsgi;
    dbful = pogodb.makeConnector(pgUrl);
    if devMode: app.setDebug(True);
    
    ########################################################
    # Templating Helpers: ##################################
    ########################################################
    
    def validateThemeDir ():
        if themeDir is None:
            return True;
        if not os.path.isdir(themeDir):
            raise ValueError("No such directory: %s" % themeDir);
        themeSlash = lambda x: os.path.join(themeDir, x);
        for fname in ["home.html", "page.html", "404.html"]:
            if not os.path.isfile(themeSlash(fname)):
                raise ValueError("Theme doesn't include file: %s" % fname);
        if not os.path.isdir(themeSlash("static")):
            raise ValueError("Theme doesn't include directory: static/");
        return True;
    validateThemeDir(); # Called immediately.

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

    def oneLine (sentence, seq=()):
        "Helper for producing one-line responses.";
        if seq is not ():
            sentence = vilo.escfmt(sentence, seq);
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
    
    def errLine (sentence, seq=()):
        "Helper for producing one-line error responses.";
        return vilo.error(oneLine(sentence, seq));
    
    def customTpl (filename, req, res, data=None):
        "Helper for rendering custom (`themeDir`) templates.";
        data = dotsi.defaults(dotsi.fy({}), data or {}, {
            "blogTitle": blogTitle,
            "blogDescription": blogDescription,
            "req": req, "res": res,
            "renderTpl": lambda filename, data=None: customTpl(
                filename, req, res, data=data,
            ),
            "footerLine": footerLine,
        });
        path = os.path.join(themeDir, filename);
        #path = os.path.abspath(path);
        try:
            return qree.renderPath(path, data=data);
        except IOError as e:
            # Note: Err may even be caused by a nested tpl.
            print("\n" + traceback.format_exc() + "\n");
            raise errLine("ERROR: Template <code>%s</code> not found.",
                e.filename,
            );
    
    def autoTpl (filename, innerTpl, req, res, data=None):
        "Helper, auto-picks between custom/default templates.";
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
        return res.redirect("/_pages");

    def clearLoginSession (res):
        res.setCookie("userId", "");
        res.setCookie("xCsrfToken", "");

    def getCurrentUser (db, req):
        errMsg = "Session expired. Please /_logout and then /_login again.";
        userId = req.getCookie("userId", cookieSecret);
        #print("userId =", userId);
        if not userId:
            raise errLine(errMsg);
        if req.getVerb() != "GET":
            xCsrfToken = req.fdata.get("xCsrfToken") or "";
            xUserId = vilo.signUnwrap(xCsrfToken, antiCsrfSecret);
            #print("repr xUserId = ", repr(xUserId));
            if userId != xUserId:
                raise errLine("CSRF invalid. " + errMsg);
        # otherwise ...
        user = db.findOne(userId);
        #print("user =", user);
        if not (user and user.type == "user"):
            raise errLine(errMsg);
        if user.role == "deactivated":
            raise errLine("Access deactivated.");
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
        raise errLine("""Access denied.
            Only admins and authors can edit/delete pages.
        """);
        

    ########################################################
    # Setup: ###############################################
    ########################################################

    @app.route("GET", "/_hello")
    def get_hello (req, res):
        return oneLine("Hello, I'm the /_hello route! Try: /_setup");
    
    @app.route("GET", "/_setup")
    @dbful
    def get_setup (req, res, db):
        anyUser = db.findOne({"type": "user"});
        if anyUser:
            raise errLine("Setup previously completed. Visit: /_login");
        return defaultTpl(ADMIN_SETUP);

    @app.route("POST", "/_setup")
    @dbful
    def post_setup (req, res, db):
        anyUser = db.findOne({"type": "user"});
        if anyUser:
            raise errLine("Setup previously completed. Visit: /_login");
        d = req.fdata;
        user = buildUser(d.name, d.email, d.password, role="admin");
        db.insertOne(user);
        #return oneLine("Done! Setup complete. Proceed to: /_login");
        #return res.redirect("/_login");
        return startLoginSession(user, res);
    
    @app.route("GET", "/_reset")
    @authful
    def get_reset (req, res, user, db):
        assert user.role == "admin";
        return defaultTpl(ADMIN_RESET);

    @app.route("POST", "/_resetFull")
    @authful
    def get_reset (req, res, user, db):
        assert user.role == "admin";
        db.clearTable(sure=True);
        #return oneLine("Done! Proceed to: /_setup");
        return res.redirect("/_setup");

    @app.route("POST", "/_resetPages")
    @authful
    def get_reset (req, res, user, db):
        assert user.role == "admin";
        pageList = getAllPages_inclDrafts(db);
        for page in pageList:
            db.deleteOne(page._id);
        #return oneLine(vilo.escfmt(
        #    "Done! Deleted %s pages. See: /_pages", len(pageList),
        #));
        return res.redirect("/_pages");

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
            raise errLine("Email not recognized.");
        if not checkPw(d.password, user.hpw):
            raise errLine("Email/password mismatch.");
        if user.role == "deactivated":
            raise errLine("Access deactivated.");
        return startLoginSession(user, res);
        #return oneLine("Done! Proceed to: /_pages");

    @app.route("GET", "/_logout")
    def get_logout (req, res):
        clearLoginSession(res);
        return oneLine("You've logged out. Visit /_login to log back in.");

    ########################################################
    # Page Management: #####################################
    ########################################################
    
    @app.route("GET", "/_pages")
    @authful
    def get_pages (req, res, db, user):
        pageList = getAllPages_inclDrafts(db);
        return defaultTpl(ADMIN_PAGE_LISTER, data={
            "pageList": pageList,
        });

    @app.route("GET", "/_newPage")
    @authful
    def get_newPage (req, res, db, user):
        assert user.role in ["author", "admin"];
        return defaultTpl(ADMIN_PAGE_EDITOR);

    @app.route("POST", "/_newPage")
    @authful
    def post_newPage (req, res, db, user):
        assert user.role in ["author", "admin"];
        assert req.fdata.body and req.fdata.meta;
        meta = dotsi.fy(json.loads(req.fdata.meta));
        sameSlugPage = getPage(db, {"meta": {"slug": meta.slug}});
        if sameSlugPage:
            raise errLine("Slug already taken. Try another?");
        #pprint.pprint(f);
        page = buildPage(meta, req.fdata.body, author=user);
        #pprint.pprint(page);
        db.insertOne(page);
        return oneLine(vilo.escfmt("""Done!
            <a href='/%s'>View page</a>,
            <a href='/_editPage/%s'>edit it</a>,
             or proceed to: /_pages""", [
                page.meta.slug, page._id,
            ],
        ));

    @app.route("GET", "/_editPage/*")
    @authful
    def get_edit_byId (req, res, db, user):
        pageId = req.wildcards[0];
        page = getPage(db, pageId);
        if not page: raise errLine("No such page.");
        assert validatePageEditDelRole(user, page);
        return defaultTpl(ADMIN_PAGE_EDITOR, data={
            "page": page,
        });

    @app.route("POST", "/_editPage/*")
    @authful
    def post_edit_byId (req, res, db, user):
        pageId = req.wildcards[0];
        page = getPage(db, pageId);
        if not page: raise errLine("No such page.");
        oldSlug = page.meta.slug;
        assert validatePageEditDelRole(user, page);
        meta = dotsi.fy(json.loads(req.fdata.meta));
        newSlug = meta.slug;
        if oldSlug != newSlug:
            sameSlugPage = getPage(db, {"meta": {"slug": newSlug}});
            if sameSlugPage:
                raise errLine("Slug already taken. Try another?");
        page.update({"meta": meta, "body": req.fdata.body});
        assert validatePage(page);
        db.replaceOne(page);
        return oneLine(vilo.escfmt("""Done!
            <a href='/%s'>View page,</a>
            <a href=''>re-edit it</a>,
            or proceed to: /_pages""", meta.slug,
        ));

    @app.route("POST", "/_previewPage/")                    # Very similar to the publicly-accessible "/*" route.
    @app.route("POST", "/_previewPage/*")                   # <-^ 
    @authful
    def post_pagePreview (req, res, db, user):
        pageId = req.wildcards[0] if req.wildcards else None;
        currentPage = getPage(db, pageId);
        meta = dotsi.fy(json.loads(req.fdata.meta));
        currentPage.update({"meta": meta, "body": req.fdata.body});
        nextPage, prevPage = getNextAndPrevPages(db, currentPage);
        return autoTpl(
            currentPage.meta.template, DEFAULT_PAGE, req, res, data={
                "currentPage": currentPage,
                "title": currentPage.meta.title + " // " + blogTitle,
                "isPreview": True,
                "nextPage": nextPage,
                "prevPage": prevPage,
            },
        );
    
    @app.route("POST", "/_deletePage")
    @authful
    def post_deletePage (req, res, db, user):
        pageId = req.fdata.pageId;
        page = getPage(db, pageId);
        if not page: raise errLine("No such page.");
        assert validatePageEditDelRole(user, page);
        db.deleteOne(page._id);
        return res.redirect("/_pages");

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
            raise errLine("Access denied. Only admins can add users.");
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
        return res.redirect("/_users");

    @app.route("GET", "/_editUser/*")
    @authful
    def get_editUser (req, res, db, user):
        thatUserId = req.wildcards[0];
        currentUser = user;
        del user;
        if currentUser.role != "admin":
            raise errLine("Access denied. Only admins can edit users.");
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
            raise errLine("Access denied. Only admins can edit users.");
        # otherwise ...
        thatUser = db.findOne(thatUserId);
        if not (thatUser and thatUser.type == "user"):
            raise errLine("No such user. See: /_users");
        # otherwise ...
        f = req.fdata;
        thatUser.update({"name": f.name, "role": f.role});  # TODO: Allow email update?
        if f.password:
            thatUser.update({"hpw": hashPw(f.password)});
        assert validateUser(thatUser);
        db.replaceOne(thatUser);
        return res.redirect("/_users");


    ########################################################
    # Caching Helpers: #####################################
    ########################################################

    pathCache = dotsi.fy({});
    def pathCacheful (fn):
        "Decorator for auto-caching reposne by path.";
        @functools.wraps(fn)
        def wrapper (req, res, *a, **ka):
            if devMode:
                #print("Caching disabled on accout of `devMode`.");
                return fn(req, res, *a, **ka);
            # otherwise ...
            path = req.getPathInfo();
            if path not in pathCache:
                #print("Caching ...");
                pathCache[path] = fn(req, res, *a, **ka);
            #else: print("Already cached!");
            return pathCache[path];
        return wrapper;
    
    def plugin_clearPathCacheOnPost (fn):
        "Plugin for auto-clearing cache on every POST request.";
        @functools.wraps(fn)
        def wrapper (req, res, *a, **ka):
            if req.getVerb() == "POST":
                pathCache.clear();
                #print("Cache cleared.");
            return fn(req, res, *a, **ka);
        return wrapper;
    app.install(plugin_clearPathCacheOnPost);

    ########################################################
    # Serving Content: #####################################
    ########################################################

    @app.route("GET", "/")
    @pathCacheful
    @dbful
    def get_homepage (req, res, db):
        pageList = getAllPages_exclDrafts(db);
        return autoTpl("home.html", DEFAULT_HOME, req, res, data={
            "pageList": pageList,
        });
    
    #TODO/Consider:
    #@app.route("GET", "/robots.txt")
    #def get_robotsTxt (req, res):
    #    res.contentType = "text/plain";
    #    return "";

    @app.route("GET", "/sitemap.txt")
    @pathCacheful
    @dbful
    def get_sitemapTxt (req, res, db):
        pageList = getAllPages_exclDrafts(db);
        schHost = req.splitUrl.scheme + "://" + req.splitUrl.netloc;
        # ^ Scheme w/ netloc. (Netloc includes port.)
        pageUrlList = mapli(pageList, lambda p: schHost + "/" + p.meta.slug);
        res.contentType = "text/plain";
        return "\n".join(pageUrlList);
    
    @app.route("GET", "/*")
    @pathCacheful
    @dbful
    def get_pageBySlug (req, res, db):
        slug = req.wildcards[0];
        currentPage = getPage(db, {"meta": {"slug": slug}});
        if not currentPage:
            raise vilo.error(autoTpl("404.html", DEFAULT_404, req, res));
        nextPage, prevPage = getNextAndPrevPages(db, currentPage);
        return autoTpl(
            currentPage.meta.template, DEFAULT_PAGE, req, res, data={
                "currentPage": currentPage,
                "title": currentPage.meta.title + " // " + blogTitle,
                "isPreview": False,
                "nextPage": nextPage,
                "prevPage": prevPage,
            },
        );

    @app.route("GET", "/static/**")
    def get_static (req, res):
        relPath = req.wildcards[0];
        if not themeDir:
            raise errLine("ERROR: Theme not configured.");
        # otherwise ...
        path = os.path.join(themeDir, "static/" + relPath);
        return res.staticFile(path);
    
    ########################################################
    # Handle Framework Errors: #############################
    ########################################################
        
    @app.frameworkError("route_not_found")
    @app.frameworkError("file_not_found")
    def route_not_found (req, res, err):
        path = req.getPathInfo();
        if path in redirectMap:
            return res.redirect(redirectMap[path]);
        # otherwise ...
        return autoTpl("404.html", DEFAULT_404, req, res);

    ########################################################
    # Return built `app`: ##################################
    ########################################################
    return app;

def tmp_theme0 (filename):
    pkgDir = os.path.dirname(os.path.realpath(__file__));
    print("pkgDir =", pkgDir);
    filepath = os.path.join(pkgDir, "theme0", filename);
    print("filepath =", filepath);
    print("os.path.isfile(.) =>", os.path.isfile(filepath));
    return filepath;

# End ######################################################
