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
from rich.style import Style
from plyer import notification

# 是否开启自动刷新(非交易时间默认关闭，可手动开启)
auto_refresh = True
# 是否启用调色板(彩色输出)
use_palette = False
# 自动刷新间隔(s)(接口的数据更新频率为3s)
refresh_duration = 3
# 是否启用股票异动监控(快速拉升/快速下跌)
enable_price_monitor = True
# 异动监控的阈值(指定时间内涨跌幅超过阈值则触发)[时间(s), 涨跌幅(%)]
monitor_threshold = [30, 2]
# 股票代码
tickers = [
    'sh000001', # 上证指数
    'sh510980', # 上证综合ETF
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
    '600518', # 康美药业
    '002547', # 春兴精工
    '002195', # 岩山科技
    '002526', # 山东矿机
    '600999', # 招商证券
    '600030', # 中信证券
]


# 终端基础样式配置
palette = [
    ('titlebar', 'light blue, bold', ''),
    ('refresh button', 'dark green, bold', ''),
    ('auto_refresh button', 'dark cyan', ''),
    ('quit button', 'dark red', ''),
    ('page button', 'dark blue', ''),
    ('palette button', 'dark magenta', ''),
    ('select button', 'dark cyan', ''),
    ('price monitor button', 'dark green', ''),
    ('fluctuation monitor button', 'dark red', ''),
    ('cancel monitor button', 'dark red', ''),
    ('1m', 'bold', ''),
]

# 默认菜单
default_menu = [
    u'立即刷新(', ('refresh button', u'R/r'), ') | ',
    u'自动刷新(', ('auto_refresh button', u'A/a'), ') | ',
    u'翻页(', ('page button', u'PgUp/PgDn/↑/↓'), ') | ',
    u'彩色显示(', ('palette button', u'C/c'), ') | ',
    u'选择(', ('select button', u'S/s'), ') | ',
    u'退出进程(', ('quit button', u'Q/q'), ')',
]
# 二级菜单
secondary_menu = [
    u'返回(', ('esc button', u'Esc'), ') | ',
    u'翻页(', ('page button', u'PgUp/PgDn/↑/↓'), ') | ',
    u'切换股票(', ('select button', u'←/→'), ') | ',
    u'价格监控(', ('price monitor button', u'P/p'), ') | ',
    u'涨跌幅监控(', ('fluctuation monitor button', u'F/f'), ') | ',
    u'取消监控(', ('cancel monitor button', u'M/m'), ') | ',
    u'退出进程(', ('quit button', u'Q/q'), ')',
]

# 数据刷新定时器
urwid_alarm = None
# 顶部文本容器
header_text = urwid.Text(u'实时数据')
header = urwid.AttrMap(header_text, 'titlebar')
# 数据展示容器
quote_text = urwid.Text(u'按下 (R/r) 以获取数据...')
quote_filler = urwid.Filler(quote_text, valign='top', top=1, bottom=1)
quote_box = urwid.Scrollable(quote_filler)
# 底部菜单容器
menu = urwid.Text(default_menu)
# 底部输入框容器
footer_input = urwid.Edit(u'')
# 布局容器
layout = urwid.Frame(header=header, body=quote_box, footer=menu)

# 上一次请求的时间
last_request_time = ''
# 上一次请求的股价数据
last_price = {}
# 当前股票列表(之所以不使用全局变量tickers，是因为在刷新数据时，结果和tickers可能不一致)
stock_list = []
# 当前菜单状态 main_menu/secondary_menu/price_monitor_menu/fluctuation_monitor_menu
menu_status = 'main_menu'
# 当前选择的股票
current_selected_stock = ''
# 股票监控数据(用来计算涨跌幅异动){股票代码: [stock_data, stock_data, ...]}
price_monitor_data = {}
# 股票异动数据(用来显示的数据){股票代码: [stock, fluctuation, time]}
fluctuation_monitor_data = {}
# 用户自定义监控数据{股票代码: [monitor_price, monitor_fluctuation]} 当价格或涨跌幅跨过设置的值时触发
custom_monitor_data = {}
# 已触发的自定义监控数据(用来显示的数据){股票代码: [stock, price, fluctuation, time]}
custom_monitor_triggered_data = {}


