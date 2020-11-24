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

import re;

import dotsi;

from . import utils;


PAGE_VERSION = 0;

def validateMeta (meta):
    assert type(meta) is dotsi.Dict;
    assert meta.title and type(meta.title) is str;
    assert meta.slug and type(meta.slug) is str;
    assert re.match(r"^[a-zA-Z0-9][a-zA-Z0-9_-]+$", meta.slug);
    assert meta.isoDate and type(meta.isoDate) is str;
    assert re.match(r"^\d\d\d\d-\d\d-\d\d$", meta.isoDate);
    assert meta.template and type(meta.template) is str;
    assert meta.template.endswith(".html");
    assert type(meta.isDraft) is bool;
    return True;

def validatePage (page, blogId):
    "Validates `page` schema.";
    assert type(page) in [dict, dotsi.Dict];
    page = dotsi.fy(page);
    assert page._id and type(page._id) is str;
    assert type(page.blogId) is str and page.blogId == blogId;
    assert page.version == PAGE_VERSION;
    assert page.type == "page";
    assert validateMeta(page.meta);
    assert page.body and type(page.body) is str;
    assert page.authorId and type(page.authorId) is str;
    assert page.createdAt and type(page.createdAt) is int;
    return True;

def buildPage (meta, body, author, blogId):
    page = dotsi.fy({
        "_id": utils.genId(),
        "blogId": blogId,
        "version": PAGE_VERSION,
        "type": "page",
        "meta": meta,
        "body": body,
        "authorId": author._id,
        "createdAt": utils.getNow(),
    });
    assert validatePage(page, blogId);
    return page;

def insertPage (db, page, blogId):
    assert validatePage(page, blogId);
    db.insertOne(page);

def replacePage(db, page, blogId):
    assert validatePage(page, blogId);
    db.replaceOne(page);

def deletePage (db, page, blogId):
    assert validatePage(page, blogId);
    db.deleteOne(page._id);

def adaptPage (db, page):
    assert page.version == PAGE_VERSION;
    return page;

def getPage (db, subdoc, blogId, whereEtc="", argsEtc=None):
    if type(subdoc) is str:
        subdoc = {"_id": subdoc};
    subdoc.update({"type": "page", "blogId": blogId});
    page = db.findOne(subdoc, whereEtc=whereEtc, argsEtc=argsEtc);
    if not page: return None;
    return adaptPage(db, page);

def getPageBySlug (db, slug, blogId):
    subdoc = {"meta": {"slug": slug}};
    return getPage(db, subdoc, blogId);

def getLatestPage_exclDrafts (db, blogId):
    subdoc = {"meta": {"isDraft": False}};
    return getPage(db, subdoc, blogId, whereEtc="""
        ORDER BY doc->'meta'->>'isoDate' DESC
    """);

def _getNextAndPrevPages (db, page, blogId, exclDrafts=True):
    subdoc = dotsi.fy({
        "meta": {"template": page.meta.template},
    });
    if exclDrafts:
        subdoc.meta.update({"isDraft": False});
    nextPage = getPage(db, subdoc, blogId, whereEtc="""
        AND doc->'meta'->>'isoDate' > %s
        ORDER BY doc->'meta'->>'isoDate' ASC
    """, argsEtc=[page.meta.isoDate]);
    prevPage = getPage(db, subdoc, blogId, whereEtc="""
        AND doc->'meta'->>'isoDate' < %s
        ORDER BY doc->'meta'->>'isoDate' DESC
    """, argsEtc=[page.meta.isoDate]);
    return [nextPage, prevPage];

def getNextAndPrevPages_inclDrafts (db, page, blogId):
    return _getNextAndPrevPages(db, page, blogId, exclDrafts=False)

def getNextAndPrevPages_exclDrafts (db, page, blogId):
    return _getNextAndPrevPages(db, page, blogId, exclDrafts=True)
    

def getPageList (db, subdoc, blogId, whereEtc="", argsEtc=None):
    subdoc.update({"type": "page", "blogId": blogId});
    if whereEtc == "" and argsEtc is None:
        whereEtc = """
            ORDER BY doc->'meta'->>'isoDate' DESC
        """; # ^^^ default order
    pageList = db.find(subdoc, whereEtc=whereEtc, argsEtc=argsEtc);
    pageList = utils.mapli(pageList, lambda p: adaptPage(db, p));
    # Finally:
    return pageList;

def getAllPages_inclDrafts (db, blogId):
    return getPageList(db, {}, blogId);

def getAllPages_exclDrafts (db, blogId):
    return getPageList(db, {"meta": {"isDraft": False}}, blogId);

def deleteAllPages (db, blogId):
    for page in getAllPages_inclDrafts(db, blogId):
        db.deleteOne(page._id);
