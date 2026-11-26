# -*- coding: utf-8 -*-
"""测试 Tushare 在 GitHub 服务器上能不能用，以及各接口的权限和返回格式。
token 从环境变量 TUSHARE_TOKEN 读取（GitHub Secrets），不会打印出来。"""
import os, time, datetime as dt
import tushare as ts

token = os.environ.get('TUSHARE_TOKEN', '')
print('token 已读取' if token else '没有读到 TUSHARE_TOKEN，请检查 GitHub Secrets', f'(长度 {len(token)})')
pro = ts.pro_api(token)
today = dt.date.today().strftime('%Y%m%d')
results = []

def check(name, api, **kw):
    t = time.time()
    try:
        df = pro.query(api, **kw)
        info = f'{len(df)} 行；列 {list(df.columns)[:12]}'
        if len(df):
            info += f'\n        第一行 {df.iloc[0].to_dict()}'
        results.append(('成功' if len(df) else '空', name, f'{time.time()-t:.1f}s', info))
        return df
    except Exception as e:
        results.append(('失败', name, f'{time.time()-t:.1f}s', f'{type(e).__name__}: {str(e)[:200]}'))
    time.sleep(0.3)

cal = check('交易日历', 'trade_cal', exchange='SSE', start_date='20261101', end_date=today, is_open='1')
last = cal['cal_date'].max() if cal is not None and len(cal) else today
# 申万
check('申万分类 SW2021 一级', 'index_classify', level='L1', src='SW2021')
check('申万分类 SW2021 二级', 'index_classify', level='L2', src='SW2021')
check('申万行业日线：某一天全部', 'sw_daily', trade_date=last)
check('申万行业日线：银行 801780.SI 历史', 'sw_daily', ts_code='801780.SI', start_date='20140101', end_date=today)
check('申万成分股（银行）', 'index_member_all', l1_code='801780.SI')
# 同花顺
check('同花顺板块列表（概念 N）', 'ths_index', exchange='A', type='N')
check('同花顺板块列表（行业 I）', 'ths_index', exchange='A', type='I')
check('同花顺板块日线：某一天全部', 'ths_daily', trade_date=last)
check('同花顺板块成分', 'ths_member', ts_code='885556.TI')
# 东方财富
check('东方财富板块列表', 'dc_index', trade_date=last)
check('东方财富板块日线：某一天全部', 'dc_daily', trade_date=last)
# 宽基
check('宽基：中证全指 000985.CSI', 'index_daily', ts_code='000985.CSI', start_date='20141201', end_date=today)
check('宽基：上证指数 000001.SH', 'index_daily', ts_code='000001.SH', start_date='20261101', end_date=today)
# 个股（用于以后算广度）
check('全市场个股日线：某一天', 'daily', trade_date=last)

print('\n================ 测试结果 ================')
for ok, name, t, info in results:
    print(f'[{ok}] {name}  ({t})\n        {info}')
print('==========================================')
print(f"成功 {sum(r[0]=='成功' for r in results)} / {len(results)}")
