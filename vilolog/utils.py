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

import uuid;
import time;

import bcrypt;

genId = lambda n=1: "".join(map(lambda i: uuid.uuid4().hex, range(n)));
getNow = lambda: int(time.time());  # Seconds since epoch.
mapli = lambda seq, fn: list(map(fn, seq));
filterli = lambda seq, fn: list(filter(fn, seq));
_b = lambda s, e="utf8": s.encode(e) if type(s) is str else s;
_s = lambda b, e="utf8": b.decode(e) if type(b) is bytes else b;
hashPw = lambda p: _s(bcrypt.hashpw(_b(p), bcrypt.gensalt()));
checkPw = lambda p, h: bcrypt.checkpw(_b(p), _b(h));
