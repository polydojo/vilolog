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

USER_VERSION = 0;

def validateUser (user, blogId):
    assert type(user) in [dict, dotsi.Dict];
    user = dotsi.fy(user);
    assert user._id and type(user._id) is str;
    assert type(user.blogId) is str and user.blogId == blogId;
    assert user.version == USER_VERSION;
    assert user.type == "user";
    assert user.name and type(user.name) is str;
    assert user.email and type(user.email) is str;
    assert re.match(r"^\S+@\S+\.\S+$", user.email);
    assert user.hpw and type(user.hpw) is str;
    assert user.createdAt and type(user.createdAt) is int;
    assert user.role in ["admin", "author", "deactivated"];
    return True;

def buildUser (name, email, password, role, blogId):
    user = dotsi.fy({
        "_id": utils.genId(),
        "blogId": blogId,
        "version": USER_VERSION,
        "type": "user",
        "name": name,
        "email": email,
        "hpw": utils.hashPw(password),
        "createdAt": utils.getNow(),
        "role": role,
        #TODO: "bio": "bio",
    });
    assert validateUser(user, blogId);
    return user;

def insertUser (db, user, blogId):
    assert validateUser(user, blogId);
    db.insertOne(user);

def replaceUser(db, user, blogId):
    assert validateUser(user, blogId);
    db.replaceOne(user);

#def deleteUser (db, user, blogId):     -- Unused.
#    assert validateUser(user, blogId);
#    db.deleteOne(user._id);

def adaptUser (db, user):
    assert user.version == USER_VERSION;
    return user;

def getUser (db, subdoc, blogId):
    if type(subdoc) is str:
        subdoc = {"_id": subdoc};
    subdoc.update({"type": "user", "blogId": blogId});
    user = db.findOne(subdoc);
    if not user: return None;
    return adaptUser(db, user);

def getAnyUser (db, blogId):
    return getUser(db, {}, blogId);

def getUserByEmail (db, email, blogId):
    return getUser(db, {"email": email}, blogId);

def getUserList (db, subdoc, blogId):
    subdoc.update({"type": "user", "blogId": blogId});
    userList = db.find(subdoc);
    return utils.mapli(userList, lambda user: adaptUser(db, user));

def getAllUsers (db, blogId):
    return getUserList(db, {}, blogId);

def deleteAllUsers (db, blogId):
    for user in getAllUsers(db, blogId):
        db.deleteOne(user._id);
