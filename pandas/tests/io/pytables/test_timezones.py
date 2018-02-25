import pytest
import datetime
from datetime import timedelta

import numpy as np
import pandas as pd
from pandas import (Series, DataFrame, date_range, Timestamp, DatetimeIndex)
from pandas.tests.io.pytables.common import ensure_clean_store, _maybe_remove
import pandas.util.testing as tm
import pandas.util._test_decorators as td
from pandas.util.testing import assert_frame_equal, set_timezone
from pandas._libs.tslibs.timezones import maybe_get_tz
from pandas.compat import lrange


def _compare_with_tz(a, b):
    tm.assert_frame_equal(a, b)
    # compare the zones on each element
    for c in a.columns:
        for i in a.index:
            a_e = a.loc[i, c]
            b_e = b.loc[i, c]
            if not (a_e == b_e and a_e.tz == b_e.tz):
                raise AssertionError(
                    "invalid tz comparison [%s] [%s]" % (a_e, b_e))


def test_append_with_timezones_dateutil():

    # use maybe_get_tz instead of dateutil.tz.gettz to handle the windows
    # filename issues.
    gettz = lambda x: maybe_get_tz('dateutil/' + x)

    # as columns
    with ensure_clean_store() as store:

        _maybe_remove(store, 'df_tz')
        df = DataFrame(dict(A=[Timestamp('20130102 2:00:00', tz=gettz(
            'US/Eastern')) + timedelta(hours=1) * i for i in range(5)]))

        store.append('df_tz', df, data_columns=['A'])
        result = store['df_tz']
        _compare_with_tz(result, df)
        assert_frame_equal(result, df)

        # select with tz aware
        expected = df[df.A >= df.A[3]]
        result = store.select('df_tz', where='A>=df.A[3]')
        _compare_with_tz(result, expected)

        # ensure we include dates in DST and STD time here.
        _maybe_remove(store, 'df_tz')
        df = DataFrame(dict(A=Timestamp('20130102',
                                        tz=gettz('US/Eastern')),
                            B=Timestamp('20130603',
                                        tz=gettz('US/Eastern'))),
                       index=range(5))
        store.append('df_tz', df)
        result = store['df_tz']
        _compare_with_tz(result, df)
        assert_frame_equal(result, df)

        df = DataFrame(dict(A=Timestamp('20130102',
                                        tz=gettz('US/Eastern')),
                            B=Timestamp('20130102', tz=gettz('EET'))),
                       index=range(5))
        pytest.raises(ValueError, store.append, 'df_tz', df)

        # this is ok
        _maybe_remove(store, 'df_tz')
        store.append('df_tz', df, data_columns=['A', 'B'])
        result = store['df_tz']
        _compare_with_tz(result, df)
        assert_frame_equal(result, df)

        # can't append with diff timezone
        df = DataFrame(dict(A=Timestamp('20130102',
                                        tz=gettz('US/Eastern')),
                            B=Timestamp('20130102', tz=gettz('CET'))),
                       index=range(5))
        pytest.raises(ValueError, store.append, 'df_tz', df)

    # as index
    with ensure_clean_store() as store:

        # GH 4098 example
        df = DataFrame(dict(A=Series(lrange(3), index=date_range(
            '2000-1-1', periods=3, freq='H', tz=gettz('US/Eastern')))))

        _maybe_remove(store, 'df')
        store.put('df', df)
        result = store.select('df')
        assert_frame_equal(result, df)

        _maybe_remove(store, 'df')
        store.append('df', df)
        result = store.select('df')
        assert_frame_equal(result, df)


def test_append_with_timezones_pytz():

    # as columns
    with ensure_clean_store() as store:

        _maybe_remove(store, 'df_tz')
        df = DataFrame(dict(A=[Timestamp('20130102 2:00:00',
                                         tz='US/Eastern') +
                               timedelta(hours=1) * i
                               for i in range(5)]))
        store.append('df_tz', df, data_columns=['A'])
        result = store['df_tz']
        _compare_with_tz(result, df)
        assert_frame_equal(result, df)

        # select with tz aware
        _compare_with_tz(store.select(
            'df_tz', where='A>=df.A[3]'), df[df.A >= df.A[3]])

        _maybe_remove(store, 'df_tz')
        # ensure we include dates in DST and STD time here.
        df = DataFrame(dict(A=Timestamp('20130102', tz='US/Eastern'),
                            B=Timestamp('20130603', tz='US/Eastern')),
                       index=range(5))
        store.append('df_tz', df)
        result = store['df_tz']
        _compare_with_tz(result, df)
        assert_frame_equal(result, df)

        df = DataFrame(dict(A=Timestamp('20130102', tz='US/Eastern'),
                            B=Timestamp('20130102', tz='EET')),
                       index=range(5))
        pytest.raises(ValueError, store.append, 'df_tz', df)

        # this is ok
        _maybe_remove(store, 'df_tz')
        store.append('df_tz', df, data_columns=['A', 'B'])
        result = store['df_tz']
        _compare_with_tz(result, df)
        assert_frame_equal(result, df)

        # can't append with diff timezone
        df = DataFrame(dict(A=Timestamp('20130102', tz='US/Eastern'),
                            B=Timestamp('20130102', tz='CET')),
                       index=range(5))
        pytest.raises(ValueError, store.append, 'df_tz', df)

    # as index
    with ensure_clean_store() as store:

        # GH 4098 example
        df = DataFrame(dict(A=Series(lrange(3), index=date_range(
            '2000-1-1', periods=3, freq='H', tz='US/Eastern'))))

        _maybe_remove(store, 'df')
        store.put('df', df)
        result = store.select('df')
        assert_frame_equal(result, df)

        _maybe_remove(store, 'df')
        store.append('df', df)
        result = store.select('df')
        assert_frame_equal(result, df)


