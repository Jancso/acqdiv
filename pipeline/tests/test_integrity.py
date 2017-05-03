""" Tests for ACQDIV dev and production databases. """

import unittest
import re
import csv
import configparser

from dateutil.parser import parse

import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker


_pattern_speaker_label = re.compile('^[a-zA-Z]{2,}\d*$')
_pattern_speaker_names = re.compile('\d')
_pattern_speaker_ages = re.compile('^(\d\d?(;([0-9]|1[01]).([12]?[0-9]|30))?)$')


class ValidationTest(object):
    """ Base class for shared tests between ACQDIV dev(elopment) and production database. """
    @classmethod
    def setUpClass(cls):
        """ Setup test fixtures. """
        # Load database.
        engine = sa.create_engine(cls.database_path)
        cls.meta = sa.MetaData(engine, reflect=True) # Reflects database metadata.
        Session = sessionmaker(bind=engine)
        cls.session = Session()

        # Load gold database counts.
        cls.cfg = configparser.ConfigParser()
        cls.cfg.read(cls.config) # TODO: how to close the config file this way?

        # Load list of tables from csv file and check for coverage proportion.
        cls.f_proportions = open("fixtures/tables-proportions-filled.csv", "r")
        cls.reader_proportion_nulls = csv.reader(cls.f_proportions)
        next(cls.reader_proportion_nulls)  # Skip the header

        # Load list of tables from csv file and check that the specified table and their columns contain no NULL.
        cls.f_no_nulls = open("fixtures/tables-no-nulls-allowed.csv", "r")
        cls.reader_tables_no_nulls = csv.reader(cls.f_no_nulls)
        next(cls.reader_tables_no_nulls)  # Skip the header

    @classmethod
    def tearDownClass(cls):
        """ Tear down the test fixtures. """
        cls.session.close()
        cls.f_proportions.close()
        cls.f_no_nulls.close()

    def test_columns_for_proportion_null(self):
        """ Check proportion of nulls per table per corpus. """
        # TODO: @rabart notesd that each corpus might need its own proportion tweaking. If that's the case, then we should change the CSV fixture file to handle corpus and proportion and these loops in this method to handle the tables (say viw SQLAlchemy meta reflection).
        corpora = ["Chintang", "Cree", "Indonesian", "Inuktitut", "Japanese_Miyata", "Japanese_MiiPro", "Russian", "Sesotho", "Turkish", "Yucatec"]

        for row in self.reader_proportion_nulls:
            table = row[0]
            column = row[1]
            proportion = float(row[2])

            for corpus in corpora:
                # Skip corpus-specific irregularities.
                if column == "pos_raw" and corpus == "Indonesian":
                    continue
                if column == "gender_raw" and corpus in ["Japanese_Miyata", "Sesotho", "Yucatec"]:
                    continue
                if column == "translation" and corpus in ["Japanese_Miyata","Japanese_MiiPro", "Russian", "Turkish"]:
                    continue

                query = "select count(*) from %s where %s is not NULL and corpus = '%s'" % (table, column, corpus)
                res = self.session.execute(query)
                result = res.fetchone()[0]

                self.assertGreater(result, proportion, msg='Proportion (%s) less than proportion of NULLs in query (%s)' % (res, query))

    """ The tests! """
    def test(self):
        # This is an example test function and should always pass.
        pass

    def test_columns_for_all_null(self):
        """ Any column with all NULL rows should throw an error. """
        for table in self.meta.tables.values():
            for column in table.c:
                self._column_contains_all_nulls(table, column)

    def test_columns_for_any_null(self):
        """ User specified columns should never have a NULL row. """
        for row in self.reader_tables_no_nulls:
            table = row[0]
            column = row[1]
            self._column_contains_null(table, column)

    def test_counts(self):
        """ Use the fixture database gold counts and check the dev or production database. """
        for section in self.cfg:
            if section == "default":
                continue
            for option in self.cfg[section]:
                count = int(self.cfg[section][option])
                res = self.session.execute("select count(*) from %s where corpus = '%s'" % (option, section))
                actual = res.fetchone()[0]
                self.assertEqual(actual, count, msg='%s %s: expected %s, got %s' % (section, option, count, actual))

    def test_sentence_type(self):
        """ Check sentence types in database vs whitelist. """
        query = "select sentence_type from utterances group by sentence_type"
        sentence_types = [None, "default", "question", "exclamation", "imperative", "trail off",
                          "interruption", "trail off question", "self interruption", "self interruption question",
                          "quotation next line", "quotation precedes", "interruption question"]
        self._in_whitelist(query, sentence_types)

    def test_gender(self):
        """ Check genders in database vs whitelist. """
        query = "select gender from speakers group by gender"
        gender = ["Female", "Male", "Unspecified", "None"]
        self._in_whitelist(query, gender)

    def test_pos(self):
        """ Check pos in database vs whitelist. """
        query = "select pos from morphemes group by pos"
        pos = [None, "ADJ", "ADV", "ART", "AUX", "CLF", "CONJ", "IDEOPH", "INTJ", "N", "NUM", "pfx", "POST",
               "PREP", "PRODEM", "PTCL", "QUANT", "sfx", "stem", "V", "???"]
        self._in_whitelist(query, pos)

    def test_role(self):
        """ Check roles in database vs whitelist. """
        query = "select role from speakers group by role"
        roles = ["Adult", "Aunt", "Babysitter", "Brother", "Caller", "Caretaker", "Child", "Cousin", "Daughter",
                 "Family_Friend", "Father", "Friend", "Grandfather", "Grandmother", "Great-Grandmother", "Host",
                 "Housekeeper", "Mother", "Neighbour", "Niece", "Playmate", "Research_Team", "Sibling", "Sister",
                 "Sister-in-law", "Son", "Speaker", "Student", "Subject", "Target_Child", "Teacher", "Toy",
                 "Twin_Brother", "Uncle", "Visitor", "None", "Unknown"]
        self._in_whitelist(query, roles)

    def test_macrorole(self):
        """ Check macroles in database vs whitelist and not whitelist. """
        query = "select macrorole from speakers group by macrorole"
        macroroles = ["Adult", "Child", "Target_Child", "Unknown"]
        self._in_whitelist(query, macroroles)

        # TODO: Robert do we really need this?
        # not_macroroles = ["Unspecified", "None", "Unidentified", "Unidentified_child", "Unidentified_adult"]
        #_not_in_blacklist(session, query, not_macroroles)

    def test_speaker_labels(self):
        """ Check whether the speaker labels are kosher orthographically. """
        query = "select speaker_label from speakers group by speaker_label"
        self._in_string(query, _pattern_speaker_label)

    def test_speaker_names(self):
        # should be able to check it in various db columns
        query = "select name from speakers group by name"
        self._not_in_string(query, _pattern_speaker_names)

    def test_speaker_ages(self):
        # should be able to check it in various db columns
        query = "select age from speakers group by age"
        self._in_string(query, _pattern_speaker_ages)

    def test_date_sessions(self):
        """ Check date in sessions.date """
        query = "select date from sessions group by date"
        self._is_valid_date(query)

    def test_date_speakers(self):
        """ Check birthdates in speakers.birthdate """
        query = "select birthdate from speakers group by birthdate"
        self._is_valid_date(query)

    def test_date_uniquespeakers(self):
        """ Check birthdates in uniquespeakers.birthdate """
        query = "select birthdate from uniquespeakers group by birthdate"
        self._is_valid_date(query)

    def test_language_per_morpheme(self):
        """ Check whether the language mapping is working as intended """
