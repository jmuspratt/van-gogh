"""python3 -m unittest discover pipeline"""

import unittest

from dates import DateParseError, parse_date


class ParseDateTest(unittest.TestCase):
    def check(self, text, earliest, latest, approximate=False, probable=False):
        d = parse_date(text)
        self.assertEqual((d.earliest, d.latest), (earliest, latest), text)
        self.assertEqual((d.approximate, d.probable), (approximate, probable), text)
        self.assertEqual(d.weekday_mismatches, [], text)

    def test_exact_day(self):
        self.check("Sunday, 29 September 1872", "1872-09-29", "1872-09-29")

    def test_on_or_about(self):
        self.check("on or about Friday, 2 March 1888", "1888-03-02", "1888-03-02", approximate=True)

    def test_alternatives_borrow_month_and_year(self):
        self.check("Tuesday, 21 or Wednesday, 22 August 1888", "1888-08-21", "1888-08-22")

    def test_between_months(self):
        self.check("between Monday, 4 January and Friday, 5 March 1875", "1875-01-04", "1875-03-05")

    def test_across_new_year(self):
        self.check("Tuesday, 31 December 1889 or Wednesday, 1 January 1890", "1889-12-31", "1890-01-01")

    def test_month_parts(self):
        self.check("mid-January 1873", "1873-01-11", "1873-01-20")
        self.check("between mid August and early September 1884", "1884-08-11", "1884-09-10")
        self.check("end of December 1880 - beginning of January 1881", "1880-12-21", "1881-01-10")
        self.check("second half of 1881", "1881-07-01", "1881-12-31")

    def test_probably_year_range(self):
        self.check("probably between 1875-1878", "1875-01-01", "1878-12-31", probable=True)

    def test_open_ended(self):
        self.check("after Sunday, 21 April 1889", "1889-04-22", None)

    def test_leading_place_and_typos(self):
        self.check("The Hague, on or about Thursday, 18 January 1883", "1883-01-18", "1883-01-18", approximate=True)
        self.check("on or about Sunday, 17June 1888", "1888-06-17", "1888-06-17", approximate=True)

    def test_weekday_mismatch_is_reported(self):
        self.assertEqual(parse_date("Monday, 29 September 1872").weekday_mismatches, [("1872-09-29", "Monday")])

    def test_garbage_is_rejected(self):
        with self.assertRaises(DateParseError):
            parse_date("sometime in spring")


if __name__ == "__main__":
    unittest.main()