def test_tseries_select_index_column():
    # GH7777
    # selecting a UTC datetimeindex column did
    # not preserve UTC tzinfo set before storing

    # check that no tz still works
    rng = date_range('1/1/2000', '1/30/2000')
    frame = DataFrame(np.random.randn(len(rng), 4), index=rng)

    with ensure_clean_store() as store:
        store.append('frame', frame)
        result = store.select_column('frame', 'index')
        assert rng.tz == DatetimeIndex(result.values).tz

    # check utc
    rng = date_range('1/1/2000', '1/30/2000', tz='UTC')
    frame = DataFrame(np.random.randn(len(rng), 4), index=rng)

    with ensure_clean_store() as store:
        store.append('frame', frame)
        result = store.select_column('frame', 'index')
        assert rng.tz == result.dt.tz

    # double check non-utc
    rng = date_range('1/1/2000', '1/30/2000', tz='US/Eastern')
    frame = DataFrame(np.random.randn(len(rng), 4), index=rng)

    with ensure_clean_store() as store:
        store.append('frame', frame)
        result = store.select_column('frame', 'index')
        assert rng.tz == result.dt.tz


def test_timezones_fixed():
    with ensure_clean_store() as store:

        # index
        rng = date_range('1/1/2000', '1/30/2000', tz='US/Eastern')
        df = DataFrame(np.random.randn(len(rng), 4), index=rng)
        store['df'] = df
        result = store['df']
        assert_frame_equal(result, df)

        # as data
        # GH11411
        _maybe_remove(store, 'df')
        df = DataFrame({'A': rng,
                        'B': rng.tz_convert('UTC').tz_localize(None),
                        'C': rng.tz_convert('CET'),
                        'D': range(len(rng))}, index=rng)
        store['df'] = df
        result = store['df']
        assert_frame_equal(result, df)


def test_fixed_offset_tz():
    rng = date_range('1/1/2000 00:00:00-07:00', '1/30/2000 00:00:00-07:00')
    frame = DataFrame(np.random.randn(len(rng), 4), index=rng)

    with ensure_clean_store() as store:
        store['frame'] = frame
        recons = store['frame']
        tm.assert_index_equal(recons.index, rng)
        assert rng.tz == recons.index.tz


@td.skip_if_windows
def test_store_timezone():
    # GH2852
    # issue storing datetime.date with a timezone as it resets when read
    # back in a new timezone

    # original method
    with ensure_clean_store() as store:

        today = datetime.date(2013, 9, 10)
        df = DataFrame([1, 2, 3], index=[today, today, today])
        store['obj1'] = df
        result = store['obj1']
        assert_frame_equal(result, df)

    # with tz setting
    with ensure_clean_store() as store:

        with set_timezone('EST5EDT'):
            today = datetime.date(2013, 9, 10)
            df = DataFrame([1, 2, 3], index=[today, today, today])
            store['obj1'] = df

        with set_timezone('CST6CDT'):
            result = store['obj1']

        assert_frame_equal(result, df)


def test_legacy_datetimetz_object():
    # legacy from < 0.17.0
    # 8260
    expected = DataFrame(dict(A=Timestamp('20130102', tz='US/Eastern'),
                              B=Timestamp('20130603', tz='CET')),
                         index=range(5))
    with ensure_clean_store(
            tm.get_data_path('legacy_hdf/datetimetz_object.h5'),
            mode='r') as store:
        result = store['df']
        assert_frame_equal(result, expected)


def test_dst_transitions():
    # make sure we are not failing on transaitions
    with ensure_clean_store() as store:
        times = pd.date_range("2013-10-26 23:00", "2013-10-27 01:00",
                              tz="Europe/London",
                              freq="H",
                              ambiguous='infer')

        for i in [times, times + pd.Timedelta('10min')]:
            _maybe_remove(store, 'df')
            df = DataFrame({'A': range(len(i)), 'B': i}, index=i)
            store.append('df', df)
            result = store.select('df')
            assert_frame_equal(result, df)
