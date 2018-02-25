import pytest
import os
from warnings import catch_warnings
from distutils.version import LooseVersion
import tempfile
import datetime

import tables
import numpy as np
import pandas as pd
from pandas import (Series, DataFrame, date_range, Index, Timestamp,
                    DatetimeIndex, compat, concat, isna)
from pandas.tests.io.pytables.common import (ensure_clean_store, safe_close,
                                             _check_roundtrip, safe_remove,
                                             _check_roundtrip_table,
                                             create_tempfile, _maybe_remove,
                                             ensure_clean_path)

import pandas.util.testing as tm
import pandas.util._test_decorators as td
from pandas.util.testing import (assert_panel_equal,
                                 assert_frame_equal,
                                 assert_series_equal)

from pandas.compat import range, lrange, u
from pandas.io.formats.printing import pprint_thing
from pandas.io.pytables import (HDFStore, get_store,
                                read_hdf, PossibleDataLossError)


def test_factory_fun():
    path = create_tempfile()
    try:
        with catch_warnings(record=True):
            with get_store(path) as tbl:
                raise ValueError('blah')
    except ValueError:
        pass
    finally:
        safe_remove(path)

    try:
        with catch_warnings(record=True):
            with get_store(path) as tbl:
                tbl['a'] = tm.makeDataFrame()

        with catch_warnings(record=True):
            with get_store(path) as tbl:
                assert len(tbl) == 1
                assert type(tbl['a']) == DataFrame
    finally:
        safe_remove(path)


def test_context():
    path = create_tempfile()
    try:
        with HDFStore(path) as tbl:
            raise ValueError('blah')
    except ValueError:
        pass
    finally:
        safe_remove(path)

    try:
        with HDFStore(path) as tbl:
            tbl['a'] = tm.makeDataFrame()

        with HDFStore(path) as tbl:
            assert len(tbl) == 1
            assert type(tbl['a']) == DataFrame
    finally:
        safe_remove(path)


def test_conv_read_write():
    path = create_tempfile()
    try:
        def roundtrip(key, obj, **kwargs):
            obj.to_hdf(path, key, **kwargs)
            return read_hdf(path, key)

        o = tm.makeTimeSeries()
        assert_series_equal(o, roundtrip('series', o))

        o = tm.makeStringSeries()
        assert_series_equal(o, roundtrip('string_series', o))

        o = tm.makeDataFrame()
        assert_frame_equal(o, roundtrip('frame', o))

        with catch_warnings(record=True):
            o = tm.makePanel()
            assert_panel_equal(o, roundtrip('panel', o))

        # table
        df = DataFrame(dict(A=lrange(5), B=lrange(5)))
        df.to_hdf(path, 'table', append=True)
        result = read_hdf(path, 'table', where=['index>2'])
        assert_frame_equal(df[df.index > 2], result)

    finally:
        safe_remove(path)


def test_long_strings():
    # GH6166
    # unconversion of long strings was being chopped in earlier
    # versions of numpy < 1.7.2
    df = DataFrame({'a': tm.rands_array(100, size=10)},
                   index=tm.rands_array(100, size=10))

    with ensure_clean_store() as store:
        store.append('df', df, data_columns=['a'])
        result = store.select('df')
        assert_frame_equal(df, result)