"""
构建ansi调色板
30-37: 前景色
40-47: 背景色
可单独存在，也可组合使用
eg: 
31m: 红色前景 ('31m', 'dark red', '')
42m: 绿色背景 ('42m', '', 'dark green')
31;42m: 红色前景 + 绿色背景 ('31;42m', 'dark red', 'dark green')
"""
def build_ansi_palette():
    color_map = {
        '30': 'black',
        '31': 'dark red',
        '32': 'dark green',
        '33': 'yellow',
        '34': 'dark blue',
        '35': 'dark magenta',
        '36': 'dark cyan',
        '37': 'white',
        '40': 'black',
        '41': 'dark red',
        '42': 'dark green',
        '43': 'brown',
        '44': 'dark blue',
        '45': 'dark magenta',
        '46': 'dark cyan',
        '47': 'light gray',
    }
    ansi_palette = []
    for i in range(30, 38):
        ansi_palette.append((f'{i}m', color_map[str(i)], ''))  # 前景色
    for i in range(40, 48):
        ansi_palette.append((f'{i}m', '', color_map[str(i)])) # 背景色
    # 组合出所有可能的前景色和背景色
    for i in range(30, 38):
        for j in range(40, 48):
            ansi_palette.append((f'{i};{j}m', color_map[str(i)], color_map[str(j)]))
    return ansi_palette


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
    global last_request_time

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
    
    last_request_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    return result

# 获取更新表格
def get_update_table(need_update=True):
    global last_price
    global stock_list


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
    table.add_column("成交额(万)", justify='center')
    table.add_column("时间", justify='center')
    table.add_column("监控价格", justify='center')
    table.add_column("监控涨跌幅", justify='center')

    temp_last_price = last_price.copy()
    tickers_data = []
    if need_update:
        tickers_data = get_price(tickers)
    else:
        tickers_data = last_price
    temp_stock_list = []
    for ticker, data in tickers_data.items():
        try:
            # 股票波动值
            diff = 0.0
            if last_price.get(ticker) is not None:
                diff = float(data[3]) - float(last_price[ticker][3])

            color = 'red' if float(data[3]) - float(data[2]) > 0 else 'green' if float(data[3]) - float(data[2]) < 0 else None
            bg_color = 'blue' if ticker == current_selected_stock and use_palette is True else None
            pre_text = '● ' if ticker == current_selected_stock and menu_status in ['secondary_menu', 'price_monitor_menu', 'fluctuation_monitor_menu'] and use_palette is False else ''
            
            custom_monitor_price = ''
            custom_monitor_fluctuation = ''
            
            if custom_monitor_data.get(ticker) is not None:
                custom_monitor_price = str(custom_monitor_data[ticker][0]) if custom_monitor_data[ticker][0] is not None else ''
                custom_monitor_fluctuation = str(custom_monitor_data[ticker][1]) + '%' if custom_monitor_data[ticker][1] is not None else ''
            
            table.add_row(
                pre_text + data[0].strip() + ' ' + ticker,
                str(data[2]),
                str(data[1]),
                str(data[3]),
                ('+' if diff > 0 else '') + str(round(diff, 3)),
                ('+' if float(data[3]) - float(data[2]) > 0 else '') + str(round(float(data[3]) - float(data[2]), 2)),
                str(round((float(data[3]) - float(data[2])) / float(data[2]) * 100, 2)) + '%',
                str(data[4]) + ' · ' + str(round((float(data[4]) - float(data[2])) / float(data[2]) * 100, 2)) + '%',
                str(data[5]) + ' · ' + str(round((float(data[5]) - float(data[2])) / float(data[2]) * 100, 2)) + '%',
                str(round(float(data[8]) / 100, 2)),
                str(round(float(data[9]) / 10000, 2)),
                str(data[31]),
                custom_monitor_price,
                custom_monitor_fluctuation,
                style=Style(color=color, bgcolor=bg_color)
            )

            # 更新上一次的股价数据
            last_price[ticker] = data
            temp_stock_list.append(ticker)
        except Exception as e:
            continue
    # 更新监控数据
    update_monitor_data()
    # 更新自定义监控数据
    update_custom_monitor_data(temp_last_price, last_price)
    # 更新当前股票列表
    stock_list = temp_stock_list
    
    return table