<<<<<<< HEAD
        query = "select morpheme_language from morphemes group by morpheme_language"
        langs = ["Chintang", "Nepali", "English", "Bantawa", "Chintang/Nepali",
                 "Nepali/English", "Chintang/Nepali/English", "Bantawa",
                 "Chintang/Bantawa", "Chintang (Mulgaũ)", "Chintang (Sambugaũ)",
                 "Chintang+Nepali", "Hindi", "Nepali/Arabic", "Nepali/Hindi",
                 "Japanese", "German", "Turkish", "Sesotho", "Yucatec", "Cree",
                 "Inuktitut", "Indonesian", "Russian", "Unknown"]
=======
        query = "select language from morphemes group by language"
        langs = ["Chintang", "Nepali", "English", "Bantawa", "Chintang/Nepali",
                 "Nepali/English", "Chintang/Nepali/English", "Bantawa",
                 "Chintang/Belhare", "Japanese", "German", "Turkish",
                 "Sesotho", "Yucatec", "Cree", "Inuktitut", "Indonesian",
                 "Russian", "Unknown"]
>>>>>>> 11d0f29fe8e018aed13b419fe38a62cd4d3d63e6
        self._in_whitelist(query, langs)


    """ Private methods below. """
    def _column_contains_null(self, table, column):
        """ Test if any row in column is NULL. """
        query = "select count(*) from %s where %s is NULL" % (table, column)
        res = self.session.execute(query)
        result = res.fetchone()[0]
        self.assertEqual(result, 0, msg='%s %s' % (res, query))

    def _column_contains_all_nulls(self, table, column):
        """ Test if rows in a column are all NULL. """
        # TODO: never do this query apparently: https://docs.python.org/2/library/sqlite3.html
        query = "select count(*) from %s where %s is not NULL" % (table, column)
        res = self.session.execute(query)
        result = res.fetchone()[0]
        self.assertGreater(result, 0, msg='%s %s' % (res, query))
        # msg='select corpus, count(*) from table where column is not NULL group by corpus'

    def _is_valid_date(self, query):
        """ Check whether an input string is database NULL, Unspecified or adheres to dateutils format. """
        res = self.session.execute(query)
        rows = res.fetchall()
        for row in rows:
            value = row[0]
            is_valid = False
            if value is None or value == "Unspecified" or self._is_date(value):
                is_valid = True
            self.assertTrue(is_valid, msg='The date value %s is not NULL in the database, is not "Unspecified", and it does not confirm to dateutils.parser in the query (%s).' % (value, query))

    def _is_date(self, string):
        """ Check for valid dateutils.parser format. """
        try:
            parse(string)
            return True
        except ValueError:
            return False

    def _is_match(self, string, pattern):
        """ Check if regex valid against string. """
        try:
            if pattern.search(string) is None:
                return False
            else:
                return True
        except ValueError: # TODO: this fails when the input doesn't conform to the regex, e.g. ints
            self.assertRaises(ValueError, msg='%s is not a valid data type for regex %s.' % (str(type(string), str(pattern))))

    def _validate_string(self, query, pattern, is_string):
        """ This function validates whether unique strings in a column confirm to some regular expression. """
        res = self.session.execute(query)
        rows = res.fetchall()
        for row in rows:
            value = row[0]
            if value is not None:
                is_valid = self._is_match(value, pattern)
                if is_string:
                    self.assertTrue(is_valid, msg='%s %s (%s)' % (value, is_valid, query))
                else:
                    self.assertFalse(is_valid, msg='%s -- %s -- (%s)' % (value, is_valid, query))

    def _in_string(self, query, pattern):
        """ Check whether the input string is valid given a regex pattern. """
        return self._validate_string(query, pattern, is_string=True)

    def _not_in_string(self, query, pattern):
        return self._validate_string(query, pattern, is_string=False)

    def _in_whitelist(self, query, filter_list):
        self._check_filter_list(query, filter_list, is_whitelist=True)

    def _not_in_blacklist(self, query, filter_list):
        self._check_filter_list(query, filter_list, is_whitelist=False)

    def _check_filter_list(self, query, filter_list, is_whitelist):
        """ Given a SQL query that returns a unique list of elements, e.g. select column from table group by column, check that the result types are in the whitelist (or not)."""
        res = self.session.execute(query)
        rows = res.fetchall()
        for row in rows:
            label = row[0]
            if is_whitelist:  # This is whitelist.
                self.assertIn(label, filter_list, msg='%s returned by (%s).' % (label, query))
            else:             # This is a blacklist.
                self.assertNotIn(label, filter_list, msg='value found in (%s) is not permitted')


class ValidationTest_DevDB(unittest.TestCase, ValidationTest):
    """ Subclass of ValidatioTest for testing the development database. """
    @classmethod
    def setUpClass(cls):
        ValidationTest.database_path = "sqlite:///../database/test.sqlite3"
        ValidationTest.config = "fixtures/dev_counts.ini"
        ValidationTest.setUpClass()


class ValidationTest_ProductionDB(unittest.TestCase, ValidationTest):
    """ Subclass of ValidatioTest for testing the production database. """
    @classmethod
    def setUpClass(cls):
        ValidationTest.database_path = "sqlite:///../database/acqdiv.sqlite3"
        ValidationTest.config = "fixtures/production_counts.ini"
        ValidationTest.setUpClass()


if __name__ == '__main__':
    unittest.main()