def test_api():
    # GH4584
    # API issue when to_hdf doesn't acdept append AND format args
    with ensure_clean_path() as path:
        df = tm.makeDataFrame()
        df.iloc[:10].to_hdf(path, 'df', append=True, format='table')
        df.iloc[10:].to_hdf(path, 'df', append=True, format='table')
        assert_frame_equal(read_hdf(path, 'df'), df)

        # append to False
        df.iloc[:10].to_hdf(path, 'df', append=False, format='table')
        df.iloc[10:].to_hdf(path, 'df', append=True, format='table')
        assert_frame_equal(read_hdf(path, 'df'), df)

    with ensure_clean_path() as path:
        df = tm.makeDataFrame()
        df.iloc[:10].to_hdf(path, 'df', append=True)
        df.iloc[10:].to_hdf(path, 'df', append=True, format='table')
        assert_frame_equal(read_hdf(path, 'df'), df)

        # append to False
        df.iloc[:10].to_hdf(path, 'df', append=False, format='table')
        df.iloc[10:].to_hdf(path, 'df', append=True)
        assert_frame_equal(read_hdf(path, 'df'), df)

    with ensure_clean_path() as path:
        df = tm.makeDataFrame()
        df.to_hdf(path, 'df', append=False, format='fixed')
        assert_frame_equal(read_hdf(path, 'df'), df)

        df.to_hdf(path, 'df', append=False, format='f')
        assert_frame_equal(read_hdf(path, 'df'), df)

        df.to_hdf(path, 'df', append=False)
        assert_frame_equal(read_hdf(path, 'df'), df)

        df.to_hdf(path, 'df')
        assert_frame_equal(read_hdf(path, 'df'), df)

    with ensure_clean_store() as store:
        path = store._path
        df = tm.makeDataFrame()

        _maybe_remove(store, 'df')
        store.append('df', df.iloc[:10], append=True, format='table')
        store.append('df', df.iloc[10:], append=True, format='table')
        assert_frame_equal(store.select('df'), df)

        # append to False
        _maybe_remove(store, 'df')
        store.append('df', df.iloc[:10], append=False, format='table')
        store.append('df', df.iloc[10:], append=True, format='table')
        assert_frame_equal(store.select('df'), df)

        # formats
        _maybe_remove(store, 'df')
        store.append('df', df.iloc[:10], append=False, format='table')
        store.append('df', df.iloc[10:], append=True, format='table')
        assert_frame_equal(store.select('df'), df)

        _maybe_remove(store, 'df')
        store.append('df', df.iloc[:10], append=False, format='table')
        store.append('df', df.iloc[10:], append=True, format=None)
        assert_frame_equal(store.select('df'), df)

    with ensure_clean_path() as path:
        # invalid
        df = tm.makeDataFrame()
        pytest.raises(ValueError, df.to_hdf, path,
                      'df', append=True, format='f')
        pytest.raises(ValueError, df.to_hdf, path,
                      'df', append=True, format='fixed')

        pytest.raises(TypeError, df.to_hdf, path,
                      'df', append=True, format='foo')
        pytest.raises(TypeError, df.to_hdf, path,
                      'df', append=False, format='bar')

    # File path doesn't exist
    path = ""
    pytest.raises(compat.FileNotFoundError,
                  read_hdf, path, 'df')


def test_api_default_format():
    # default_format option
    with ensure_clean_store() as store:
        df = tm.makeDataFrame()

        pd.set_option('io.hdf.default_format', 'fixed')
        _maybe_remove(store, 'df')
        store.put('df', df)
        assert not store.get_storer('df').is_table
        pytest.raises(ValueError, store.append, 'df2', df)

        pd.set_option('io.hdf.default_format', 'table')
        _maybe_remove(store, 'df')
        store.put('df', df)
        assert store.get_storer('df').is_table
        _maybe_remove(store, 'df2')
        store.append('df2', df)
        assert store.get_storer('df').is_table

        pd.set_option('io.hdf.default_format', None)

    with ensure_clean_path() as path:
        df = tm.makeDataFrame()

        pd.set_option('io.hdf.default_format', 'fixed')
        df.to_hdf(path, 'df')
        with HDFStore(path) as store:
            assert not store.get_storer('df').is_table
        pytest.raises(ValueError, df.to_hdf, path, 'df2', append=True)

        pd.set_option('io.hdf.default_format', 'table')
        df.to_hdf(path, 'df3')
        with HDFStore(path) as store:
            assert store.get_storer('df3').is_table
        df.to_hdf(path, 'df4', append=True)
        with HDFStore(path) as store:
            assert store.get_storer('df4').is_table

        pd.set_option('io.hdf.default_format', None)


def test_keys():
    with ensure_clean_store() as store:
        store['a'] = tm.makeTimeSeries()
        store['b'] = tm.makeStringSeries()
        store['c'] = tm.makeDataFrame()
        with catch_warnings(record=True):
            store['d'] = tm.makePanel()
            store['foo/bar'] = tm.makePanel()
        assert len(store) == 5
        expected = set(['/a', '/b', '/c', '/d', '/foo/bar'])
        assert set(store.keys()) == expected
        assert set(store) == expected


def test_iter_empty():

    with ensure_clean_store() as store:
        # GH 12221
        assert list(store) == []


