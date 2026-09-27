"""python3 -m unittest  — curate_opendata.py + verify_selection.py on synthetic
slices with the real Open Data headers (snapshot 2026-08-27). No network."""
import csv, gzip, json, os, tempfile, unittest
import curate_opendata as co, verify_selection as vs

TABLES = {
 "taxa": ["taxon_id\tancestry\trank_level\trank\tname\tactive",
          "100\t48460/1/2\t20\tgenus\tTestus\ttrue",
          "101\t48460/1/2/100\t10\tspecies\tTestus alpha\ttrue",
          "102\t48460/1/2/100/101\t5\tsubspecies\tTestus alpha beta\ttrue",
          "103\t48460/1/2/100\t10\thybrid\tTestus alpha × gamma\ttrue",
          "104\t48460/1/2/100\t10\tspecies\tTestus gamma\ttrue",
          "105\t48460/1/2/200\t10\tspecies\tOtherus delta\ttrue",
          "106\t48460/1/2/100/101\t5\thybrid\tTestus alpha alpha × beta\ttrue"],
 "observations": ["observation_uuid\tobserver_id\tlatitude\tlongitude\tpositional_accuracy\ttaxon_id\tquality_grade\tobserved_on\tanomaly_score",
          "o1\t1\t10.0\t20.0\t5\t101\tresearch\t2024-01-01\t12.5",
          "o2\t1\t10.1\t20.1\t\t102\tresearch\t2024-01-02\t",
          "o3\t1\t10.2\t20.2\t5\t103\tresearch\t2024-01-03\t9",
          "o4\t1\t10.3\t20.3\t5\t104\tresearch\t2024-01-04\t9",
          "o5\t1\t10.4\t20.4\t5\t101\tneeds_id\t2024-01-05\t9",
          "o6\t2\t-33.0\t151.0\t50000\t101\tresearch\t2024-01-06\t9",
          "o7\t2\t45.0\t-60.0\t5\t105\tresearch\t2024-01-07\t0.2"],
 "photos": ["photo_uuid\tphoto_id\tobservation_uuid\tobserver_id\textension\tlicense\twidth\theight\tposition",
          "a1\t1\to1\t1\tjpg\tCC-BY\t2048\t1536\t0",
          "a2\t2\to1\t1\tjpeg\tCC0\t2048\t1536\t1",
          "a3\t3\to1\t1\tjpg\tCC-BY-NC\t2048\t1536\t2",
          "a4\t4\to2\t1\tjpg\tCC-BY-SA\t2048\t1536\t1",
          "a5\t5\to2\t1\tpng\tCC-BY\t2048\t1536\t0",
          "a6\t6\to3\t1\tjpg\tCC-BY\t2048\t1536\t0",
          "a7\t7\to4\t1\tjpg\tCC0\t2048\t1536\t0",
          "a8\t8\to5\t1\tjpg\tCC0\t2048\t1536\t0",
          "a9\t9\to6\t2\tjpg\tCC-BY-ND\t2048\t1536\t0",
          "b0\t10\to6\t2\tjpg\tCC0\t2048\t1536\t1",
          "b1\t11\to7\t2\tjpg\tCC0\t100\t80\t0"],
 "observers": ["observer_id\tlogin\tname", "1\talice\tAlice A", "2\tbob\t", "3\tcarol\tCarol C"],
}
SPECIES = {"Testus alpha": 101, "Otherus delta": 105}