# 监听键盘输入
def handle_input(key):
    global menu_status
    global urwid_alarm

    if key == 'R' or key == 'r': # 刷新
        if menu_status == 'main_menu':
            quote_text.set_text('获取数据中，请等待...')
            refresh(main_loop, '')

    elif key == 'Q' or key == 'q': # 退出
        if urwid_alarm is not None:
            main_loop.remove_alarm(urwid_alarm)
        
        quote_text.set_text('正在退出，请稍后...')
        main_loop.draw_screen()
        raise urwid.ExitMainLoop()

    elif key == 'A' or key == 'a': # 切换自动刷新
        global auto_refresh
        if menu_status == 'main_menu':
            auto_refresh = not auto_refresh
            if auto_refresh:
                urwid_alarm = main_loop.set_alarm_in(0, refresh)
            else:
                if urwid_alarm is not None:
                    main_loop.remove_alarm(urwid_alarm)
                urwid_alarm = None
                update_header()
                main_loop.draw_screen()

    elif key == 'C' or key == 'c': # 切换调色板
        global use_palette
        global palette
        if menu_status == 'main_menu':
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

    elif key == 'S' or key == 's': # 选择股票
        # 只有在主菜单时才能进入选择股票
        if menu_status == 'main_menu':
            menu_status = 'secondary_menu'
            menu.set_text(secondary_menu)
            main_loop.draw_screen()
            # 选中第一个股票
            switch_stock(True)

    elif key == 'esc': # 返回主菜单
        global current_selected_stock
        # 只有在二级菜单时才能返回主菜单
        if menu_status == 'secondary_menu':
            current_selected_stock = ''
            menu_status = 'main_menu'
            menu.set_text(default_menu)
            main_loop.draw_screen()
            refresh(main_loop, '')
        if menu_status == 'price_monitor_menu' or menu_status == 'fluctuation_monitor_menu':
            menu_status = 'secondary_menu'
            menu.set_text(secondary_menu)
            layout.set_footer(menu)
            layout.set_focus('body')
            main_loop.draw_screen()
            refresh(main_loop, '')

    elif key == 'left': # 上一个股票
        if menu_status == 'secondary_menu':
            switch_stock()

    elif key == 'right': # 下一个股票
        if menu_status == 'secondary_menu':
            switch_stock(True)

    elif key == 'P' or key == 'p': # 价格监控
        if menu_status == 'secondary_menu':
            menu_status = 'price_monitor_menu'
            footer_input.set_caption(u'价格监控 | 返回(Esc) | 确认(Enter) | 请输入要监控的价格: ')
            footer_input.set_edit_text(u'')
            footer_input.set_edit_pos(len(footer_input.get_edit_text()))
            layout.set_footer(footer_input)
            layout.set_focus('footer')
            main_loop.draw_screen()

    elif key == 'F' or key == 'f': # 涨跌幅监控
        if menu_status == 'secondary_menu':
            menu_status = 'fluctuation_monitor_menu'
            footer_input.set_caption(u'涨跌幅监控 | 返回(Esc) | 确认(Enter) | 请输入要监控的涨跌幅(%): ')
            footer_input.set_edit_text(u'')
            footer_input.set_edit_pos(len(footer_input.get_edit_text()))
            layout.set_footer(footer_input)
            layout.set_focus('footer')
            main_loop.draw_screen()

    elif key == 'M' or key == 'm': # 取消监控
        if menu_status == 'secondary_menu':
            if custom_monitor_data.get(current_selected_stock) is not None:
                custom_monitor_data.pop(current_selected_stock)
                update_header()
                main_loop.draw_screen()
                refresh(main_loop, '')

    elif key == 'enter': # 确认输入
        if menu_status == 'price_monitor_menu' or menu_status == 'fluctuation_monitor_menu':
            # 如果没有初始化，则初始化
            if custom_monitor_data.get(current_selected_stock) is None:
                custom_monitor_data[current_selected_stock] = [None, None]
            value = footer_input.get_edit_text()
            # 判断是否为数字
            result = re.compile(r'^-?\d+(\.\d+)?$').match(value)
            if value != '' and result is None:
                footer_input.set_edit_text(u'')
                return
            if menu_status == 'price_monitor_menu':
                custom_monitor_data[current_selected_stock][0] = float(value) if value != '' else None
                update_header()
            elif menu_status == 'fluctuation_monitor_menu':
                custom_monitor_data[current_selected_stock][1] = float(value) if value != '' else None
                update_header()
            # 返回二级菜单
            menu_status = 'secondary_menu'
            menu.set_text(secondary_menu)
            layout.set_footer(menu)
            layout.set_focus('body')
            main_loop.draw_screen()
            refresh(main_loop, '')