def test_repr():
    with ensure_clean_store() as store:
        repr(store)
        store.info()
        store['a'] = tm.makeTimeSeries()
        store['b'] = tm.makeStringSeries()
        store['c'] = tm.makeDataFrame()

        with catch_warnings(record=True):
            store['d'] = tm.makePanel()
            store['foo/bar'] = tm.makePanel()
            store.append('e', tm.makePanel())

        df = tm.makeDataFrame()
        df['obj1'] = 'foo'
        df['obj2'] = 'bar'
        df['bool1'] = df['A'] > 0
        df['bool2'] = df['B'] > 0
        df['bool3'] = True
        df['int1'] = 1
        df['int2'] = 2
        df['timestamp1'] = Timestamp('20010102')
        df['timestamp2'] = Timestamp('20010103')
        df['datetime1'] = datetime.datetime(2001, 1, 2, 0, 0)
        df['datetime2'] = datetime.datetime(2001, 1, 3, 0, 0)
        df.loc[3:6, ['obj1']] = np.nan
        df = df._consolidate()._convert(datetime=True)

        # PerformanceWarning
        with catch_warnings(record=True):
            store['df'] = df

        # make a random group in hdf space
        store._handle.create_group(store._handle.root, 'bah')

        assert store.filename in repr(store)
        assert store.filename in str(store)
        store.info()

    # storers
    with ensure_clean_store() as store:
        df = tm.makeDataFrame()
        store.append('df', df)

        s = store.get_storer('df')
        repr(s)
        str(s)


def test_contains():
    with ensure_clean_store() as store:
        store['a'] = tm.makeTimeSeries()
        store['b'] = tm.makeDataFrame()
        store['foo/bar'] = tm.makeDataFrame()
        assert 'a' in store
        assert 'b' in store
        assert 'c' not in store
        assert 'foo/bar' in store
        assert '/foo/bar' in store
        assert '/foo/b' not in store
        assert 'bar' not in store

        # gh-2694: tables.NaturalNameWarning
        with catch_warnings(record=True):
            store['node())'] = tm.makeDataFrame()
        assert 'node())' in store


def test_versioning():
    with ensure_clean_store() as store:
        store['a'] = tm.makeTimeSeries()
        store['b'] = tm.makeDataFrame()
        df = tm.makeTimeDataFrame()
        _maybe_remove(store, 'df1')
        store.append('df1', df[:10])
        store.append('df1', df[10:])
        assert store.root.a._v_attrs.pandas_version == '0.15.2'
        assert store.root.b._v_attrs.pandas_version == '0.15.2'
        assert store.root.df1._v_attrs.pandas_version == '0.15.2'

        # write a file and wipe its versioning
        _maybe_remove(store, 'df2')
        store.append('df2', df)

        # this is an error because its table_type is appendable, but no
        # version info
        store.get_node('df2')._v_attrs.pandas_version = None
        pytest.raises(Exception, store.select, 'df2')


def test_mode():
    df = tm.makeTimeDataFrame()

    def check(mode):
        with ensure_clean_path() as path:
            # constructor
            if mode in ['r', 'r+']:
                pytest.raises(IOError, HDFStore, path, mode=mode)

            else:
                store = HDFStore(path, mode=mode)
                assert store._handle.mode == mode
                store.close()

        with ensure_clean_path() as path:
            # context
            if mode in ['r', 'r+']:
                def f():
                    with HDFStore(path, mode=mode) as store:  # noqa
                        pass
                pytest.raises(IOError, f)
            else:
                with HDFStore(path, mode=mode) as store:
                    assert store._handle.mode == mode

        with ensure_clean_path() as path:
            # conv write
            if mode in ['r', 'r+']:
                pytest.raises(IOError, df.to_hdf,
                              path, 'df', mode=mode)
                df.to_hdf(path, 'df', mode='w')
            else:
                df.to_hdf(path, 'df', mode=mode)

            # conv read
            if mode in ['w']:
                pytest.raises(ValueError, read_hdf,
                              path, 'df', mode=mode)
            else:
                result = read_hdf(path, 'df', mode=mode)
                assert_frame_equal(result, df)

    def check_default_mode():
        # read_hdf uses default mode
        with ensure_clean_path() as path:
            df.to_hdf(path, 'df', mode='w')
            result = read_hdf(path, 'df')
            assert_frame_equal(result, df)

    check('r')
    check('r+')
    check('a')
    check('w')
    check_default_mode()


def test_reopen_handle():
    with ensure_clean_path() as path:
        store = HDFStore(path, mode='a')
        store['a'] = tm.makeTimeSeries()

        # invalid mode change
        pytest.raises(PossibleDataLossError, store.open, 'w')
        store.close()
        assert not store.is_open

        # truncation ok here
        store.open('w')
        assert store.is_open
        assert len(store) == 0
        store.close()
        assert not store.is_open

        store = HDFStore(path, mode='a')
        store['a'] = tm.makeTimeSeries()

        # reopen as read
        store.open('r')
        assert store.is_open
        assert len(store) == 1
        assert store._mode == 'r'
        store.close()
        assert not store.is_open

        # reopen as append
        store.open('a')
        assert store.is_open
        assert len(store) == 1
        assert store._mode == 'a'
        store.close()
        assert not store.is_open

        # reopen as append (again)
        store.open('a')
        assert store.is_open
        assert len(store) == 1
        assert store._mode == 'a'
        store.close()
        assert not store.is_open


