import flet as ft
import sqlite3
import calendar
import os
from datetime import datetime

# 设置日历逻辑：周日为一周开始
calendar.setfirstweekday(calendar.SUNDAY)

def init_db():
    db_path = "accounting.db"
    # 自动识别环境：安卓使用私有目录，电脑使用当前目录
    if os.environ.get("FLET_PLATFORM") == "android" or "ANDROID_DATA" in os.environ:
        data_dir = os.environ.get("FLET_APP_STORAGE_DATA", os.getcwd())
        db_path = os.path.join(data_dir, "accounting.db")

    conn = sqlite3.connect(db_path, check_same_thread=False)
    c = conn.cursor()
    # 核心表结构：含件数、油费、备注
    c.execute('''
        CREATE TABLE IF NOT EXISTS records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            record_date TEXT,
            car_number INTEGER,
            cost REAL,
            price REAL,
            labor REAL,
            misc REAL,
            quantity INTEGER DEFAULT 0,
            fuel REAL DEFAULT 0,
            income REAL,
            note TEXT,
            UNIQUE(record_date, car_number)
        )
    ''')
    # 数据库字段自动补齐逻辑1
    columns = [row[1] for row in c.execute("PRAGMA table_info(records)").fetchall()]
    for col, dtype in [("quantity", "INTEGER DEFAULT 0"), ("fuel", "REAL DEFAULT 0"), ("note", "TEXT")]:
        if col not in columns:
            c.execute(f"ALTER TABLE records ADD COLUMN {col} {dtype}")
    conn.commit()
    return conn

