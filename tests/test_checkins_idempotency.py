import os
import tempfile
import threading
import unittest
from datetime import datetime, timedelta

from services import local_db
from services import itinerary


class TestCheckinsIdempotency(unittest.TestCase):
    def test_concurrent_checkin_is_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            db_path = os.path.join(td, "local.db")
            user_id = "u1"
            spot_id = "s1"

            local_db.init_db(db_path)

            barrier = threading.Barrier(10)
            results = []
            lock = threading.Lock()

            def worker():
                barrier.wait()
                ok = local_db.insert_checkin(db_path, user_id, spot_id)
                with lock:
                    results.append(ok)

            threads = [threading.Thread(target=worker) for _ in range(10)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            self.assertEqual(local_db.count_checkins(db_path, user_id, spot_id), 1)
            self.assertEqual(sum(1 for r in results if r), 1)


class TestItineraryOptions(unittest.TestCase):
    def test_round_to_hour(self):
        dt = datetime(2026, 4, 19, 10, 20, 5)
        self.assertEqual(itinerary.round_to_hour(dt), datetime(2026, 4, 19, 11, 0, 0))
        dt2 = datetime(2026, 4, 19, 10, 0, 0)
        self.assertEqual(itinerary.round_to_hour(dt2), dt2)

    def test_validate_time_range(self):
        now = datetime(2026, 4, 19, 10, 0, 0)
        errs = itinerary.validate_time_range(now, now - timedelta(hours=1), now + timedelta(hours=2))
        self.assertTrue(any(e["code"] == "E_START_IN_PAST" for e in errs))
        errs2 = itinerary.validate_time_range(now, now + timedelta(hours=1), now + timedelta(hours=1))
        self.assertTrue(any(e["code"] == "E_END_BEFORE_START" for e in errs2))
        errs3 = itinerary.validate_time_range(now, now + timedelta(hours=1), now + timedelta(hours=1, minutes=30))
        self.assertTrue(any(e["code"] == "E_RANGE_TOO_SHORT" for e in errs3))

    def test_replan_increments_version_and_checksum(self):
        now = datetime(2026, 4, 19, 10, 0, 0)
        base_plan = {"city": "杭州", "route": "大铭", "itinerary_version": 0}
        stops = [{"name": "A", "visit_duration": "60分钟"}, {"name": "B", "visit_duration": "60分钟"}]
        start = now + timedelta(hours=1)
        end = start + timedelta(days=1)
        r1 = itinerary.replan_itinerary(
            base_plan=base_plan,
            stops=stops,
            now=now,
            start_dt=start,
            end_dt=end,
            budget_amount=None,
            budget_currency="CNY",
            extra_options={},
            prev_preview=None,
        )
        self.assertEqual(r1.preview["version"], 1)
        self.assertTrue(isinstance(r1.preview.get("checksum"), str) and len(r1.preview.get("checksum")) > 10)
        base_plan["itinerary_version"] = r1.preview["version"]
        r2 = itinerary.replan_itinerary(
            base_plan=base_plan,
            stops=stops,
            now=now,
            start_dt=start,
            end_dt=end,
            budget_amount=None,
            budget_currency="CNY",
            extra_options={},
            prev_preview=r1.preview,
        )
        self.assertEqual(r2.preview["version"], 2)
        self.assertNotEqual(r1.preview["checksum"], r2.preview["checksum"])


if __name__ == "__main__":
    unittest.main()