def test_open_args():
    with ensure_clean_path() as path:
        df = tm.makeDataFrame()

        # create an in memory store
        store = HDFStore(path, mode='a', driver='H5FD_CORE',
                         driver_core_backing_store=0)
        store['df'] = df
        store.append('df2', df)

        tm.assert_frame_equal(store['df'], df)
        tm.assert_frame_equal(store['df2'], df)

        store.close()

        # the file should not have actually been written
        assert not os.path.exists(path)


def test_flush():
    with ensure_clean_store() as store:
        store['a'] = tm.makeTimeSeries()
        store.flush()
        store.flush(fsync=True)


def test_get():
    with ensure_clean_store() as store:
        store['a'] = tm.makeTimeSeries()
        left = store.get('a')
        right = store['a']
        tm.assert_series_equal(left, right)

        left = store.get('/a')
        right = store['/a']
        tm.assert_series_equal(left, right)

        pytest.raises(KeyError, store.get, 'b')


def test_getattr():
    with ensure_clean_store() as store:
        s = tm.makeTimeSeries()
        store['a'] = s

        # test attribute access
        result = store.a
        tm.assert_series_equal(result, s)
        result = getattr(store, 'a')
        tm.assert_series_equal(result, s)

        df = tm.makeTimeDataFrame()
        store['df'] = df
        result = store.df
        tm.assert_frame_equal(result, df)

        # errors
        pytest.raises(AttributeError, getattr, store, 'd')

        for x in ['mode', 'path', 'handle', 'complib']:
            pytest.raises(AttributeError, getattr, store, x)

        # not stores
        for x in ['mode', 'path', 'handle', 'complib']:
            getattr(store, "_%s" % x)


def test_to_hdf_with_min_itemsize():
    with ensure_clean_path() as path:
        # min_itemsize in index with to_hdf (GH 10381)
        df = tm.makeMixedDataFrame().set_index('C')
        df.to_hdf(path, 'ss3', format='table', min_itemsize={'index': 6})
        # just make sure there is a longer string:
        df2 = df.copy().reset_index().assign(C='longer').set_index('C')
        df2.to_hdf(path, 'ss3', append=True, format='table')
        tm.assert_frame_equal(pd.read_hdf(path, 'ss3'),
                              pd.concat([df, df2]))

        # same as above, with a Series
        df['B'].to_hdf(path, 'ss4', format='table',
                       min_itemsize={'index': 6})
        df2['B'].to_hdf(path, 'ss4', append=True, format='table')
        tm.assert_series_equal(pd.read_hdf(path, 'ss4'),
                               pd.concat([df['B'], df2['B']]))


def test_pass_spec_to_storer():
    df = tm.makeDataFrame()
    with ensure_clean_store() as store:
        store.put('df', df)
        pytest.raises(TypeError, store.select, 'df', columns=['A'])
        pytest.raises(TypeError, store.select,
                      'df', where=[('columns=A')])


def test_table_values_dtypes_roundtrip():
    with ensure_clean_store() as store:
        df1 = DataFrame({'a': [1, 2, 3]}, dtype='f8')
        store.append('df_f8', df1)
        assert_series_equal(df1.dtypes, store['df_f8'].dtypes)

        df2 = DataFrame({'a': [1, 2, 3]}, dtype='i8')
        store.append('df_i8', df2)
        assert_series_equal(df2.dtypes, store['df_i8'].dtypes)

        # incompatible dtype
        pytest.raises(ValueError, store.append, 'df_i8', df1)

        # check creation/storage/retrieval of float32 (a bit hacky to
        # actually create them thought)
        df1 = DataFrame(
            np.array([[1], [2], [3]], dtype='f4'), columns=['A'])
        store.append('df_f4', df1)
        assert_series_equal(df1.dtypes, store['df_f4'].dtypes)
        assert df1.dtypes[0] == 'float32'

        # check with mixed dtypes
        df1 = DataFrame(dict((c, Series(np.random.randn(5), dtype=c))
                             for c in ['float32', 'float64', 'int32',
                                       'int64', 'int16', 'int8']))
        df1['string'] = 'foo'
        df1['float322'] = 1.
        df1['float322'] = df1['float322'].astype('float32')
        df1['bool'] = df1['float32'] > 0
        df1['time1'] = Timestamp('20130101')
        df1['time2'] = Timestamp('20130102')

        store.append('df_mixed_dtypes1', df1)
        result = store.select('df_mixed_dtypes1').get_dtype_counts()
        expected = Series({'float32': 2, 'float64': 1, 'int32': 1,
                           'bool': 1, 'int16': 1, 'int8': 1,
                           'int64': 1, 'object': 1, 'datetime64[ns]': 2})
        result = result.sort_index()
        result = expected.sort_index()
        tm.assert_series_equal(result, expected)


