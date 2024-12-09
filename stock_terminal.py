#!/usr/bin/python
# -*- coding: utf8 -*-
# @Author: Devin-Kung
# Project: https://github.com/Devin-Kung/stock_terminal

import re
import urwid
import requests
from datetime import datetime
from rich import print
from rich.table import Table
from rich.console import Console
import chinese_calendar as calendar

# 是否开启自动刷新(非交易时间默认关闭，可手动开启)
auto_refresh = True
# 是否启用调色板(彩色输出)
use_palette = False
# 自动刷新间隔(s)(接口的数据更新频率为3s)
refresh_duration = 3
# 股票代码
tickers = [
    'sh000001', # 上证指数
    '159934', # 黄金ETF
    '159941', # 纳指ETF
    '159952', # 创业板ETF广发
    '159692', # 证券ETF东财
    '002583', # 海能达
    '002456', # 欧菲光
    '000158', # 常山北明
    '300059', # 东方财富
    '600839', # 四川长虹
    '000062', # 深圳华强
    '601127', # 塞力斯
    '002354', # 天娱数科
    '600776', # 东方通信
    '002175', # 东方智造
    '002467', # 二六三
    '002045', # 国光电器
    '601360', # 三六零
    '002362', # 汉王科技
    '002402', # 和而泰
    '600206', # 有研新材
    '600340', # 华夏幸福
    '001696', # 宗申动力
    '603038', # 华立股份
    '002131', # 利欧股份
    '002820', # 桂发祥
    '605179', # 一鸣食品
    '603366', # 日出东方
    '003042', # 中农联合
    '000716', # 黑芝麻
    '000564', # 供销大集
    '002995', # 天地在线
    '002103', # 广博股份
    '002329', # 皇氏集团
]


# 终端样式配置
palette = [
    ('titlebar', 'light blue, bold', ''),
    ('refresh button', 'dark green, bold', ''),
    ('auto_refresh button', 'dark cyan', ''),
    ('quit button', 'dark red', ''),
    ('page button', 'dark blue', ''),
    ('palette button', 'dark magenta', ''),
    ('1m', 'bold', ''),
    ('30m', 'black', ''),
    ('31m', 'dark red', ''),
    ('32m', 'dark green', ''),
    ('33m', 'yellow', ''),
    ('34m', 'dark blue', ''),
    ('35m', 'dark magenta', ''),
    ('36m', 'dark cyan', ''),
    ('37m', 'white', '')
]

header_text = urwid.Text(u'实时数据')
header = urwid.AttrMap(header_text, 'titlebar')

default_menu = [
    u'立即刷新(', ('refresh button', u'R/r'), ') | ',
    u'自动刷新(', ('auto_refresh button', u'A/a'), ') | ',
    u'翻页(', ('page button', u'PgUp/PgDn/↑/↓'), ') | ',
    u'彩色显示(', ('palette button', u'C/c'), ') | ',
    u'退出进程(', ('quit button', u'Q/q'), ')',
]
# 底部菜单
menu = urwid.Text(default_menu)

# 数据展示
quote_text = urwid.Text(u'按下 (R/r) 以获取数据...')
quote_filler = urwid.Filler(quote_text, valign='top', top=1, bottom=1)
quote_box = urwid.Scrollable(quote_filler)

# 布局
layout = urwid.Frame(header=header, body=quote_box, footer=menu)

# 上一次请求的股价数据
last_price = {}

