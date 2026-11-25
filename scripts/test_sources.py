# -*- coding: utf-8 -*-
"""第二轮测试：东方财富板块换线路重试；同花顺行业/概念指数能不能拿到历史数据。"""
import time, datetime as dt
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

def em_kline(host, secid):
    r = requests.get(f'https://{host}/api/qt/stock/kline/get', headers=UA, timeout=20,
                     params={'secid': secid, 'fields1': 'f1,f2,f3', 'fields2': 'f51,f52,f53,f54,f55', 'klt': '101',
                             'fqt': '0', 'beg': '20141201', 'end': '20500101', 'lmt': '1000000'})
    kl = r.json()['data']['klines']
    return f'{len(kl)} 天，最新 {kl[-1]}'

def em_list(host):
    r = requests.get(f'https://{host}/api/qt/clist/get', headers=UA, timeout=30,
                     params={'pn': 1, 'pz': 100, 'po': 1, 'np': 1, 'fltt': 2, 'invt': 2, 'fid': 'f3', 'fs': 'm:90+t:3', 'fields': 'f12,f14'})
    d = r.json()['data']
    return f"共 {d['total']} 个"

def ths_concepts():
    import akshare as ak
    df = ak.stock_board_concept_name_ths()
    names = df.iloc[:, 0].astype(str).tolist() if 'name' not in df.columns else df['name'].tolist()
    hit = [n for n in names if any(k in n for k in ['航天', '机器人', '人工智能', '芯片', '半导体', '算力', '低空', '军工', '卫星'])]
    return f'{len(df)} 个，列名 {list(df.columns)}，相关的有 {hit[:20]}'

def ths_concept_hist(name, start):
    import akshare as ak
    df = ak.stock_board_concept_index_ths(symbol=name, start_date=start, end_date=dt.date.today().strftime('%Y%m%d'))
    return f'{len(df)} 天，最早 {df.iloc[0, 0]}，最新 {df.iloc[-1].tolist()[:5]}'

def ths_industries():
    import akshare as ak
    df = ak.stock_board_industry_name_ths()
    return f'{len(df)} 个，列名 {list(df.columns)}，前几个 {df.iloc[:8, 0].tolist()}'

def ths_industry_hist(name):
    import akshare as ak
    df = ak.stock_board_industry_index_ths(symbol=name, start_date='20140101', end_date=dt.date.today().strftime('%Y%m%d'))
    return f'{len(df)} 天，最早 {df.iloc[0, 0]}，最新 {df.iloc[-1].tolist()[:5]}'

for host in ['push2his.eastmoney.com', '91.push2his.eastmoney.com', '7.push2his.eastmoney.com']:
    check(f'东方财富 板块K线 BK0475 银行（线路 {host}）', lambda h=host: em_kline(h, '90.BK0475'))
    time.sleep(2)
for host in ['82.push2.eastmoney.com', '17.push2.eastmoney.com']:
    check(f'东方财富 概念板块列表（线路 {host}）', lambda h=host: em_list(h))
check('同花顺 概念列表', ths_concepts)
check('同花顺 概念指数 商业航天（2024起）', lambda: ths_concept_hist('商业航天', '20240101'))
check('同花顺 概念指数 人形机器人（2024起）', lambda: ths_concept_hist('人形机器人', '20240101'))
check('同花顺 概念指数 芯片概念（2014起，测全历史速度）', lambda: ths_concept_hist('芯片概念', '20140101'))
check('同花顺 行业列表', ths_industries)
check('同花顺 行业指数 半导体（2014起）', lambda: ths_industry_hist('半导体'))

print('\n================ 测试结果 ================')
for ok, name, t, info in results:
    print(f'[{ok}] {name}  ({t})\n        {info}')
print('==========================================')
print(f"成功 {sum(r[0]=='成功' for r in results)} / {len(results)}")