def test_table_mixed_dtypes():
    # frame
    df = tm.makeDataFrame()
    df['obj1'] = 'foo'
    df['obj2'] = 'bar'
    df['bool1'] = df['A'] > 0
    df['bool2'] = df['B'] > 0
    df['bool3'] = True
    df['int1'] = 1
    df['int2'] = 2
    df['timestamp1'] = Timestamp('20010102')
    df['timestamp2'] = Timestamp('20010103')
    df['datetime1'] = datetime.datetime(2001, 1, 2, 0, 0)
    df['datetime2'] = datetime.datetime(2001, 1, 3, 0, 0)
    df.loc[3:6, ['obj1']] = np.nan
    df = df._consolidate()._convert(datetime=True)

    with ensure_clean_store() as store:
        store.append('df1_mixed', df)
        tm.assert_frame_equal(store.select('df1_mixed'), df)

    with catch_warnings(record=True):
        # panel
        wp = tm.makePanel()
        wp['obj1'] = 'foo'
        wp['obj2'] = 'bar'
        wp['bool1'] = wp['ItemA'] > 0
        wp['bool2'] = wp['ItemB'] > 0
        wp['int1'] = 1
        wp['int2'] = 2
        wp = wp._consolidate()

    with catch_warnings(record=True):
        with ensure_clean_store() as store:
            store.append('p1_mixed', wp)
            assert_panel_equal(store.select('p1_mixed'), wp)


def test_unimplemented_dtypes_table_columns():
    with ensure_clean_store() as store:
        l = [('date', datetime.date(2001, 1, 2))]

        # py3 ok for unicode
        if not compat.PY3:
            l.append(('unicode', u('\\u03c3')))

        # currently not supported dtypes ####
        for n, f in l:
            df = tm.makeDataFrame()
            df[n] = f
            pytest.raises(
                TypeError, store.append, 'df1_%s' % n, df)

    # frame
    df = tm.makeDataFrame()
    df['obj1'] = 'foo'
    df['obj2'] = 'bar'
    df['datetime1'] = datetime.date(2001, 1, 2)
    df = df._consolidate()._convert(datetime=True)

    with ensure_clean_store() as store:
        # this fails because we have a date in the object block......
        pytest.raises(TypeError, store.append, 'df_unimplemented', df)


def test_same_name_scoping():
    with ensure_clean_store() as store:
        df = DataFrame(np.random.randn(20, 2),
                       index=pd.date_range('20130101', periods=20))
        store.put('df', df, format='table')
        expected = df[df.index > pd.Timestamp('20130105')]

        result = store.select('df', 'index>datetime.datetime(2013,1,5)')
        assert_frame_equal(result, expected)

        # technically an error, but allow it
        result = store.select('df', 'index>datetime.datetime(2013,1,5)')
        assert_frame_equal(result, expected)

        result = store.select('df', 'index>datetime.datetime(2013,1,5)')
        assert_frame_equal(result, expected)


def test_series():
    s = tm.makeStringSeries()
    _check_roundtrip(s, tm.assert_series_equal)

    ts = tm.makeTimeSeries()
    _check_roundtrip(ts, tm.assert_series_equal)

    ts2 = Series(ts.index, Index(ts.index, dtype=object))
    _check_roundtrip(ts2, tm.assert_series_equal)

    ts3 = Series(ts.values, Index(np.asarray(ts.index, dtype=object),
                                  dtype=object))
    _check_roundtrip(ts3, tm.assert_series_equal, check_index_type=False)


@pytest.mark.parametrize("compression", [
    False, pytest.param(True, marks=td.skip_if_windows_python_3)
])
def test_frame(compression):
    df = tm.makeDataFrame()

    # put in some random NAs
    df.values[0, 0] = np.nan
    df.values[5, 3] = np.nan

    _check_roundtrip_table(df, tm.assert_frame_equal, compression=compression)
    _check_roundtrip(df, tm.assert_frame_equal, compression=compression)

    tdf = tm.makeTimeDataFrame()
    _check_roundtrip(tdf, tm.assert_frame_equal, compression=compression)

    with ensure_clean_store() as store:
        # not consolidated
        df['foo'] = np.random.randn(len(df))
        store['df'] = df
        recons = store['df']
        assert recons._data.is_consolidated()

    # empty
    _check_roundtrip(df[:0], tm.assert_frame_equal)


