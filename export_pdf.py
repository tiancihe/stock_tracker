import os
import tempfile
from datetime import datetime
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.font_manager as fm
from matplotlib.backends.backend_pdf import PdfPages

plt.rcParams["axes.unicode_minus"] = False

_FONT_PROPS = fm.FontProperties(fname="C:\\Windows\\Fonts\\simhei.ttf")


def _font(size=10):
    return {"fontproperties": _FONT_PROPS, "size": size} if _FONT_PROPS else {"size": size}


def _plot_price(data, ax1, ax2):
    dates = [datetime.strptime(r["date"], "%Y%m%d") for r in data]
    closes = [r["close"] for r in data]
    volumes = [r["volume"] / 1e4 for r in data]
    ax1.plot(dates, closes, "b-", linewidth=1.5)
    ax1.set_ylabel("收盘价", **_font(9))
    ax1.grid(True, alpha=0.3)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
    colors = ["g" if i >= 0 else "r" for i in range(len(closes))]
    ax2.bar(dates, volumes, color=colors, alpha=0.6)
    ax2.set_ylabel("成交量(万手)", **_font(9))
    ax2.grid(True, alpha=0.3)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))


def _plot_fund_flow(data, ax):
    dates = [datetime.strptime(r["date"], "%Y%m%d") for r in data]
    super_large = [r["super_large_net_flow"] / 1e8 for r in data]
    large = [r["large_net_flow"] / 1e8 for r in data]
    medium = [r["medium_net_flow"] / 1e8 for r in data]
    small = [r["small_net_flow"] / 1e8 for r in data]
    x = range(len(dates))
    width = 0.2
    ax.bar([i - 1.5 * width for i in x], super_large, width, label="超大单", alpha=0.7)
    ax.bar([i - 0.5 * width for i in x], large, width, label="大单", alpha=0.7)
    ax.bar([i + 0.5 * width for i in x], medium, width, label="中单", alpha=0.7)
    ax.bar([i + 1.5 * width for i in x], small, width, label="小单", alpha=0.7)
    ax.set_ylabel("净流入(亿元)", **_font(9))
    ax.axhline(y=0, color="k", linewidth=0.5)
    ax.legend(prop=_FONT_PROPS if _FONT_PROPS else {})
    ax.set_xticks(list(x))
    ax.set_xticklabels([d.strftime("%m-%d") for d in dates], rotation=45, ha="right", **_font(8))
    ax.grid(True, alpha=0.3)


def _plot_intraday(data, ax):
    dates = [datetime.strptime(r["date"], "%Y%m%d") for r in data]
    morning_amt = [r["morning_amount"] / 1e8 for r in data]
    afternoon_amt = [r["afternoon_amount"] / 1e8 for r in data]
    x = range(len(dates))
    width = 0.35
    ax.bar([i - width / 2 for i in x], morning_amt, width, label="上午成交额", alpha=0.7, color="orange")
    ax.bar([i + width / 2 for i in x], afternoon_amt, width, label="下午成交额", alpha=0.7, color="steelblue")
    ax.set_ylabel("成交额(亿元)", **_font(9))
    ax.legend(prop=_FONT_PROPS if _FONT_PROPS else {})
    ax.set_xticks(list(x))
    ax.set_xticklabels([d.strftime("%m-%d") for d in dates], rotation=45, ha="right", **_font(8))
    ax.grid(True, alpha=0.3)


def _plot_margin(data, ax1, ax2):
    dates = [datetime.strptime(r["date"], "%Y%m%d") for r in data]
    balance = [r["margin_balance"] / 1e8 for r in data]
    buy = [r["margin_buy"] / 1e8 for r in data]
    sell = [r["margin_sell"] / 1e8 for r in data]
    ax1.plot(dates, balance, "b-", linewidth=1.5)
    ax1.set_ylabel("融资余额(亿元)", **_font(9))
    ax1.grid(True, alpha=0.3)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
    ax2.plot(dates, buy, "g-", label="融资买入", linewidth=1)
    ax2.plot(dates, sell, "r-", label="融资偿还", linewidth=1)
    ax2.set_ylabel("金额(亿元)", **_font(9))
    ax2.legend(prop=_FONT_PROPS if _FONT_PROPS else {})
    ax2.grid(True, alpha=0.3)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))


def generate_pdf(daily_data, fund_flow_data, intraday_data, margin_data, stock_name, start_date, end_date):
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    pdf_path = tmp.name
    tmp.close()

    with PdfPages(pdf_path) as pdf:
        if daily_data:
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 4.5), gridspec_kw={"height_ratios": [3, 1]})
            fig.suptitle(f"{stock_name} - 价格走势", **_font(12))
            _plot_price(daily_data, ax1, ax2)
            plt.tight_layout()
            pdf.savefig(fig, dpi=150)
            plt.close()

        if fund_flow_data:
            fig, ax = plt.subplots(figsize=(11, 4))
            fig.suptitle(f"{stock_name} - 资金流向", **_font(12))
            _plot_fund_flow(fund_flow_data, ax)
            plt.tight_layout()
            pdf.savefig(fig, dpi=150)
            plt.close()

        if intraday_data:
            fig, ax = plt.subplots(figsize=(11, 4))
            fig.suptitle(f"{stock_name} - 上下午成交额对比", **_font(12))
            _plot_intraday(intraday_data, ax)
            plt.tight_layout()
            pdf.savefig(fig, dpi=150)
            plt.close()

        if margin_data:
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 4.5))
            fig.suptitle(f"{stock_name} - 融资融券数据", **_font(12))
            _plot_margin(margin_data, ax1, ax2)
            plt.tight_layout()
            pdf.savefig(fig, dpi=150)
            plt.close()

        if not any([daily_data, fund_flow_data, intraday_data, margin_data]):
            fig, ax = plt.subplots(figsize=(8, 3))
            ax.text(0.5, 0.5, "暂无数据", transform=ax.transAxes, ha="center", va="center", fontsize=14)
            ax.axis("off")
            pdf.savefig(fig, dpi=150)
            plt.close()

    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()
    os.unlink(pdf_path)
    return pdf_bytes