def main(page: ft.Page):
    page.title = "记账本"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.theme = ft.Theme(color_scheme_seed=ft.Colors.DEEP_ORANGE)
    page.padding = 0
    
    # 强制页面语言环境为中文
    page.locale_configuration = ft.LocaleConfiguration(
        current_locale=ft.Locale("zh", "CN"),
        supported_locales=[ft.Locale("zh", "CN")],
    )

    conn = init_db()
    state = {
        "selected_date": datetime.now().strftime("%Y-%m-%d"),
        "cur_year": datetime.now().year,
        "cur_month": datetime.now().month
    }

    # --- 统计逻辑 ---
    def get_stats():
        c = conn.cursor()
        y_start = f"{state['selected_date'][:4]}-01-01"
        c.execute("SELECT SUM(income), COUNT(*) FROM records WHERE record_date >= ? AND record_date <= ?", (y_start, state['selected_date']))
        y_res = c.fetchone()
        m_prefix = f"{state['cur_year']}-{state['cur_month']:02d}"
        c.execute("SELECT SUM(income) FROM records WHERE record_date LIKE ?", (f"{m_prefix}%",))
        m_income = c.fetchone()[0] or 0.0
        return y_res[0] or 0.0, y_res[1] or 0, m_income

    # 【修复1】移除了默认白色，将在 load_flow 中动态计算颜色
    year_income_text = ft.Text("年度总盈利: ¥ 0.00", weight="bold", size=16)
    
    # 【修复2】移除了默认 deeporange 色，将在 build_calendar 中动态计算颜色
    month_total_text = ft.Text("¥ 0.00", size=26, weight="bold")

    # --- 流水卡片工厂 ---
    def create_car_card(car_num, price="", cost="", labor="", misc="", quantity="", fuel="", income=0.0, note="", total_count=0):
        qty_f = ft.TextField(label="件数", value=str(quantity) if quantity else "", expand=1, keyboard_type="number")
        cost_f = ft.TextField(label="进价", value=str(cost) if cost else "", expand=1, keyboard_type="number")
        price_f = ft.TextField(label="卖价", value=str(price) if price else "", expand=1, keyboard_type="number")
        labor_f = ft.TextField(label="工费", value=str(labor) if labor else "", expand=1, keyboard_type="number")
        fuel_f = ft.TextField(label="油费", value=str(fuel) if fuel else "", expand=1, keyboard_type="number")
        misc_f = ft.TextField(label="杂费", value=str(misc) if misc else "", expand=1, keyboard_type="number")
        note_f = ft.TextField(label="备注", value=str(note) if note else "", multiline=True, expand=1)
        income_t = ft.Text(f"{income:.2f}", size=20, weight="bold", color="red" if income >= 0 else "green")

        def calc_income(e):
            try:
                res = float(price_f.value or 0) - float(cost_f.value or 0) - float(labor_f.value or 0) - float(fuel_f.value or 0) - float(misc_f.value or 0)
                income_t.value = f"{res:.2f}"
                income_t.color = "red" if res >= 0 else "green"
                page.update()
            except: pass

        for f in [price_f, cost_f, labor_f, fuel_f, misc_f]:
            f.on_change = calc_income

        def delete_click(e):
            c = conn.cursor()
            c.execute("DELETE FROM records WHERE record_date = ? AND car_number = ?", (state["selected_date"], car_num))
            conn.commit()
            load_flow()

        return ft.Card(
            content=ft.Container(
                padding=12,
                content=ft.Column([
                    # 标题行
                    ft.Row([
                        ft.Text(f"第 {car_num} 车 (总{total_count}车)", weight="bold"),
                        ft.IconButton(ft.Icons.DELETE_OUTLINE, icon_color="red400", on_click=delete_click)
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Row([qty_f, cost_f, price_f], spacing=8),
                    ft.Row([labor_f, fuel_f, misc_f], spacing=8),
                    ft.Row([note_f, ft.Container(expand=1, content=ft.Column([ft.Text("本车利润", size=11, color="grey700"), income_t], horizontal_alignment=ft.CrossAxisAlignment.CENTER))], spacing=10),
                ], spacing=12)
            ),
            data={"price": price_f, "cost": cost_f, "labor": labor_f, "misc": misc_f, "qty": qty_f, "fuel": fuel_f, "note": note_f, "income": income_t, "num": car_num}
        )

    car_list_column = ft.ListView(expand=True, spacing=10, padding=15)
    date_label = ft.Text(state["selected_date"], size=18, weight="bold")

    def load_flow():
        car_list_column.controls.clear()
        y_inc, y_cars, _ = get_stats()
        year_income_text.value = f"年度总盈利 ({state['selected_date'][:4]}年): ¥ {y_inc:.2f}"
        
        # 【修复3】年度总利润颜色判断：盈利=红，亏损=绿
        year_income_text.color = "red" if y_inc >= 0 else "green"
        
        c = conn.cursor()
        c.execute("SELECT car_number, price, cost, labor, misc, quantity, fuel, income, note FROM records WHERE record_date = ? ORDER BY car_number ASC", (state["selected_date"],))
        rows = c.fetchall()
        base_count = y_cars - len(rows)
        for i, r in enumerate(rows):
            car_list_column.controls.append(create_car_card(r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8], base_count + i + 1))
        page.update()

    cal_grid = ft.GridView(runs_count=7, spacing=5, run_spacing=5, expand=True)
    month_txt = ft.Text("", size=20, weight="bold")

    def build_calendar():
        cal_grid.controls.clear()
        for w in ["日", "一", "二", "三", "四", "五", "六"]:
            cal_grid.controls.append(ft.Row([ft.Text(w, size=12, weight="bold")], alignment=ft.MainAxisAlignment.CENTER))
        c = conn.cursor()
        prefix = f"{state['cur_year']}-{state['cur_month']:02d}"
        c.execute("SELECT record_date, SUM(income) FROM records WHERE record_date LIKE ? GROUP BY record_date", (f"{prefix}%",))
        data = {row[0]: row[1] for row in c.fetchall()}
        month_days = calendar.monthcalendar(state['cur_year'], state['cur_month'])
        for week in month_days:
            for day in week:
                if day == 0:
                    cal_grid.controls.append(ft.Container())
                else:
                    d_str = f"{prefix}-{day:02d}"
                    income = data.get(d_str, 0)
                    cal_grid.controls.append(
                        ft.Container(
                            content=ft.Column([
                                ft.Text(str(day), weight="bold" if d_str == datetime.now().strftime("%Y-%m-%d") else None),
                                ft.Text(f"{income:.0f}" if income != 0 else "", size=9, color="red" if income > 0 else "green")
                            ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2),
                            bgcolor="white", border_radius=8, on_click=lambda _, ds=d_str: jump_to_date(ds)
                        )
                    )
        _, _, m_total = get_stats()
        month_txt.value = f"{state['cur_year']}年{state['cur_month']}月"
        month_total_text.value = f"¥ {m_total:.2f}"
        
        # 【修复4】月度总利润颜色判断：盈利=红，亏损=绿
        month_total_text.color = "red" if m_total >= 0 else "green"
        
        page.update()

    def jump_to_date(ds):
        state["selected_date"] = ds; date_label.value = ds
        page.navigation_bar.selected_index = 0; load_flow(); update_view(0)

    date_picker = ft.DatePicker(
        locale="zh",
        on_change=lambda e: (state.update({"selected_date": e.control.value.strftime("%Y-%m-%d")}), load_flow()) if e.control.value else None
    )
    page.overlay.append(date_picker)

    # --- 界面主体 ---
    flow_view = ft.Column([
        # 【修复5】将顶部空白栏高度改为 44 像素，与下面的标题栏对齐
        ft.Container(height=44, bgcolor=ft.Colors.TRANSPARENT), 
        ft.Container(content=ft.Row([year_income_text], alignment=ft.MainAxisAlignment.CENTER), bgcolor=ft.Colors.DEEP_ORANGE_ACCENT, padding=12),
        ft.Container(padding=10, bgcolor="white", content=ft.Row([
            ft.Row([ft.Icon(ft.Icons.CALENDAR_MONTH, size=20), date_label]),
            ft.IconButton(ft.Icons.EDIT_CALENDAR, on_click=lambda _: setattr(date_picker, "open", True) or page.update())
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)),
        car_list_column,
        ft.Container(padding=15, content=ft.Row([
            ft.ElevatedButton("增车", icon=ft.Icons.ADD, expand=1, on_click=lambda _: add_new_car()),
            ft.ElevatedButton("保存", icon=ft.Icons.SAVE, expand=1, bgcolor="deeporange", color="white", on_click=lambda _: save_all())
        ]))
    ], expand=True)

    def add_new_car():
        _, y_cars = get_year_stats()
        cur_cards = len([c for c in car_list_column.controls if isinstance(c, ft.Card)])
        car_list_column.controls.append(create_car_card(cur_cards + 1, total_count=y_cars + 1))
        page.update()

    def save_all():
        c = conn.cursor()
        for card in car_list_column.controls:
            if isinstance(card, ft.Card):
                d = card.data
                c.execute("""INSERT OR REPLACE INTO records 
                             (record_date, car_number, price, cost, labor, misc, quantity, fuel, income, note) 
                             VALUES (?,?,?,?,?,?,?,?,?,?)""",
                          (state["selected_date"], d["num"], float(d["price"].value or 0), float(d["cost"].value or 0),
                           float(d["labor"].value or 0), float(d["misc"].value or 0), int(d["qty"].value or 0),
                           float(d["fuel"].value or 0), float(d["income"].value), d["note"].value))
        conn.commit()
        page.snack_bar = ft.SnackBar(ft.Text("✅ 数据已保存成功")); page.snack_bar.open = True; load_flow()

    board_view = ft.Column([
        # 【修复6】看板页顶部空白也统一改为 44 像素
        ft.Container(height=44, bgcolor=ft.Colors.TRANSPARENT), 
        ft.Container(padding=15, content=ft.Row([
            ft.IconButton(ft.Icons.ARROW_BACK_IOS, on_click=lambda _: change_month(-1)),
            month_txt,
            ft.IconButton(ft.Icons.ARROW_FORWARD_IOS, on_click=lambda _: change_month(1)),
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)),
        ft.Container(content=cal_grid, expand=True, padding=10),
        ft.Container(
            padding=20, bgcolor="white", border_radius=ft.border_radius.only(top_left=25, top_right=25),
            content=ft.Column([
                ft.Text("本月累计盈利汇总", size=14, color="grey600"),
                ft.Row([month_total_text], alignment=ft.MainAxisAlignment.CENTER)
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=5)
        )
    ], expand=True, visible=False)

    def change_month(delta):
        state["cur_month"] += delta
        if state["cur_month"] > 12: state["cur_month"] = 1; state["cur_year"] += 1
        elif state["cur_month"] < 1: state["cur_month"] = 12; state["cur_year"] -= 1
        build_calendar()

    def update_view(idx):
        flow_view.visible = (idx == 0); board_view.visible = (idx == 1)
        if idx == 1: build_calendar()
        page.update()

    page.navigation_bar = ft.NavigationBar(
        destinations=[ft.NavigationBarDestination(icon=ft.Icons.LIST, label="流水"), ft.NavigationBarDestination(icon=ft.Icons.GRID_VIEW, label="看板")],
        on_change=lambda e: update_view(e.control.selected_index)
    )

    page.add(ft.Stack([flow_view, board_view]))
    load_flow()

if __name__ == "__main__":
    ft.app(target=main)