def test_empty_series_frame():
    s0 = Series()
    s1 = Series(name='myseries')
    df0 = DataFrame()
    df1 = DataFrame(index=['a', 'b', 'c'])
    df2 = DataFrame(columns=['d', 'e', 'f'])

    _check_roundtrip(s0, tm.assert_series_equal)
    _check_roundtrip(s1, tm.assert_series_equal)
    _check_roundtrip(df0, tm.assert_frame_equal)
    _check_roundtrip(df1, tm.assert_frame_equal)
    _check_roundtrip(df2, tm.assert_frame_equal)


def test_empty_series():
    for dtype in [np.int64, np.float64, np.object, 'm8[ns]', 'M8[ns]']:
        s = Series(dtype=dtype)
        _check_roundtrip(s, tm.assert_series_equal)


def test_overwrite_node():
    with ensure_clean_store() as store:
        store['a'] = tm.makeTimeDataFrame()
        ts = tm.makeTimeSeries()
        store['a'] = ts

        tm.assert_series_equal(store['a'], ts)


def test_invalid_filtering():
    # can't use more than one filter (atm)
    df = tm.makeTimeDataFrame()
    with ensure_clean_store() as store:
        store.put('df', df, format='table')

        # not implemented
        pytest.raises(NotImplementedError, store.select,
                      'df', "columns=['A'] | columns=['B']")

        # in theory we could deal with this
        pytest.raises(NotImplementedError, store.select,
                      'df', "columns=['A','B'] & columns=['C']")


def test_string_select():
    # GH 2973
    with ensure_clean_store() as store:
        df = tm.makeTimeDataFrame()

        # test string ==/!=
        df['x'] = 'none'
        df.loc[2:7, 'x'] = ''

        store.append('df', df, data_columns=['x'])

        result = store.select('df', 'x=none')
        expected = df[df.x == 'none']
        assert_frame_equal(result, expected)

        try:
            result = store.select('df', 'x!=none')
            expected = df[df.x != 'none']
            assert_frame_equal(result, expected)
        except Exception as detail:
            pprint_thing("[{0}]".format(detail))
            pprint_thing(store)
            pprint_thing(expected)

        df2 = df.copy()
        df2.loc[df2.x == '', 'x'] = np.nan

        store.append('df2', df2, data_columns=['x'])
        result = store.select('df2', 'x!=none')
        expected = df2[isna(df2.x)]
        assert_frame_equal(result, expected)

        # int ==/!=
        df['int'] = 1
        df.loc[2:7, 'int'] = 2

        store.append('df3', df, data_columns=['int'])

        result = store.select('df3', 'int=2')
        expected = df[df.int == 2]
        assert_frame_equal(result, expected)

        result = store.select('df3', 'int!=2')
        expected = df[df.int != 2]
        assert_frame_equal(result, expected)


def test_coordinates():
    df = tm.makeTimeDataFrame()
    with ensure_clean_store() as store:
        _maybe_remove(store, 'df')
        store.append('df', df)

        # all
        c = store.select_as_coordinates('df')
        assert((c.values == np.arange(len(df.index))).all())

        # get coordinates back & test vs frame
        _maybe_remove(store, 'df')

        df = DataFrame(dict(A=lrange(5), B=lrange(5)))
        store.append('df', df)
        c = store.select_as_coordinates('df', ['index<3'])
        assert((c.values == np.arange(3)).all())
        result = store.select('df', where=c)
        expected = df.loc[0:2, :]
        tm.assert_frame_equal(result, expected)

        c = store.select_as_coordinates('df', ['index>=3', 'index<=4'])
        assert((c.values == np.arange(2) + 3).all())
        result = store.select('df', where=c)
        expected = df.loc[3:4, :]
        tm.assert_frame_equal(result, expected)
        assert isinstance(c, Index)

        # multiple tables
        _maybe_remove(store, 'df1')
        _maybe_remove(store, 'df2')
        df1 = tm.makeTimeDataFrame()
        df2 = tm.makeTimeDataFrame().rename(columns=lambda x: "%s_2" % x)
        store.append('df1', df1, data_columns=['A', 'B'])
        store.append('df2', df2)

        c = store.select_as_coordinates('df1', ['A>0', 'B>0'])
        df1_result = store.select('df1', c)
        df2_result = store.select('df2', c)
        result = concat([df1_result, df2_result], axis=1)

        expected = concat([df1, df2], axis=1)
        expected = expected[(expected.A > 0) & (expected.B > 0)]
        tm.assert_frame_equal(result, expected)

    # pass array/mask as the coordinates
    with ensure_clean_store() as store:
        df = DataFrame(np.random.randn(1000, 2),
                       index=date_range('20000101', periods=1000))
        store.append('df', df)
        c = store.select_column('df', 'index')
        where = c[DatetimeIndex(c).month == 5].index
        expected = df.iloc[where]

        # locations
        result = store.select('df', where=where)
        tm.assert_frame_equal(result, expected)

        # boolean
        result = store.select('df', where=where)
        tm.assert_frame_equal(result, expected)

        # invalid
        pytest.raises(ValueError, store.select, 'df',
                      where=np.arange(len(df), dtype='float64'))
        pytest.raises(ValueError, store.select, 'df',
                      where=np.arange(len(df) + 1))
        pytest.raises(ValueError, store.select, 'df',
                      where=np.arange(len(df)), start=5)
        pytest.raises(ValueError, store.select, 'df',
                      where=np.arange(len(df)), start=5, stop=10)

        # selection with filter
        selection = date_range('20000101', periods=500)
        result = store.select('df', where='index in selection')
        expected = df[df.index.isin(selection)]
        tm.assert_frame_equal(result, expected)

        # list
        df = DataFrame(np.random.randn(10, 2))
        store.append('df2', df)
        result = store.select('df2', where=[0, 3, 5])
        expected = df.iloc[[0, 3, 5]]
        tm.assert_frame_equal(result, expected)

        # boolean
        where = [True] * 10
        where[-2] = False
        result = store.select('df2', where=where)
        expected = df.loc[where]
        tm.assert_frame_equal(result, expected)

        # start/stop
        result = store.select('df2', start=5, stop=10)
        expected = df[5:10]
        tm.assert_frame_equal(result, expected)


