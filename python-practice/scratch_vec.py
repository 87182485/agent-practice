import sqlite3, sqlite_vec
from sqlite_vec import serialize_float32 as f32

db = sqlite3.connect(":memory:")
db.enable_load_extension(True); sqlite_vec.load(db); db.enable_load_extension(False)

# Unknown 1: does vec0 support a partition key + cosine metric?
db.execute("""create virtual table v using vec0(
    user_id integer partition key,
    embedding float[2] distance_metric=cosine)""")

for rid, uid, vec in [(1, 1, [1.0, 0.0]), (2, 1, [0.0, 1.0]), (3, 2, [1.0, 0.0])]:
    db.execute("insert into v(rowid, user_id, embedding) values (?, ?, ?)", (rid, uid, f32(vec)))

knn = """select rowid, distance from v
         where embedding match ? and k = ? and user_id = ? order by distance"""
print("knn:", db.execute(knn, (f32([1.0, 0.1]), 2, 1)).fetchall())

# Unknown 2: does a plain delete remove the row from KNN results?
db.execute("delete from v where rowid = 1")
print("after delete:", db.execute(knn, (f32([1.0, 0.1]), 2, 1)).fetchall())

# Unknown 3: can a rowid be replaced in place?
try:
    db.execute("insert or replace into v(rowid, user_id, embedding) values (2, 1, ?)", (f32([1.0, 0.0]),))
    print("insert or replace: works")
except sqlite3.Error as e:
    print("insert or replace:", type(e).__name__, e)