# 切换选中的股票
def switch_stock(next=False):
    global current_selected_stock
    global stock_list
    global last_price

    if next:
        if current_selected_stock == '':
            current_selected_stock = stock_list[0] if len(stock_list) > 0 else ''
        else:
            current_selected_stock = stock_list[(stock_list.index(current_selected_stock) + 1) % len(stock_list)]
    else:
        if current_selected_stock == '':
            current_selected_stock = stock_list[-1] if len(stock_list) > 0 else ''
        else:
            current_selected_stock = stock_list[(stock_list.index(current_selected_stock) - 1) % len(stock_list)]

    update_header()
    quote_box.set_scrollpos(stock_list.index(current_selected_stock))
    console = Console(record=True)
    table = get_update_table(False)

    with console.capture() as capture:
        console.print(table)
    quote_text.set_text(ansi_str_to_urwid(capture.get()))
    
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

    update_header()
    quote_text.set_text(ansi_str_to_urwid(capture.get()))
    
    main_loop.draw_screen()
    # 如果开启自动刷新，则继续刷新
    if auto_refresh:
        urwid_alarm = main_loop.set_alarm_in(refresh_duration, refresh)


# 更新顶部文本
def update_header():
    global auto_refresh
    global last_request_time
    global current_selected_stock

    header_text.set_text(u'实时数据 | 刷新间隔: {}s | 刷新于: {}'.format(refresh_duration, last_request_time))
    # 如果自动刷新关闭，则显示已暂停自动刷新
    if auto_refresh is False:
        header_text.set_text(header_text.get_text()[0] + u' | 已暂停自动刷新')
    # 如果当前有选中的股票，则显示选中的股票
    if current_selected_stock != '':
        header_text.set_text(header_text.get_text()[0] + u' | 当前选择: {}({})'.format(last_price[current_selected_stock][0], current_selected_stock))
    # 如果开启了股票异动监控，则显示异动信息
    if enable_price_monitor and len(fluctuation_monitor_data) > 0:
        fluctuation_text = ''
        for ticker, data in fluctuation_monitor_data.items():
            fluctuation_text += '{}({}): {}{}% | '.format(data[0], data[2], '+' if data[1] > 0 else '',round(data[1], 2))
        # 移除最后一个 |
        fluctuation_text = fluctuation_text[:-2]
        header_text.set_text(header_text.get_text()[0] + u'\n异动监控: {}'.format(fluctuation_text))
    
    main_loop.draw_screen()