"""
0: 股票名字
1: 今日开盘价
2: 昨日收盘价
3: 当前价格
4: 今日最高价
5: 今日最低价
6: 竞买价，即“买一”报价
7: 竞卖价，即“卖一”报价
8: 成交数(股)
9: 成交额(元)
10: 买一申请数(股)
11: 买一报价
(12, 13), (14, 15), (16, 17), (18, 19) 买二、买三、买四、买五的申请数(股)和报价
20: 卖一申请数(股)
21: 卖一报价
(22, 23), (24, 25), (26, 27), (28, 29) 卖二、卖三、卖四、卖五的申请数(股)和报价
30: 日期
31: 时间
"""
# 获取股票数据
# 
def get_price(tickers):
    headers = {'referer': 'http://finance.sina.com.cn'}
    tickerurl = "http://hq.sinajs.cn/list="
    query_str = ''
    for ticker in tickers:
        if str(ticker).startswith('30') or str(ticker).startswith('00') or str(ticker).startswith('15'):
            query_str += 'sz' + str(ticker) + ','
        elif str(ticker).startswith('60') or str(ticker).startswith('688'):
            query_str += 'sh' + str(ticker) + ','
        else:
            query_str += ticker + ','
    url = tickerurl + query_str
    res = requests.get(url, headers=headers).text

    # 响应的结构如下
    # var hq_str_sz002583="海能达,17.290,17.530,17.550,17.970,16.960,17.540,17.550,255884353,4462582236.680,212300,17.540,240100,17.530,88900,17.520,161100,17.510,1177600,17.500,1011020,17.550,369900,17.560,519500,17.570,280000,17.580,180500,17.590,2024-11-29,15:00:00,00";
    # var hq_str_sz002456="欧菲光,13.380,13.450,13.390,13.630,13.000,13.390,13.400,341289935,4540992553.610,1804500,13.390,1595000,13.380,452900,13.370,370000,13.360,684000,13.350,1537156,13.400,292600,13.410,400500,13.420,139500,13.430,143300,13.440,2024-11-29,15:00:00,00";
    # 使用正则表达式提取数据
    splited = res.split(';')
    result = {}
    pattern = re.compile(r'var hq_str_(.*)="(.*)"')
    for s in splited:
        s = s.strip()
        match = pattern.match(s)
        if match:
            result[match.group(1)] = match.group(2).split(',')
    
    return result

# 获取更新表格
def get_update_table():
    global last_price

    table = Table(show_header=True, header_style=None)

    table.add_column("股票", justify='center')
    table.add_column("昨收", justify='center')
    table.add_column("今开", justify='center')
    table.add_column("实时", justify='center')
    table.add_column("波动", justify='center')
    table.add_column("涨跌", justify='center')
    table.add_column("涨跌幅", justify='center')
    table.add_column("今日最高", justify='center')
    table.add_column("今日最低", justify='center')
    table.add_column("成交数(手)", justify='center')
    table.add_column("成交额(万元)", justify='center')
    table.add_column("时间", justify='center')

    tickers_data = get_price(tickers)
    for ticker, data in tickers_data.items():
        try:
            # 股票波动值
            diff = 0.0
            if last_price.get(ticker) is not None:
                diff = float(data[3]) - float(last_price[ticker][3])

            table.add_row(
                data[0].strip(),
                str(data[2]),
                str(data[1]),
                str(data[3]),
                ('+' if diff > 0 else '') + str(round(diff, 3)),
                str(round(float(data[3]) - float(data[2]), 2)),
                str(round((float(data[3]) - float(data[2])) / float(data[2]) * 100, 2)) + '%',
                str(data[4]) + '(' + str(round((float(data[4]) - float(data[2])) / float(data[2]) * 100, 2)) + '%)',
                str(data[5]) + '(' + str(round((float(data[5]) - float(data[2])) / float(data[2]) * 100, 2)) + '%)',
                str(round(float(data[8]) / 100, 2)),
                str(round(float(data[9]) / 10000, 2)),
                str(data[30] + ' ' + data[31]),
                style=('red' if float(data[3]) - float(data[2]) > 0 else 'green' if float(data[3]) - float(data[2]) < 0 else None)
            )

            # 更新上一次的股价数据
            last_price[ticker] = data
        except Exception as e:
            continue

    return table