@pytest.mark.skipif(
    LooseVersion(tables.__version__) < LooseVersion('3.1.0'),
    reason=("tables version does not support fix for nan selection "
            "bug: GH 4858"))
def test_nan_selection_bug_4858():
    with ensure_clean_store() as store:
        df = DataFrame(dict(cols=range(6), values=range(6)),
                       dtype='float64')
        df['cols'] = (df['cols'] + 10).apply(str)
        df.iloc[0] = np.nan

        expected = DataFrame(dict(cols=['13.0', '14.0', '15.0'], values=[
                             3., 4., 5.]), index=[3, 4, 5])

        # write w/o the index on that particular column
        store.append('df', df, data_columns=True, index=['cols'])
        result = store.select('df', where='values>2.0')
        assert_frame_equal(result, expected)


@pytest.mark.parametrize('start, stop', [(0, 2), (1, 2), (None, None)])
def test_contiguous_mixed_data_table(start, stop):
    # GH 17021
    # ValueError when reading a contiguous mixed-data table ft. VLArray
    df = DataFrame({'a': Series([20111010, 20111011, 20111012]),
                    'b': Series(['ab', 'cd', 'ab'])})

    with ensure_clean_store() as store:
        store.append('test_dataset', df)

        result = store.select('test_dataset', start=start, stop=stop)
        assert_frame_equal(df[start:stop], result)


def test_copy():
    with catch_warnings(record=True):
        def do_copy(f, new_f=None, keys=None,
                    propindexes=True, **kwargs):
            try:
                store = HDFStore(f, 'r')

                if new_f is None:
                    fd, new_f = tempfile.mkstemp()

                tstore = store.copy(
                    new_f, keys=keys, propindexes=propindexes, **kwargs)

                # check keys
                if keys is None:
                    keys = store.keys()
                assert set(keys) == set(tstore.keys())

                # check indicies & nrows
                for k in tstore.keys():
                    if tstore.get_storer(k).is_table:
                        new_t = tstore.get_storer(k)
                        orig_t = store.get_storer(k)

                        assert orig_t.nrows == new_t.nrows

                        # check propindixes
                        if propindexes:
                            for a in orig_t.axes:
                                if a.is_indexed:
                                    assert new_t[a.name].is_indexed

            finally:
                safe_close(store)
                safe_close(tstore)
                safe_close(fd)
                safe_remove(new_f)

        # new table
        df = tm.makeDataFrame()

        try:
            path = create_tempfile()
            st = HDFStore(path)
            st.append('df', df, data_columns=['A'])
            st.close()
            do_copy(f=path)
            do_copy(f=path, propindexes=False)
        finally:
            safe_remove(path)


def test_query_with_nested_special_character():
    df = DataFrame({'a': ['a', 'a', 'c', 'b',
                          'test & test', 'c', 'b', 'e'],
                    'b': [1, 2, 3, 4, 5, 6, 7, 8]})
    expected = df[df.a == 'test & test']
    with ensure_clean_store() as store:
        store.append('test', df, format='table', data_columns=True)
        result = store.select('test', 'a = "test & test"')
    tm.assert_frame_equal(expected, result)


