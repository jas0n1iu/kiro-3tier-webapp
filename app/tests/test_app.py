import datetime as dt
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import report  # noqa: E402
import server  # noqa: E402

TODAY = dt.date(2026, 11, 13)


def payload(**kw):
    p = {"product": "TV", "fault": "显示故障", "purchase_date": "2025-06-01",
         "symptom": "屏幕闪烁（测试数据）", "urgency": "高"}
    p.update(kw)
    return p


class AddMonths(unittest.TestCase):
    def test_clamps_month_end(self):
        self.assertEqual(report.add_months(dt.date(2024, 1, 31), 1), dt.date(2024, 2, 29))
        self.assertEqual(report.add_months(dt.date(2023, 8, 31), 6), dt.date(2024, 2, 29))

    def test_year_rollover(self):
        self.assertEqual(report.add_months(dt.date(2025, 12, 15), 24), dt.date(2027, 12, 15))


class Warranty(unittest.TestCase):
    def test_in_and_out(self):
        w = report.warranty("TV", "显示故障", dt.date(2025, 6, 1), TODAY)
        self.assertEqual(w["status"], "保修期内")
        w = report.warranty("智能手机", "显示故障", dt.date(2025, 6, 1), TODAY)  # 12 months -> ended 2026-06-01
        self.assertEqual(w["status"], "保修期外")

    def test_boundary_last_day_is_in_warranty(self):
        end = report.add_months(dt.date(2024, 11, 13), 24)  # 2026-11-13 == TODAY
        self.assertEqual(end, TODAY)
        self.assertEqual(report.warranty("TV", "电源故障", dt.date(2024, 11, 13), TODAY)["status"], "保修期内")
        self.assertEqual(report.warranty("TV", "电源故障", dt.date(2024, 11, 12), TODAY)["status"], "保修期外")

    def test_physical_damage_note(self):
        w = report.warranty("TV", "物理损坏", dt.date(2025, 6, 1), TODAY)
        self.assertIn("不在免费保修范围", w["note"])


class Validation(unittest.TestCase):
    def check(self, **kw):
        with self.assertRaises(report.ValidationError):
            report.parse_input(payload(**kw), TODAY)

    def test_ok(self):
        c = report.parse_input(payload(), TODAY)
        self.assertEqual(c["purchase_date"], dt.date(2025, 6, 1))

    def test_bad_values(self):
        self.check(product="微波炉")
        self.check(fault="其他")
        self.check(urgency="紧急")
        self.check(purchase_date="2026-11-14")      # future
        self.check(purchase_date="1999-12-31")      # too old
        self.check(purchase_date="2025/06/01")
        self.check(purchase_date=None)
        self.check(symptom="   ")
        self.check(symptom="x" * 501)
        self.check(symptom=123)

    def test_not_a_dict(self):
        with self.assertRaises(report.ValidationError):
            report.parse_input([], TODAY)


class Report(unittest.TestCase):
    def test_all_combinations_have_steps(self):
        for p in report.PRODUCTS:
            for f in report.FAULTS:
                self.assertEqual(len(report.REPAIR_STEPS[p][f]), 3, (p, f))

    def test_out_of_warranty_adds_quote_step(self):
        c = report.parse_input(payload(product="智能手机"), TODAY)
        r = report.build_report(c, TODAY, "AS-X")
        self.assertTrue(any("报价" in s for s in r["steps"]))
        self.assertIn("保修状态：保修期外", r["report_text"])

    def test_priority_by_urgency(self):
        for u, lvl in (("高", "P1"), ("中", "P2"), ("低", "P3")):
            r = report.build_report(report.parse_input(payload(urgency=u), TODAY), TODAY, "AS-X")
            self.assertTrue(r["priority"]["level"].startswith(lvl))

    def test_ticket_number(self):
        self.assertEqual(report.ticket_number(TODAY, 42), "AS20261113-00042")
        self.assertEqual(report.ticket_number(TODAY), "AS20261113-DRAFT")


class CreateReport(unittest.TestCase):
    def test_saved_flag_and_ticket(self):
        r = server.create_report(payload(), TODAY, saver=lambda c, s: 7)
        self.assertTrue(r["saved"])
        self.assertEqual(r["ticket_no"], "AS20261113-00007")

    def test_works_without_db(self):
        r = server.create_report(payload(), TODAY, saver=lambda c, s: None)
        self.assertFalse(r["saved"])
        self.assertIn("DRAFT", r["ticket_no"])
        self.assertIn("A/S 受理报告（草稿）", r["report_text"])

    def test_symptom_kept_verbatim(self):
        evil = "<script>alert(1)</script>'; DROP TABLE as_request;--"
        r = server.create_report(payload(symptom=evil), TODAY, saver=lambda c, s: None)
        self.assertIn(evil, r["report_text"])  # escaping is the client's job (textContent); SQL is parameterized


if __name__ == "__main__":
    unittest.main()