# 更新股票监控数据
def update_monitor_data():
    global price_monitor_data
    global last_price
    global fluctuation_monitor_data

    for ticker, data in last_price.items():
        if price_monitor_data.get(ticker) is None:
            price_monitor_data[ticker] = []
        
        # price_monitor_data中最后一条数据的时间不能大于等于当前数据的时间
        if len(price_monitor_data[ticker]) > 0 and price_monitor_data[ticker][-1][31] >= data[31]:
            continue
        # 添加新数据
        price_monitor_data[ticker].append(data)
        # 价格最大的数据
        max_price_data = max(price_monitor_data[ticker], key=lambda x: x[3])
        # 价格最小的数据
        min_price_data = min(price_monitor_data[ticker], key=lambda x: x[3])
        fluctuation = 0.0
        # 判断数据先后，计算涨跌幅，[31]为时间
        if max_price_data[31] > min_price_data[31]:
            diff = float(max_price_data[3]) - float(min_price_data[3])
            fluctuation = diff / float(min_price_data[2]) * 100
        else:
            diff = float(min_price_data[3]) - float(max_price_data[3])
            fluctuation = diff / float(max_price_data[2]) * 100
        # 如果涨跌幅超过阈值，则触发异动
        if abs(fluctuation) >= monitor_threshold[1]:
            fluctuation_monitor_data[ticker] = [max_price_data[0], fluctuation, max_price_data[31]]

        # 清除过期超过阈值时间的数据
        now = datetime.now()
        temp_price_monitor_data = price_monitor_data[ticker].copy()
        for data in temp_price_monitor_data:
            if (now - datetime.strptime(data[31], '%H:%M:%S')).seconds > monitor_threshold[0]:
                price_monitor_data[ticker].remove(data)
        
    # 清除过期超过3分钟fluctuation_monitor_data数据
    now = datetime.now()
    temp_fluctuation_monitor_data = fluctuation_monitor_data.copy()
    for ticker, data in temp_fluctuation_monitor_data.items():
        if (now - datetime.strptime(data[2], '%H:%M:%S')).seconds > 3 * 60:
            fluctuation_monitor_data.pop(ticker)



# 更新自定义股票监控数据，当价格或涨跌幅跨过(上升和下降都算)设置的值时触发
def update_custom_monitor_data(old_data, new_data):
    global custom_monitor_triggered_data

    for ticker, data in custom_monitor_data.items():
        # 如果没有监控价格或涨跌幅，则跳过
        if data[0] is None and data[1] is None:
            continue
        # 如果没有初始化，则初始化
        if custom_monitor_triggered_data.get(ticker) is None:
            custom_monitor_triggered_data[ticker] = []
        
        old_price = old_data[ticker][3]
        new_price = new_data[ticker][3]
        old_fluctuation = (float(old_data[ticker][3]) - float(old_data[ticker][2])) / float(old_data[ticker][2]) * 100
        new_fluctuation = (float(new_data[ticker][3]) - float(new_data[ticker][2])) / float(new_data[ticker][2]) * 100
        
        # 如果价格监控触发
        if data[0] is not None and (old_price < data[0] <= new_price or old_price > data[0] >= new_price):
            send_notification('价格监控', f'{new_data[ticker][0]}({ticker}): {round(float(new_data[ticker][3]), 2)}')
        # 如果涨跌幅监控触发
        if data[1] is not None and (old_fluctuation < data[1] <= new_fluctuation or old_fluctuation > data[1] >= new_fluctuation):
            send_notification('涨跌幅监控', f'{new_data[ticker][0]}({ticker}): {round(new_fluctuation, 2)}%')


# 发送通知
def send_notification(title, message):
    notification.notify(
        title=title,
        message=message,
        app_name='stock_terminal',
        timeout=10
    )

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


# 构建ansi调色板
palette = palette + build_ansi_palette()
# 创建主循环
main_loop = urwid.MainLoop(layout, palette=palette if use_palette else [], unhandled_input=handle_input)
# 开始运行
run()