def test_duplicate_column_name():
    df = DataFrame(columns=["a", "a"], data=[[0, 0]])

    with ensure_clean_path() as path:
        pytest.raises(ValueError, df.to_hdf,
                      path, 'df', format='fixed')

        df.to_hdf(path, 'df', format='table')
        other = read_hdf(path, 'df')

        tm.assert_frame_equal(df, other)
        assert df.equals(other)
        assert other.equals(df)


def test_round_trip_equals():
    # GH 9330
    df = DataFrame({"B": [1, 2], "A": ["x", "y"]})

    with ensure_clean_path() as path:
        df.to_hdf(path, 'df', format='table')
        other = read_hdf(path, 'df')
        tm.assert_frame_equal(df, other)
        assert df.equals(other)
        assert other.equals(df)


def test_to_hdf_with_object_column_names():
    # GH9057
    # Writing HDF5 table format should only work for string-like
    # column types
    types_should_fail = [tm.makeIntIndex, tm.makeFloatIndex,
                         tm.makeDateIndex, tm.makeTimedeltaIndex,
                         tm.makePeriodIndex]
    types_should_run = [tm.makeStringIndex, tm.makeCategoricalIndex]

    if compat.PY3:
        types_should_run.append(tm.makeUnicodeIndex)
    else:
        types_should_fail.append(tm.makeUnicodeIndex)

    for index in types_should_fail:
        df = DataFrame(np.random.randn(10, 2), columns=index(2))
        with ensure_clean_path() as path:
            with catch_warnings(record=True):
                with pytest.raises(
                    ValueError, msg=("cannot have non-object label "
                                     "DataIndexableCol")):
                    df.to_hdf(path, 'df', format='table',
                              data_columns=True)

    for index in types_should_run:
        df = DataFrame(np.random.randn(10, 2), columns=index(2))
        with ensure_clean_path() as path:
            with catch_warnings(record=True):
                df.to_hdf(path, 'df', format='table', data_columns=True)
                result = pd.read_hdf(
                    path, 'df', where="index = [{0}]".format(df.index[0]))
                assert(len(result))


def test_query_long_float_literal():
    # GH 14241
    df = pd.DataFrame({'A': [1000000000.0009,
                             1000000000.0011,
                             1000000000.0015]})

    with ensure_clean_store() as store:
        store.append('test', df, format='table', data_columns=True)

        cutoff = 1000000000.0006
        result = store.select('test', "A < %.4f" % cutoff)
        assert result.empty

        cutoff = 1000000000.0010
        result = store.select('test', "A > %.4f" % cutoff)
        expected = df.loc[[1, 2], :]
        tm.assert_frame_equal(expected, result)

        exact = 1000000000.0011
        result = store.select('test', 'A == %.4f' % exact)
        expected = df.loc[[1], :]
        tm.assert_frame_equal(expected, result)


def test_query_compare_column_type():
    # GH 15492
    df = pd.DataFrame({'date': ['2014-01-01', '2014-01-02'],
                       'real_date': date_range('2014-01-01', periods=2),
                       'float': [1.1, 1.2],
                       'int': [1, 2]},
                      columns=['date', 'real_date', 'float', 'int'])

    with ensure_clean_store() as store:
        store.append('test', df, format='table', data_columns=True)

        ts = pd.Timestamp('2014-01-01')  # noqa
        result = store.select('test', where='real_date > ts')
        expected = df.loc[[1], :]
        tm.assert_frame_equal(expected, result)

        for op in ['<', '>', '==']:
            # non strings to string column always fail
            for v in [2.1, True, pd.Timestamp('2014-01-01'),
                      pd.Timedelta(1, 's')]:
                query = 'date {op} v'.format(op=op)
                with pytest.raises(TypeError):
                    result = store.select('test', where=query)

            # strings to other columns must be convertible to type
            v = 'a'
            for col in ['int', 'float', 'real_date']:
                query = '{col} {op} v'.format(op=op, col=col)
                with pytest.raises(ValueError):
                    result = store.select('test', where=query)

            for v, col in zip(['1', '1.1', '2014-01-01'],
                              ['int', 'float', 'real_date']):
                query = '{col} {op} v'.format(op=op, col=col)
                result = store.select('test', where=query)

                if op == '==':
                    expected = df.loc[[0], :]
                elif op == '>':
                    expected = df.loc[[1], :]
                else:
                    expected = df.loc[[], :]
                tm.assert_frame_equal(expected, result)