# 监听键盘输入
def handle_input(key):
    global urwid_alarm

    if key == 'R' or key == 'r':
        quote_text.set_text('获取数据中，请等待...')
        refresh(main_loop, '')

    elif key == 'Q' or key == 'q':
        if urwid_alarm is not None:
            main_loop.remove_alarm(urwid_alarm)
        
        quote_text.set_text('正在退出，请稍后...')
        main_loop.draw_screen()
        raise urwid.ExitMainLoop()

    elif key == 'A' or key == 'a':
        global auto_refresh
        auto_refresh = not auto_refresh
        if auto_refresh:
            urwid_alarm = main_loop.set_alarm_in(0, refresh)
        else:
            if urwid_alarm is not None:
                main_loop.remove_alarm(urwid_alarm)
            urwid_alarm = None
            top_text = header_text.get_text()[0] + u' | 已暂停自动刷新'
            header_text.set_text(top_text)
            main_loop.draw_screen()

    elif key == 'C' or key == 'c':
        global use_palette
        global palette
        use_palette = not use_palette
        if use_palette:
            main_loop.screen.register_palette(palette)
        else:
            # 将调色板的样式清空，即每一项的第二个参数置为空
            palette_empty = [(name, '', background) for name, _, background in palette]
            main_loop.screen.register_palette(palette_empty)
        
        header_text.set_text('')
        quote_text.set_text('')
        menu.set_text('')
        main_loop.draw_screen()
        
        refresh(main_loop, '')
        menu.set_text(default_menu)
        main_loop.draw_screen()

# 将ansi样式转换为urwid样式
def ansi_str_to_urwid(ansi):
    # 查找所有ansi控制字符的位置
    ansi_positions = [i for i in range(len(ansi)) if ansi[i] == '\033']

    urwid_text_tuple = []
    pre_pos = 0
    pre_style = None
    # 遍历所有控制字符，将其转换为urwid样式
    for i in range(len(ansi_positions)):
        pos = ansi_positions[i]
        m_index = ansi.find('m', pos)
        # 获取控制字符的值，如 0m, 1m
        ansi_code = ansi[pos + 2:m_index + 1]
        
        if ansi[pre_pos:pos] == '' or ansi[pre_pos:pos].strip() == '' or pre_style is None:
            urwid_text_tuple.append(u"{}".format(ansi[pre_pos:pos]))
        else:
            urwid_text_tuple.append((pre_style, u"{}".format(ansi[pre_pos:pos])))
        
        if ansi_code == '0m':
            pre_style = None
        else:
            pre_style = ansi_code
        pre_pos = m_index + 1
    # 添加最后一个
    urwid_text_tuple.append(u"{}".format(ansi[pre_pos:]))

    return urwid_text_tuple


# 刷新数据面板
def refresh(_loop, _data):    
    global urwid_alarm
    global auto_refresh

    if urwid_alarm is not None:
        main_loop.remove_alarm(urwid_alarm)
    
    console = Console(record=True)
    table = get_update_table()

    with console.capture() as capture:
        console.print(table)

    header_text.set_text(u'实时数据 | 刷新间隔: {}s | 刷新于: {}'.format(refresh_duration, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    if auto_refresh is False:
        header_text.set_text(header_text.get_text()[0] + u' | 已暂停自动刷新')
    quote_text.set_text(ansi_str_to_urwid(capture.get()))
    
    main_loop.draw_screen()
    # 如果开启自动刷新，则继续刷新
    if auto_refresh:
        urwid_alarm = main_loop.set_alarm_in(refresh_duration, refresh)


main_loop = urwid.MainLoop(layout, palette=palette if use_palette else [], unhandled_input=handle_input)
urwid_alarm = None


def run():
    global urwid_alarm
    global auto_refresh

    # 当前是否为交易时间
    # 交易时间为非节假日的周一至周五 9:30-11:30  13:00-15:00
    now = datetime.now()
    time_str = now.strftime('%H:%M')
    if not ((calendar.is_workday(now) and 1 <= now.isoweekday() <= 5) and ('09:15' <= time_str <= '11:30' or '13:00' <= time_str <= '15:05')):
        auto_refresh = False

    urwid_alarm = main_loop.set_alarm_in(0, refresh)
    main_loop.run()


if __name__ == '__main__':
    run()
