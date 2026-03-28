import flet as ft
import sqlite3
import calendar
import os
from datetime import datetime


# --- 数据库初始化 (适配安卓/电脑路径) ---
def init_db():
    db_path = "accounting.db"
    if os.environ.get("FLET_PLATFORM") == "android" or "ANDROID_DATA" in os.environ:
        data_dir = os.environ.get("FLET_APP_STORAGE_DATA", os.getcwd())
        db_path = os.path.join(data_dir, "accounting.db")

    conn = sqlite3.connect(db_path, check_same_thread=False)
    c = conn.cursor()
    c.execute('''
              CREATE TABLE IF NOT EXISTS records
              (
                  id
                  INTEGER
                  PRIMARY
                  KEY
                  AUTOINCREMENT,
                  record_date
                  TEXT,
                  car_number
                  INTEGER,
                  cost
                  REAL,
                  price
                  REAL,
                  labor
                  REAL,
                  transport
                  REAL,
                  misc
                  REAL,
                  income
                  REAL,
                  note
                  TEXT,
                  UNIQUE
              (
                  record_date,
                  car_number
              )
                  )
              ''')
    try:
        c.execute("ALTER TABLE records ADD COLUMN note TEXT")
    except:
        pass
    conn.commit()
    return conn


def main(page: ft.Page):
    page.title = "我的记账本"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.theme = ft.Theme(color_scheme_seed=ft.Colors.DEEP_ORANGE)
    page.bgcolor = ft.Colors.GREY_100
    page.padding = 0

    conn = init_db()

    state = {
        "cur_year": datetime.now().year,
        "cur_month": datetime.now().month,
        "selected_date": datetime.now().strftime("%Y-%m-%d")
    }

    # --- 1. 流水页组件 ---
    class CarCard(ft.Card):
        def __init__(self, car_num, price="", cost="", labor="", misc="", income=0.0, note=""):
            super().__init__()
            self.car_num = car_num
            self.elevation = 2
            self.price_ref = ft.TextField(label="卖价", value=str(price) if price else "", expand=1,
                                          keyboard_type=ft.KeyboardType.NUMBER, on_change=self.calc)
            self.cost_ref = ft.TextField(label="进价", value=str(cost) if cost else "", expand=1,
                                         keyboard_type=ft.KeyboardType.NUMBER, on_change=self.calc)
            self.labor_ref = ft.TextField(label="工费", value=str(labor) if labor else "", expand=1,
                                          keyboard_type=ft.KeyboardType.NUMBER, on_change=self.calc)
            self.misc_ref = ft.TextField(label="杂费", value=str(misc) if misc else "", expand=1,
                                         keyboard_type=ft.KeyboardType.NUMBER, on_change=self.calc)
            self.note_ref = ft.TextField(label="备注", value=str(note) if note else "", multiline=True, min_lines=1)
            self.income_txt = ft.Text(f"{income:.2f}", size=18, weight=ft.FontWeight.BOLD,
                                      color=ft.Colors.RED_600 if income >= 0 else ft.Colors.GREEN_600)

            self.content = ft.Container(padding=15, content=ft.Column([
                ft.Row([
                    ft.Row([ft.Icon(ft.Icons.LOCAL_SHIPPING, color=ft.Colors.DEEP_ORANGE),
                            ft.Text(f"第 {self.car_num} 车", weight=ft.FontWeight.BOLD)]),
                    ft.IconButton(ft.Icons.DELETE_OUTLINE, icon_color=ft.Colors.RED_400, on_click=self.delete_me)
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Row([self.price_ref, self.cost_ref], spacing=10),
                ft.Row([self.labor_ref, self.misc_ref], spacing=10),
                self.note_ref,
                ft.Divider(height=1, color=ft.Colors.BLACK12),
                ft.Row([ft.Text("本车利润:"), self.income_txt], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
            ]))

        def calc(self, e=None):
            try:
                res = float(self.price_ref.value or 0) - float(self.cost_ref.value or 0) - float(
                    self.labor_ref.value or 0) - float(self.misc_ref.value or 0)
                self.income_txt.value = f"{res:.2f}"
                self.income_txt.color = ft.Colors.RED_600 if res >= 0 else ft.Colors.GREEN_600
                self.update()
            except:
                pass

        def delete_me(self, e):
            c = conn.cursor()
            c.execute("DELETE FROM records WHERE record_date = ? AND car_number = ?",
                      (state["selected_date"], self.car_num))
            conn.commit()
            car_list_column.controls.remove(self)
            page.update()

    car_list_column = ft.ListView(expand=True, spacing=10, padding=15)
    date_label = ft.Text(state["selected_date"], size=18, weight=ft.FontWeight.BOLD)

    def load_flow():
        car_list_column.controls.clear()
        c = conn.cursor()
        c.execute(
            "SELECT car_number, price, cost, labor, misc, income, note FROM records WHERE record_date = ? ORDER BY car_number ASC",
            (state["selected_date"],))
        for r in c.fetchall():
            car_list_column.controls.append(CarCard(r[0], r[1], r[2], r[3], r[4], r[5], r[6]))
        page.update()

    # --- 2. 看板页组件 ---
    cal_grid = ft.GridView(runs_count=7, spacing=5, run_spacing=5, expand=True)
    month_txt = ft.Text("", size=20, weight=ft.FontWeight.BOLD)
    total_month_income = ft.Text("¥ 0.00", size=26, weight=ft.FontWeight.BOLD, color=ft.Colors.DEEP_ORANGE)

    def build_calendar():
        cal_grid.controls.clear()
        # 星期头
        for w in ["一", "二", "三", "四", "五", "六", "日"]:
            cal_grid.controls.append(ft.Row([ft.Text(w, size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.GREY_500)],
                                            alignment=ft.MainAxisAlignment.CENTER))

        c = conn.cursor()
        prefix = f"{state['cur_year']}-{state['cur_month']:02d}"
        c.execute("SELECT record_date, SUM(income) FROM records WHERE record_date LIKE ? GROUP BY record_date",
                  (f"{prefix}%",))
        data = {row[0]: row[1] for row in c.fetchall()}

        month_days = calendar.monthcalendar(state['cur_year'], state['cur_month'])
        month_sum = 0
        for week in month_days:
            for day in week:
                if day == 0:
                    cal_grid.controls.append(ft.Container())
                else:
                    d_str = f"{prefix}-{day:02d}"
                    income = data.get(d_str, 0)
                    month_sum += income
                    is_today = d_str == datetime.now().strftime("%Y-%m-%d")

                    cal_grid.controls.append(
                        ft.Container(
                            content=ft.Column([
                                ft.Text(str(day), size=14, weight=ft.FontWeight.BOLD if is_today else None),
                                ft.Text(f"{income:.0f}" if income != 0 else "", size=9,
                                        color=ft.Colors.RED_600 if income > 0 else ft.Colors.GREEN_600)
                            ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                spacing=2),
                            bgcolor=ft.Colors.WHITE,
                            border_radius=8,
                            on_click=lambda _, ds=d_str: jump_to_date(ds)  # 这里触发跳转
                        )
                    )
        month_txt.value = f"{state['cur_year']}年 {state['cur_month']}月"
        total_month_income.value = f"¥ {month_sum:.2f}"
        page.update()

    # --- 跳转核心逻辑 ---
    def jump_to_date(ds):
        state["selected_date"] = ds
        date_label.value = ds
        # 切换导航栏索引到 0 (流水页)
        page.navigation_bar.selected_index = 0
        load_flow()
        update_view(0)

    # --- 布局与逻辑 ---
    date_picker = ft.DatePicker(
        on_change=lambda e: (state.update({"selected_date": e.control.value.strftime("%Y-%m-%d")}),
                             setattr(date_label, "value", state["selected_date"]),
                             load_flow()) if e.control.value else None)
    page.overlay.append(date_picker)

    flow_view = ft.Column([
        ft.Container(padding=15, bgcolor=ft.Colors.WHITE, content=ft.Row([
            ft.Row([ft.Icon(ft.Icons.EVENT_NOTE), date_label]),
            ft.IconButton(ft.Icons.EDIT_CALENDAR,
                          on_click=lambda _: setattr(date_picker, "open", True) or page.update())
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)),
        car_list_column,
        ft.Container(padding=15, content=ft.Row([
            ft.ElevatedButton("加一车", icon=ft.Icons.ADD, expand=1, on_click=lambda _: car_list_column.controls.append(
                CarCard(len([c for c in car_list_column.controls if isinstance(c, CarCard)]) + 1)) or page.update()),
            ft.ElevatedButton("保存", icon=ft.Icons.SAVE, expand=1, bgcolor=ft.Colors.DEEP_ORANGE,
                              color=ft.Colors.WHITE, on_click=lambda _: save_all_records())
        ]))
    ], expand=True)

    def save_all_records():
        c = conn.cursor()
        for ctrl in car_list_column.controls:
            if isinstance(ctrl, CarCard):
                c.execute(
                    "INSERT OR REPLACE INTO records (record_date, car_number, price, cost, labor, misc, income, note) VALUES (?,?,?,?,?,?,?,?)",
                    (state["selected_date"], ctrl.car_num, float(ctrl.price_ref.value or 0),
                     float(ctrl.cost_ref.value or 0),
                     float(ctrl.labor_ref.value or 0), float(ctrl.misc_ref.value or 0), float(ctrl.income_txt.value),
                     ctrl.note_ref.value))
        conn.commit()
        page.snack_bar = ft.SnackBar(ft.Text("✅ 数据已保存"), bgcolor=ft.Colors.GREEN_800)
        page.snack_bar.open = True
        page.update()

    board_view = ft.Column([
        ft.Container(padding=15, content=ft.Row([
            ft.IconButton(ft.Icons.ARROW_BACK_IOS_NEW, on_click=lambda _: change_month(-1)),
            month_txt,
            ft.IconButton(ft.Icons.ARROW_FORWARD_IOS, on_click=lambda _: change_month(1)),
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)),
        ft.Container(content=cal_grid, expand=True, padding=10),
        ft.Container(
            padding=20,
            bgcolor=ft.Colors.WHITE,
            border_radius=ft.border_radius.only(top_left=25, top_right=25),
            content=ft.Column([
                ft.Text("本月累计盈利汇总", size=14, color=ft.Colors.GREY_600),
                ft.Row([total_month_income], alignment=ft.MainAxisAlignment.CENTER)
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=5)
        )
    ], expand=True, visible=False)

    def change_month(delta):
        state["cur_month"] += delta
        if state["cur_month"] > 12:
            state["cur_month"] = 1; state["cur_year"] += 1
        elif state["cur_month"] < 1:
            state["cur_month"] = 12; state["cur_year"] -= 1
        build_calendar()

    def update_view(idx):
        flow_view.visible = (idx == 0)
        board_view.visible = (idx == 1)
        if idx == 1: build_calendar()
        page.update()

    page.navigation_bar = ft.NavigationBar(
        destinations=[
            ft.NavigationBarDestination(icon=ft.Icons.LIST_ALT, label="流水"),
            ft.NavigationBarDestination(icon=ft.Icons.GRID_VIEW, label="看板")
        ],
        on_change=lambda e: update_view(e.control.selected_index)
    )

    page.add(flow_view, board_view)
    load_flow()


if __name__ == "__main__":
    ft.app(target=main)
