# -*- coding: utf-8 -*-
"""测试各个数据源在当前网络（GitHub 服务器）能不能拿到数据。只抓少量数据，1~2 分钟跑完。"""
import time, traceback
import requests

UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36',
      'Referer': 'https://quote.eastmoney.com/'}
results = []

def check(name, fn):
    t = time.time()
    try:
        info = fn()
        results.append(('成功', name, f'{time.time()-t:.1f}s', info))
    except Exception as e:
        results.append(('失败', name, f'{time.time()-t:.1f}s', f'{type(e).__name__}: {str(e)[:150]}'))

def em_kline(secid):
    r = requests.get('https://push2his.eastmoney.com/api/qt/stock/kline/get', headers=UA, timeout=20,
                     params={'secid': secid, 'fields1': 'f1,f2,f3', 'fields2': 'f51,f52,f53,f54,f55', 'klt': '101',
                             'fqt': '0', 'beg': '20141201', 'end': '20500101', 'lmt': '1000000'})
    kl = r.json()['data']['klines']
    return f'{len(kl)} 天，最早 {kl[0][:10]}，最新 {kl[-1]}'

def em_list(fs):
    r = requests.get('https://push2.eastmoney.com/api/qt/clist/get', headers=UA, timeout=20,
                     params={'pn': 1, 'pz': 100, 'po': 1, 'np': 1, 'fltt': 2, 'invt': 2, 'fid': 'f3', 'fs': fs, 'fields': 'f12,f14'})
    d = r.json()['data']
    diff = d['diff'] if isinstance(d['diff'], list) else list(d['diff'].values())
    return f"共 {d['total']} 个，例如 {[x['f14'] for x in diff[:5]]}"

def sw(code):
    import akshare as ak
    df = ak.index_hist_sw(symbol=code, period='day')
    return f'{len(df)} 天，最早 {df.iloc[0]["日期"]}，最新 {df.iloc[-1]["日期"]} 收盘 {df.iloc[-1]["收盘"]}'

def sina_index():
    import akshare as ak
    df = ak.index_zh_daily_sina(symbol='sh000985')
    return f'{len(df)} 天，最新 {df.iloc[-1].to_dict()}'

def tx_index():
    import akshare as ak
    df = ak.index_zh_daily_tx(symbol='sh000985')
    return f'{len(df)} 天，最新 {df.iloc[-1].to_dict()}'

def ths_concept():
    import akshare as ak
    df = ak.stock_board_concept_name_ths()
    return f'{len(df)} 个概念'

check('东方财富 宽基指数K线（中证全指）', lambda: em_kline('1.000985'))
check('东方财富 行业板块列表', lambda: em_list('m:90+t:2'))
check('东方财富 概念板块列表', lambda: em_list('m:90+t:3'))
check('东方财富 板块K线（BK0475 银行）', lambda: em_kline('90.BK0475'))
check('申万宏源 申万一级（801780 银行）', lambda: sw('801780'))
check('申万宏源 申万二级（801081 半导体）', lambda: sw('801081'))
check('备选：新浪 指数日线', sina_index)
check('备选：腾讯 指数日线', tx_index)
check('备选：同花顺 概念列表', ths_concept)

print('\n================ 测试结果 ================')
for ok, name, t, info in results:
    print(f'[{ok}] {name}  ({t})\n        {info}')
print('==========================================')
print(f"成功 {sum(r[0]=='成功' for r in results)} / {len(results)}")
