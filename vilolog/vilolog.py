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

from . import utils;
from . import pageModel;
from . import userModel;

__version__ = "0.0.6";  # Req'd by flit.

PKG_DIR = os.path.dirname(os.path.realpath(__file__));
DEFAULT_ADMIN_THEME_DIR = os.path.join(PKG_DIR, "default-admin-theme");
DEFAULT_BLOG_THEME_DIR = os.path.join(PKG_DIR, "default-blog-theme");

############################################################
# Theme Helpers, ETC.: #####################################
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

def mkRenderTpl (baseThemeDir, defaultData):
    "Returns a function that render from `baseThemeDir`.";
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
            <title>ViloLog</title>
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
            <a href="/">Home</a> &nbsp; | &nbsp;
            <a href='javascript:history.back();'>Back</a>
        </body>
        </html>
    """ % sentence);

def errLine (sentence, seq=()):
    "Helper for producing one-line error responses.";
    return vilo.error(oneLine(sentence, seq));

############################################################
# Quick Plugins: ###########################################
############################################################


def checkLocalhost (netloc):
    "Helper for checking if `netloc` is localhost.";
    return netloc.split(":")[0] == "localhost";

def plugin_enforceRemoteHttps (fn):
    "Plugin for enforcing https.";
    @functools.wraps(fn)
    def wrapper (req, res, *a, **ka):
        #print("Entered plugin_enforceRemoteHttps().");
        scheme = req.splitUrl.scheme;
        netloc = req.splitUrl.netloc;
        if checkLocalhost(netloc):
            pass;       # No enforcement w.r.t localhost.
        elif scheme != "https":
            secureUrl = req.url.replace(scheme, "https", 1);
            #print("Early exiting plugin_enforceRemoteHttps().");
            return res.redirect(secureUrl);
        # otherwise ...
        #print("Properly exiting plugin_enforceRemoteHttps().");
        return fn(req, res, *a, **ka);
    return wrapper;

def mkPlugin_enforceRemoteNetloc (netlocList):
    "Makes a plugin for enforcing netlocs in `netlocList`.";
    assert len(netlocList) >= 1 and type(netlocList[0]) is str;
    def plugin_enforceRemoteNetloc (fn):
        @functools.wraps(fn)
        def wrapper (req, res, *a, **ka):
            #print("Entered plugin_enforceRemoteNetloc().");
            netloc = req.splitUrl.netloc;
            if checkLocalhost(netloc):
                pass;   # No enforcement w.r.t localhost.
            elif netloc not in netlocList:
                newUrl = req.url.replace(netloc, netlocList[0], 1);
                #print("Early exiting plugin_enforceRemoteNetloc().");
                return res.redirect(newUrl);
            # otherwise ...
            #print("Properly exiting plugin_enforceRemoteNetloc().");
            return fn(req, res, *a, **ka);
        return wrapper;
    return plugin_enforceRemoteNetloc;

def mkPlugin_disableRemoteLogin (blogTpl):
    "Makes plugin for disable remote (non-localhost) login.";
    # Helper:
    def checkAccessOk (netloc, path):
        if checkLocalhost(netloc):
            return True;    # On localhost, always allowed.
        if path.startswith("/_blog_static/"):
            return True;    # Special path, always allowed.
        if not path.startswith("/_"):
            return True;    # Non-admin path, always allowed.
        # otherwise ...
        return False;
    # Plugin:
    def plugin_disableRemoteLogin (fn):
        @functools.wraps(fn)
        def wrapper (req, res, *a, **ka):
            #print("Entered plugin_disableRemoteLogin().");
            netloc = req.splitUrl.netloc;
            path = req.getPathInfo();
            if not checkAccessOk(netloc, path):
                #print("Early exiting plugin_disableRemoteLogin().");
                raise vilo.error(blogTpl("404.html",
                    data={"req": req, "res": res},
                ));
            #print("Properly exiting plugin_disableRemoteLogin().");
            return fn(req, res, *a, **ka);
        return wrapper;
    return plugin_disableRemoteLogin;

############################################################
# Build: ###################################################
############################################################

def buildApp (
        pgUrl, # 1st positional param
        blogId = "",
        blogTitle = "My ViloLog Blog",
        blogDescription = "Yet another ViloLog blog.",
        footerLine = "Powered by ViloLog.",
        cookieSecret = "",
        antiCsrfSecret = "",
        blogThemeDir = DEFAULT_BLOG_THEME_DIR,
        _adminThemeDir = DEFAULT_ADMIN_THEME_DIR,
        devMode = False,
        redirectMap = None,
        loginSlug = "_login",
        disableRemoteLogin = False,
        remoteNetlocList = None,
        remoteHttpsOnly = False,
    ):
    ########################################################
    # Prelims: #############################################
    ########################################################
    # Param defaults:
    redirectMap = redirectMap or {};
    remoteNetlocList = remoteNetlocList or [];
    if devMode:
        cookieSecret = cookieSecret or "dev_cookie_secret";
        antiCsrfSecret = antiCsrfSecret or "dev_xCsrf_secret";
    else:
        cookieSecret = cookieSecret or utils.genId(3);
        antiCsrfSecret = antiCsrfSecret or utils.genId(3);
    
    # Validate params, etc:
    validateThemeDir(_adminThemeDir, [
        "setup.html", "login.html", "reset.html",
        "page-lister.html", "page-editor.html",
        "user-lister.html", "user-editor.html",
    ]);
    validateThemeDir(blogThemeDir, [
        "home.html", "page.html", "404.html",
    ]);
    if not re.match(r"^_login\w*$", loginSlug):
        raise ValueError(r"Invalid `loginSlug`, doesn't match: r'_login\w*'");
    loginPath = "/" + loginSlug;
    
    # Build app, db-connector:
    app = vilo.buildApp();
    dbful = pogodb.makeConnector(pgUrl, verbose=False);
    if devMode: app.setDebug(True);
    
    # Renderers:
    adminTpl = mkRenderTpl(_adminThemeDir, {
        "blogTitle": blogTitle,
        "blogDescription": blogDescription,
        "footerLine": footerLine,
    });
    blogTpl = mkRenderTpl(blogThemeDir, {
        "blogTitle": blogTitle,
        "blogDescription": blogDescription,
        "footerLine": footerLine,    
    });

    # Install plugins:
    if remoteHttpsOnly:
        app.install(plugin_enforceRemoteHttps);
    if remoteNetlocList:
        app.install(mkPlugin_enforceRemoteNetloc(remoteNetlocList));
    if disableRemoteLogin:
        app.install(mkPlugin_disableRemoteLogin(blogTpl));

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
        return oneLine("Done! You've logged out.");

    def getCurrentUser (db, req):
        errMsg = "Session expired. Please /_logout and then log back in.";
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
        user = userModel.getUser(db, userId, blogId);
        #print("user =", user);
        if not user:
            raise errLine(errMsg);
        if user.role == "deactivated":
            raise errLine("Access deactivated.");
        return user;

    def authful (fn):
        @dbful
        def wrapper(req, res, db, *a, **ka):
            user = getCurrentUser(db, req);
            return fn(req, res, db=db, user=user, *a, **ka);
        return functools.update_wrapper(wrapper, fn);
    
    def validatePageEditDelRole (user, page):
        assert user.role != "deactivated";
        if user.role == "admin":
            return True;
        if user.role == "author" and user._id == page.authorId:
            return True;
        raise errLine("""Access denied.
            Only admins and page-authors can edit/delete pages.
        """);
    
    ########################################################
    # Setup: ###############################################
    ########################################################
    
    @app.route("GET", "/_setup")
    @dbful
    def get_setup (req, res, db):
        anyUser = userModel.getAnyUser(db, blogId);
        if anyUser:
            raise errLine("Setup previously completed. Please log in.");
        return adminTpl("setup.html");

    @app.route("POST", "/_setup")
    @dbful
    def post_setup (req, res, db):
        anyUser = userModel.getAnyUser(db, blogId);
        if anyUser:
            raise errLine("Setup previously completed. Please log in.");
        # otherwise ...
        f = req.fdata;
        user = userModel.buildUser(
            f.name, f.email, f.password, "admin", blogId,
        );
        userModel.insertUser(db, user, blogId);
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
        pageModel.deleteAllPages(db, blogId);
        userModel.deleteAllUsers(db, blogId);
        return res.redirect("/_setup");

    @app.route("POST", "/_resetPages")
    @authful
    def get_reset (req, res, user, db):
        assert user.role == "admin";
        pageModel.deleteAllPages(db, blogId);
        return res.redirect("/_pages");

    ########################################################
    # Login/logout: ########################################
    ########################################################

    @app.route("GET", loginPath)
    def get_login (req, res):
        return adminTpl("login.html");

    @app.route("POST", loginPath)
    @dbful
    def post_login (req, res, db):
        f = req.fdata;
        user = userModel.getUserByEmail(db, f.email, blogId);
        if not (user and utils.checkPw(f.password, user.hpw)):
            raise errLine("Invalid email and/or password.");
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
        pageList = pageModel.getAllPages_inclDrafts(db, blogId);
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
        #print("meta = ", meta);
        sameSlugPage = pageModel.getPageBySlug(db, meta.slug, blogId);
        #print("sameSlugPage = ", sameSlugPage);
        if sameSlugPage:
            raise errLine("Slug already taken. Try another?");
        #pprint.pprint(req.fdata);
        page = pageModel.buildPage(
            meta, req.fdata.body, user, blogId
        );
        #pprint.pprint(page);
        pageModel.insertPage(db, page, blogId);
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
        page = pageModel.getPage(db, pageId, blogId);
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
        page = pageModel.getPage(db, pageId, blogId);
        if not page: raise errLine("No such page.");
        oldSlug = page.meta.slug;
        assert validatePageEditDelRole(user, page);
        meta = dotsi.fy(json.loads(req.fdata.meta));
        newSlug = meta.slug;
        if oldSlug != newSlug:
            sameSlugPage = pageModel.getPageBySlug(db, newSlug, blogId);
            if sameSlugPage:
                raise errLine("Slug already taken. Try another?");
        page.update({"meta": meta, "body": req.fdata.body});
        pageModel.replacePage(db, page, blogId);
        return oneLine(vilo.escfmt("""Done!
            <a href='/%s'>View page,</a>
            <a href=''>re-edit it</a>,
            or proceed to: /_pages""", meta.slug,
        ));
    
    # GET => Preview saved page, launched from page-lister.
    # POST => Live-preview unsaved edits, launched from page-editor.
    @app.route("GET", "/_previewPage/*")
    @app.route("POST", "/_previewPage/")
    @app.route("POST", "/_previewPage/*")
    @authful
    def getOrPost_previewPage (req, res, db, user):
        verb = req.getVerb();
        pageId = req.wildcards[0] if req.wildcards else None;
        if verb == "POST":
            f = req.fdata;
            meta = dotsi.fy(json.loads(f.meta));
            currentPage = (
                pageModel.getPage(db, pageId, blogId) if pageId else
                pageModel.buildPage(meta, req.fdata.body, user, blogId)
            );
            currentPage.update({"meta": meta, "body": req.fdata.body});
        else:
            currentPage = pageModel.getPage(db, pageId, blogId);
        # Eitherway ...
        assert currentPage;
        nextPage, prevPage = pageModel.getNextAndPrevPages(
            db, currentPage, blogId,
        );
        return blogTpl(currentPage.meta.template, data={
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
        page = pageModel.getPage(db, pageId, blogId);
        if not page: raise errLine("No such page.");
        assert validatePageEditDelRole(user, page);
        pageModel.deletePage(db, page, blogId);
        return res.redirect("/_pages");

    ########################################################
    # User Management: #####################################
    ########################################################

    @app.route("GET", "/_users")
    @authful
    def get_users (req, res, db, user):
        userList = userModel.getAllUsers(db, blogId)
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
        f = req.fdata;
        existingUser = userModel.getUserByEmail(db, f.email, blogId);
        if existingUser:
            raise errLine("Error: Email address already registered.");
        # otherwise ...
        newUser = userModel.buildUser(
            f.name, f.email, f.password, f.role, blogId,
        );
        userModel.insertUser(db, newUser, blogId);
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
        thatUser = userModel.getUser(db, thatUserId, blogId);
        if not thatUser:
            raise errLine("No such user. See: /_users");
        # otherwise ...
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
        thatUser = userModel.getUser(db, thatUserId, blogId);
        if not thatUser:
            raise errLine("No such user. See: /_users");
        # otherwise ...
        f = req.fdata;
        thatUser.update({"name": f.name, "role": f.role});
        # TODO: _Consider_ allowing email update?
        if f.password:
            thatUser.update({"hpw": utils.hashPw(f.password)});
        userModel.replaceUser(db, thatUser, blogId);
        return res.redirect("/_users");

    ########################################################
    # Serving Content: #####################################
    ########################################################

    @app.route("GET", "/")
    @dbful
    def get_homepage (req, res, db):
        pageList = pageModel.getAllPages_exclDrafts(db, blogId);
        return blogTpl("home.html", data={
            "pageList": pageList,
            "req": req, "res": res,
        });
    
    #TODO/Consider:
    #@app.route("GET", "/robots.txt")
    #def get_robotsTxt (req, res):
    #    res.contentType = "text/plain";
    #    return "";

    @app.route("GET", "/sitemap.txt")
    @dbful
    def get_sitemapTxt (req, res, db):
        pageList = pageModel.getAllPages_exclDrafts(db, blogId);
        schHost = req.splitUrl.scheme + "://" + req.splitUrl.netloc;
        # ^ Scheme w/ netloc. (Netloc includes port.)
        pageUrlList = utils.mapli(pageList,
            lambda p: schHost + "/" + p.meta.slug
        );
        res.contentType = "text/plain";
        rootUrl = schHost + "/";
        return "\n".join([rootUrl] + pageUrlList);
    
    @app.route("GET", "/*")
    @dbful
    def get_pageBySlug (req, res, db):
        slug = req.wildcards[0];
        currentPage = pageModel.getPageBySlug(db, slug, blogId);
        if (not currentPage) or (currentPage.meta.isDraft):
            raise vilo.error(blogTpl("404.html", data={
                "req": req, "res": res,
            }));
        nextPage, prevPage = pageModel.getNextAndPrevPages(
            db, currentPage, blogId,
        );
        return blogTpl(currentPage.meta.template, data={
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
            _adminThemeDir, "static", req.wildcards[0],
        ));
    
    @app.route("GET", "/_blog_static/**")
    def get_admin_static (req, res):
        return res.staticFile(os.path.join(
            blogThemeDir, "static", req.wildcards[0],
        ));
    
    ########################################################
    # Handle Framework Errors: #############################
    ########################################################
        
    @app.frameworkError("route_not_found")
    @app.frameworkError("file_not_found")
    def route_not_found (req, res, err):
        path = req.getPathInfo();
        if redirectMap and path in redirectMap:
            return res.redirect(redirectMap[path]);
        # otherwise ...
        return blogTpl("404.html", data={"req": req, "res": res});

    ########################################################
    # Return built `app`: ##################################
    ########################################################
    return app;

# End ######################################################
