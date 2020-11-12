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

__version__ = "0.0.4";  # Req'd by flit.
USER_VERSION = 0;
PAGE_VERSION = 0;

PKG_DIR = os.path.dirname(os.path.realpath(__file__));
DEFAULT_ADMIN_THEME_DIR = os.path.join(PKG_DIR, "default-admin-theme");
DEFAULT_PUBLIC_THEME_DIR = os.path.join(PKG_DIR, "default-public-theme");

genId = lambda n=1: "".join(map(lambda i: uuid.uuid4().hex, range(n)));
getNow = lambda: int(time.time());  # Seconds since epoch.
mapli = lambda seq, fn: list(map(fn, seq));
filterli = lambda seq, fn: list(filter(fn, seq));
_b = lambda s, e="utf8": s.encode(e) if type(s) is str else s;
_s = lambda b, e="utf8": b.decode(e) if type(b) is bytes else b;
hashPw = lambda p: _s(bcrypt.hashpw(_b(p), bcrypt.gensalt()));
checkPw = lambda p, h: bcrypt.checkpw(_b(p), _b(h));

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
# Theme Validators: ########################################
############################################################

def validateThemeDir (themeDir, reqdFilenameList):
    if not os.path.isdir(themeDir):
        raise ValueError("No such directory: %s" % themeDir);
    sep = os.path.sep; # Separator like '/'.
    themeName = themeDir.strip(sep).split(sep)[-1];
    themeSlash = lambda x: os.path.join(themeDir, x);
    for filename in reqdFilenameList:
        if not os.path.isfile(themeSlash(filename)):
            raise ValueError(
                "Theme `%s` doesn't include file: %s" % (themeName, filename)
            );
    if not os.path.isdir(themeSlash("static")):
        raise ValueError("Theme `%s` doesn't include directory: static/" % themeName);
    return True;


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
        adminThemeDir = DEFAULT_ADMIN_THEME_DIR,
        publicThemeDir = DEFAULT_PUBLIC_THEME_DIR,
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
    
    validateThemeDir(adminThemeDir, [
        "setup.html", "login.html", "reset.html",
        "page-lister.html", "page-editor.html",
        "user-lister.html", "user-editor.html",
    ]);
    validateThemeDir(publicThemeDir, [
        "home.html", "page.html", "404.html",
    ]);

    def oneLine (sentence, seq=()):
        "Helper for producing one-line HTML responses.";
        if seq is not ():
            sentence = vilo.escfmt(sentence, seq);
        spPaths = re.findall(r"\s/_\w+", sentence);
        # ^ Pattern: <space> <slash> <underscore> <onePlusWordChars>
        for spPath in spPaths:
            path = spPath.strip();
            link = "<a href='%s'><code>%s</code></a>" % (path, path);
            sentence = sentence.replace(path, link, 1);
        #return sentence;
        return ("""<!doctype html>
            <html>
            <head>
                <meta name="viewport" content="width=device-width, initial-scale=1">
                <title>%s</title>
                <style>
                    body {
                        max-width: 720px;
                        margin: auto;
                        font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
                        font-size: 16px;
                    }
                    a { text-decoration: none; }
                </style>
            </head>
            <body>
                <br><br>%s<br><br>
                <a href='javascript:history.back();'>&lt; Back</a>
            </body>
            </html>
        """ % (vilo.esc(blogTitle), sentence));

    def errLine (sentence, seq=()):
        "Helper for producing one-line error responses.";
        return vilo.error(oneLine(sentence, seq));
    
    def mkRenderTpl (baseThemeDir, defaultData):
        def renderTpl (filename, data=None):
            data = dotsi.defaults(dotsi.fy({}),
                data or {}, defaultData, {"renderTpl": renderTpl},
            );
            path = os.path.join(baseThemeDir, filename);
            try:
                return qree.renderPath(path, data);
            except IOError as e:
                # Note: Error may be caused by a nested tpl.
                print("\n" + traceback.format_exc() + "\n");
                raise errLine("ERROR: Template %s not found.",
                    e.filename,
                );    
        return renderTpl;
    
    adminTpl = mkRenderTpl(adminThemeDir, {
        "blogTitle": blogTitle,
        "blogDescription": blogDescription,
        #"title": blogTitle,
        "footerLine": footerLine,
    });
    publicTpl = mkRenderTpl(publicThemeDir, {
        "blogTitle": blogTitle,
        "blogDescription": blogDescription,
        "footerLine": footerLine,    
    });

    ########################################################
    # Authentication Helpers: ##############################
    ########################################################

    def startLoginSession (user, res):
        res.setCookie("userId", user._id, cookieSecret);
        xCsrfToken = vilo.signWrap(user._id, antiCsrfSecret);
        res.setUnsignedCookie("xCsrfToken", xCsrfToken, {"httponly": False});
        return res.redirect("/_pages");

    def endLoginSession (res):
        res.setCookie("userId", "");
        res.setCookie("xCsrfToken", "");
        #return res.redirect("/_login");
        return oneLine("Done! You've logged out. Visit /_login to log back in.");

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

    
    @app.route("GET", "/_setup")
    @dbful
    def get_setup (req, res, db):
        anyUser = db.findOne({"type": "user"});
        if anyUser:
            raise errLine("Setup previously completed. Visit: /_login");
        return adminTpl("setup.html");

    @app.route("POST", "/_setup")
    @dbful
    def post_setup (req, res, db):
        anyUser = db.findOne({"type": "user"});
        if anyUser:
            raise errLine("Setup previously completed. Visit: /_login");
        d = req.fdata;
        user = buildUser(d.name, d.email, d.password, role="admin");
        db.insertOne(user);
        #return res.redirect("/_login");
        return startLoginSession(user, res);
    
    @app.route("GET", "/_reset")
    @authful
    def get_reset (req, res, user, db):
        assert user.role == "admin";
        return adminTpl("reset.html", {
            "title": "ViloLog ~ Reset . . . Please be careful!"
        });

    @app.route("POST", "/_resetFull")
    @authful
    def get_reset (req, res, user, db):
        assert user.role == "admin";
        db.clearTable(sure=True);
        return res.redirect("/_setup");

    @app.route("POST", "/_resetPages")
    @authful
    def get_reset (req, res, user, db):
        assert user.role == "admin";
        pageList = getAllPages_inclDrafts(db);
        for page in pageList:
            db.deleteOne(page._id);
        return res.redirect("/_pages");

    ########################################################
    # Login/logout: ########################################
    ########################################################

    @app.route("GET", "/_login")
    def get_login (req, res):
        return adminTpl("login.html");

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

    @app.route("GET", "/_logout")
    def get_logout (req, res):
        return endLoginSession(res);

    ########################################################
    # Page Management: #####################################
    ########################################################
    
    @app.route("GET", "/_pages")
    @authful
    def get_pages (req, res, db, user):
        pageList = getAllPages_inclDrafts(db);
        return adminTpl("page-lister.html", data={
            "pageList": pageList,
            "title": "ViloLog ~ All Pages",
        });

    @app.route("GET", "/_newPage")
    @authful
    def get_newPage (req, res, db, user):
        assert user.role in ["author", "admin"];
        return adminTpl("page-editor.html", {
            "title": "ViloLog ~ Page Composer",
        });

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
        return adminTpl("page-editor.html", data={
            "page": page,
            "title": "ViloLog ~ Page Composer",
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
        return publicTpl(currentPage.meta.template, data={
                "currentPage": currentPage,
                "title": currentPage.meta.title + " // " + blogTitle,
                "isPreview": True,
                "nextPage": nextPage,
                "prevPage": prevPage,
                "req": req, "res": res,
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
        return adminTpl("user-lister.html", data={
            "userList": userList,
            "title": "ViloLog ~ All Users",
        });

    @app.route("GET", "/_newUser")
    @authful
    def get_newUser (req, res, db, user):
        currentUser = user;
        del user;
        if currentUser.role != "admin":
            raise errLine("Access denied. Only admins can add users.");
        # otherwise ...
        return adminTpl("user-editor.html", data={
            "title": "ViloLog ~ Add User",
        });

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
        return adminTpl("user-editor.html", data={
            "thatUser": thatUser,
            "title": "ViloLog ~ Update User",
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
        return publicTpl("home.html", data={
            "pageList": pageList,
            "req": req, "res": res,
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
            raise vilo.error(publicTpl("404.html", data={
                "req": req, "res": res,
            }));
        nextPage, prevPage = getNextAndPrevPages(db, currentPage);
        return publicTpl(currentPage.meta.template, data={
                "currentPage": currentPage,
                "title": currentPage.meta.title + " // " + blogTitle,
                "isPreview": False,
                "nextPage": nextPage,
                "prevPage": prevPage,
                "req": req, "res": res,
            },
        );

    @app.route("GET", "/_admin_static/**")
    def get_admin_static (req, res):
        return res.staticFile(os.path.join(
            adminThemeDir, "static", req.wildcards[0],
        ));
    
    @app.route("GET", "/_public_static/**")
    def get_admin_static (req, res):
        return res.staticFile(os.path.join(
            publicThemeDir, "static", req.wildcards[0],
        ));
    
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
        return publicTpl("404.html", data={"req": req, "res": res});

    ########################################################
    # Return built `app`: ##################################
    ########################################################
    return app;

# End ######################################################