class Curate(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        for name, lines in TABLES.items():
            with gzip.open(os.path.join(self.dir, name + ".csv.gz"), "wt") as f: f.write("\n".join(lines) + "\n")

    def run_(self, **kw):
        return co.curate(SPECIES, source=self.dir, log=lambda *_: None, **kw)

    def ids(self, rows, sp="Testus alpha"):
        return [r["photo_id"] for r in rows if r["species"] == sp]

    def test_descendants_drop_hybrids_and_siblings(self):
        d = co.descendants([101, 105], self.dir, None)
        self.assertEqual({k: v[0] for k, v in d.items()}, {b"101": 101, b"102": 101, b"105": 105})

    def test_licence_research_grade_and_order(self):
        # NC (3), ND (9), BY-SA (4) out; needs_id (8), hybrid (6), sibling (7) out.
        # Order: every position-0 photo (by photo_uuid) before position 1.
        self.assertEqual(self.ids(self.run_()), ["1", "5", "2", "10"])
        self.assertEqual(self.ids(self.run_(by_sa=True)), ["1", "5", "2", "4", "10"])

    def test_caps(self):
        self.assertEqual(self.ids(self.run_(per_obs=1)), ["1", "5", "10"])
        self.assertEqual(self.ids(self.run_(per_observer=1)), ["1", "10"])
        self.assertEqual(self.ids(self.run_(want=2)), ["1", "5"])

    def test_photo_on_two_observations_listed_once(self):
        TABLES["photos"].append("c1\t1\to6\t2\tjpg\tCC-BY\t2048\t1536\t0")
        try:
            self.setUp()
            self.assertEqual(self.ids(self.run_()).count("1"), 1)
        finally:
            TABLES["photos"].pop()

    def test_size_floor(self):
        self.assertEqual(self.ids(self.run_(), "Otherus delta"), ["11"])
        self.assertEqual(self.ids(self.run_(min_px=500), "Otherus delta"), [])

    def test_join_and_columns(self):
        rows = {r["photo_id"]: r for r in self.run_()}
        r = rows["5"]
        self.assertEqual(r["url"], "https://inaturalist-open-data.s3.amazonaws.com/photos/5/medium.png")
        self.assertEqual((r["author"], r["author_login"], r["taxon_id"], r["target_taxon_id"]),
                         ("Alice A", "alice", "102", 101))
        self.assertEqual(r["attribution"], "© Alice A, some rights reserved (CC-BY)")
        self.assertEqual((r["license"], r["license_code"]), ("CC-BY 4.0", "cc-by"))
        self.assertEqual(rows["10"]["attribution"], "bob, no rights reserved (CC0)")  # blank name -> login
        self.assertEqual(r["observation_uuid"], "o2")
        self.assertRegex(r["snapshot_date"], r"^\d{4}-\d\d-\d\d$")
        self.assertEqual(list(r), co.COLUMNS)

    def test_truncated_table_raises(self):
        path = os.path.join(self.dir, "taxa.csv.gz")
        raw = gzip.compress(("\n".join(TABLES["taxa"]) + "\n").encode() * 2000)
        open(path, "wb").write(raw[:len(raw) // 2])
        with self.assertRaises((RuntimeError, EOFError)):
            list(co.rows("taxa", self.dir)[1])

    def test_coords_filter(self):
        path = os.path.join(self.dir, "c.tsv")
        self.run_(coords=path)
        got = [(r["species"], r["latitude"]) for r in csv.DictReader(open(path), delimiter="\t")]
        # o6 dropped (accuracy 50 km), o7 dropped (anomaly 0.2 < 1), o2 kept (no score)
        self.assertEqual(got, [("Testus alpha", "10.0"), ("Testus alpha", "10.1")])


def obs(uuid, oid, photos, taxon=(101, "Testus alpha", "species"), anc=(100,), qg="research", **extra):
    return dict({"uuid": uuid, "id": oid, "quality_grade": qg,
                 "taxon": {"id": taxon[0], "name": taxon[1], "rank": taxon[2], "ancestor_ids": list(anc)},
                 "photos": [{"id": p, "license_code": l} for p, l in photos],
                 "user": {"login": "alice", "name": "Alice Renamed"}, "identifications": []}, **extra)


class Verify(unittest.TestCase):
    def test_verify(self):
        live = [obs("u1", 11, [(1, "cc-by")]),
                obs("u2", 12, [(2, "cc-by-nc")]),                                    # relicensed
                obs("u3", 13, [(3, "cc0")], comments=[{"body": "Could be a HYBRID?"}]),
                obs("u5", 15, [(5, "cc0")], taxon=(104, "Testus gamma", "species")),  # ID moved
                obs("u6", 16, [(66, "cc0")]),                                        # photo gone
                obs("u7", 17, [(7, "cc-by-sa")]),
                obs("u8", 18, [(8, "cc0")], identifications=[{"taxon": {"name": "Testus alpha × gamma"}}]),
                obs("u9", 19, [(9, "cc0")], qg="needs_id")]
        calls = []
        vs.fetch_json = lambda url: calls.append(url) or {"results": live}
        base = dict.fromkeys(co.COLUMNS, "")
        rows = [dict(base, photo_id=str(p), observation_uuid=f"u{p}", target_taxon_id="101", species="Testus alpha",
                     author_login="alice") for p in (1, 2, 3, 4, 5, 6, 7, 8, 9)]
        kept, drops = vs.verify(rows, pause=0, now="2026-09-27T00:00:00Z")
        self.assertEqual(len(calls), 1)
        self.assertIn("uuid=u1,u2,u3", calls[0])
        self.assertEqual({d["photo_id"]: d["reason"] for d in drops},
                         {"2": "licence now cc-by-nc", "3": "hybrid mention", "4": "observation gone",
                          "5": "taxon moved", "6": "photo removed", "7": "licence now cc-by-sa",
                          "8": "hybrid mention", "9": "not research grade"})
        (k,) = kept
        self.assertEqual((k["source_page"], k["author"], k["license_checked_utc"]),
                         ("https://www.inaturalist.org/observations/11", "Alice Renamed", "2026-09-27T00:00:00Z"))
        kept, _ = vs.verify(rows, by_sa=True, pause=0)
        self.assertEqual(sorted(k["photo_id"] for k in kept), ["1", "7"])
        self.assertEqual(kept[1]["attribution"], "© Alice Renamed, some rights reserved (CC-BY-SA)")

    def test_batches_of_200(self):
        calls = []
        vs.fetch_json = lambda url: calls.append(url) or {"results": []}
        vs.verify([{"observation_uuid": f"u{i}", "target_taxon_id": "1", "photo_id": "1", "species": "x"}
                   for i in range(401)], pause=0)
        self.assertEqual([c.count(",") + 1 for c in calls], [200, 200, 1])



class ObserverCapTests(unittest.TestCase):
    """Supply-scaled photographer cap (Rick 2026-09-27: more supply, tighter cap)."""
    def test_cap_tightens_with_supply(self):
        from curate_opendata import observer_cap
        self.assertEqual(observer_cap(80, 60), 15)    # thin: 25% of 60
        self.assertEqual(observer_cap(200, 60), 12)   # 20%
        self.assertEqual(observer_cap(2000, 60), 6)   # deep: 10%
        self.assertEqual(observer_cap(5, 0), 2)       # never below 2

    def _cand(self, per_user):
        c = []
        for u, n in per_user.items():
            for k in range(n):
                pid = f"{u}-{k}"
                c.append(({"photo_id": pid, "observation_uuid": pid}, {"observer_id": u}))
        return c

    def test_relaxes_only_to_reach_30(self):
        from curate_opendata import select_capped
        # one dominant photographer (40) + 3 small ones (3 each): 49 photos
        cand = self._cand({"a": 40, "b": 3, "c": 3, "d": 3})
        kept, _, users, cap, relaxed = select_capped(cand, want=60)
        self.assertTrue(relaxed)
        self.assertEqual(len(kept), 30)
        self.assertEqual(users["a"], 21)

    def test_deep_supply_is_not_relaxed(self):
        from curate_opendata import select_capped
        cand = self._cand({f"u{i}": 20 for i in range(40)})   # 800 photos, 40 people
        kept, _, users, cap, relaxed = select_capped(cand, want=60)
        self.assertFalse(relaxed)
        self.assertEqual(cap, 6)
        self.assertEqual(len(kept), 60)
        self.assertLessEqual(max(users.values()), 6)

    def test_explicit_zero_means_no_cap(self):
        from curate_opendata import select_capped
        kept, _, users, cap, relaxed = select_capped(self._cand({"a": 50}), want=40, per_observer=0)
        self.assertEqual(len(kept), 40); self.assertEqual(cap, 0)

if __name__ == "__main__":
    unittest.main()
