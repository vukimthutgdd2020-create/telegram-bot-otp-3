 (cd "$(git rev-parse --show-toplevel)" && git apply --3way <<'EOF' 
diff --git a/test_otp.py b/test_otp.py
index 94832743b1855b8bdaaddc3b69fad43d9fb96fb9..4c65db6841aaae5f9d666d6eac5a3d4d6ec5b112 100644
--- a/test_otp.py
+++ b/test_otp.py
@@ -1,121 +1,129 @@
-import asyncio
-import logging
-import sqlite3
-import html
-from pathlib import Path
-from urllib.parse import quote
-from io import BytesIO
+import asyncio
+import logging
+import sqlite3
+import html
+import time
+from pathlib import Path
+from urllib.parse import quote
+from io import BytesIO
 
 import httpx
 from PIL import Image
 from aiogram import Bot, Dispatcher, F
 from aiogram.client.default import DefaultBotProperties
 from aiogram.enums import ParseMode
 from aiogram.filters import Command
 from aiogram.fsm.context import FSMContext
 from aiogram.fsm.state import State, StatesGroup
 from aiogram.types import (
     CallbackQuery,
     InlineKeyboardButton,
     InlineKeyboardMarkup,
     Message,
     BufferedInputFile
 )
 
 # --- CẤU HÌNH ---
 BOT_TOKEN = "8762970436:AAHpz95Ua00kER-R7eLIij9lm1XGyR7nRDM"
 ADMIN_ID = 7078570432
 OTP_API_KEY = "8fc8e078133cde11"
 OTP_BASE_URL = "https://chaycodeso3.com/api"
 
 BANK_BIN = "970422"
 BANK_ACCOUNT = "346641789567"
 ACCOUNT_NAME = "VU VAN CUONG"
 
 BASE_DIR = Path(__file__).resolve().parent
 DB_NAME = str(BASE_DIR / "shop_bot.db")
 
 logging.basicConfig(level=logging.INFO)
 bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
-dp = Dispatcher()
-HTTP_CLIENT = httpx.AsyncClient(
-    timeout=httpx.Timeout(15.0, connect=5.0),
+dp = Dispatcher()
+HTTP_CLIENT = httpx.AsyncClient(
+    timeout=httpx.Timeout(15.0, connect=5.0),
     limits=httpx.Limits(max_connections=50, max_keepalive_connections=20),
     follow_redirects=True
-)
-
-DEFAULT_NOTE = "📌 Ghi chú: OTP về sẽ tính tiền. Nếu sau thời gian chờ không có OTP thì hệ thống sẽ hoàn tiền."
-QR_TEMPLATE_PATH = BASE_DIR / "qr_mau_nguoi_cam_giay.jpg"
+)
+API_RETRY_COUNT = 2
+API_RETRY_DELAY = 0.6
+APP_LIST_CACHE_TTL = 20
+OTP_POLL_ATTEMPTS = 45
+OTP_POLL_INTERVAL_SECONDS = 6
+
+DEFAULT_NOTE = "📌 Ghi chú: OTP về sẽ tính tiền. Nếu sau thời gian chờ không có OTP thì hệ thống sẽ hoàn tiền."
+QR_TEMPLATE_PATH = BASE_DIR / "qr_mau_nguoi_cam_giay.jpg"
 
 # Tọa độ vùng tờ giấy theo ảnh bạn đã gửi
 QR_PASTE_X = 220
 QR_PASTE_Y = 500
 QR_PASTE_W = 270
 QR_PASTE_H = 270
 # --- DANH SÁCH APP CỐ ĐỊNH HIỂN THỊ TRONG BOT ---
 FIXED_APP_LIST = [
     {"Id": 1001, "Name": "Facebook"},
     {"Id": 1002, "Name": "Shopee/shopee pay"},
     {"Id": 1005, "Name": "Gmail/Google"},
     {"Id": 1010, "Name": "Instagram"},
     {"Id": 1007, "Name": "Lazada"},
     {"Id": 1021, "Name": "Grab"},
     {"Id": 1022, "Name": "wechat"},
     {"Id": 1024, "Name": "WhatsApp"},
     {"Id": 1032, "Name": "TikTok"},
     {"Id": 1030, "Name": "Twitter"},
     {"Id": 1034, "Name": "Momo"},
     {"Id": 1090, "Name": "Paypal"},
     {"Id": 1097, "Name": "Tiki"},
     {"Id": 1095, "Name": "Amazon"},
     {"Id": 1102, "Name": "My Viettel"},
     {"Id": 1136, "Name": "Roblox"},
     {"Id": 1160, "Name": "Garena"},
     {"Id": 1176, "Name": "ZaloPay"},
     {"Id": 1289, "Name": "Netflix"},
     {"Id": 1301, "Name": "MY VNPT/ DIGILIFE/MYTV/VNPT Money"},
     {"Id": 1425, "Name": "Youtube"},
     {"Id": 1432, "Name": "Highlands"},
     {"Id": 1472, "Name": "Shopee Food"},
     {"Id": 1477, "Name": "VNPAY"},
     {"Id": 1561, "Name": "Binance"},
     {"Id": 1656, "Name": "Katinat"},
     {"Id": 1869, "Name": "Claude"},
     {"Id": 1247, "Name": "Id Apple"},
     {"Id": 1195, "Name": "Dịch Vụ Khác"},
 ]
 
 # --- FSM ---
 class DepositState(StatesGroup):
     waiting_for_amount = State()
 
 # --- DATABASE ---
-def db():
-    conn = sqlite3.connect(DB_NAME)
-    conn.row_factory = sqlite3.Row
-    return conn
+def db():
+    conn = sqlite3.connect(DB_NAME, timeout=10)
+    conn.row_factory = sqlite3.Row
+    conn.execute("PRAGMA journal_mode=WAL")
+    conn.execute("PRAGMA busy_timeout=5000")
+    return conn
 
 def init_db():
     conn = db()
     cur = conn.cursor()
 
     cur.execute("""
         CREATE TABLE IF NOT EXISTS users(
             user_id INTEGER PRIMARY KEY,
             full_name TEXT,
             username TEXT,
             balance INTEGER DEFAULT 0
         )
     """)
 
     cur.execute("""
         CREATE TABLE IF NOT EXISTS app_notes(
             keyword TEXT PRIMARY KEY,
             note TEXT NOT NULL
         )
     """)
 
     cur.execute("PRAGMA table_info(users)")
     columns = [column[1] for column in cur.fetchall()]
     if 'balance' not in columns:
         cur.execute("ALTER TABLE users ADD COLUMN balance INTEGER DEFAULT 0")
@@ -218,138 +226,162 @@ def get_app_note(app_name: str):
     conn = db()
     rows = conn.execute("SELECT keyword, note FROM app_notes ORDER BY LENGTH(keyword) DESC").fetchall()
     conn.close()
 
     app_name_lower = app_name.lower()
     for row in rows:
         if row["keyword"] in app_name_lower:
             return row["note"]
 
     return DEFAULT_NOTE
 def normalize_phone_vn(phone: str) -> str:
     s = "".join(ch for ch in str(phone) if ch.isdigit())
 
     if s.startswith("84"):
         s = "0" + s[2:]
     elif not s.startswith("0"):
         s = "0" + s
 
     return s
 
 def is_valid_phone_vn(phone: str) -> bool:
     s = normalize_phone_vn(phone)
     return s.isdigit() and len(s) == 10 and s.startswith("0")
 
 # --- API OTP ---
-class ChayCodeAPI:
-    def __init__(self, api_key):
-        self.api_key = api_key
-
-    async def _get(self, params):
-        params['apik'] = self.api_key
-        try:
-            response = await HTTP_CLIENT.get(OTP_BASE_URL, params=params)
-            return response.json()
-        except Exception:
-            logging.exception("Lỗi gọi OTP API")
-            return {"ResponseCode": 1, "Msg": "Lỗi kết nối Server"}
+class ChayCodeAPI:
+    def __init__(self, api_key):
+        self.api_key = api_key
+
+    async def _get(self, params):
+        params['apik'] = self.api_key
+        for attempt in range(API_RETRY_COUNT + 1):
+            try:
+                response = await HTTP_CLIENT.get(OTP_BASE_URL, params=params)
+                response.raise_for_status()
+                data = response.json()
+                if isinstance(data, dict):
+                    return data
+                logging.warning("OTP API trả dữ liệu không hợp lệ: %s", type(data))
+            except Exception:
+                logging.exception("Lỗi gọi OTP API (attempt=%s)", attempt + 1)
+
+            if attempt < API_RETRY_COUNT:
+                await asyncio.sleep(API_RETRY_DELAY * (attempt + 1))
+
+        return {"ResponseCode": 1, "Msg": "Lỗi kết nối Server"}
 
     async def get_apps(self):
         return await self._get({'act': 'app'})
 
     # Bổ sung các tham số nhà mạng, đầu số, và số cũ
     async def request_number(self, app_id, carrier=None, prefix=None, number=None):
         params = {'act': 'number', 'appId': app_id}
         if carrier: params['carrier'] = carrier
         if prefix: params['prefix'] = prefix
         if number: params['number'] = number
         return await self._get(params)
 
     async def get_otp_code(self, request_id):
         return await self._get({'act': 'code', 'id': request_id})
 
-otp_api = ChayCodeAPI(OTP_API_KEY)
-QR_TEMPLATE_CACHE = None
-
-async def build_qr_on_paper_image(qr_url: str) -> BufferedInputFile:
+otp_api = ChayCodeAPI(OTP_API_KEY)
+QR_TEMPLATE_CACHE = None
+APP_LIST_CACHE = {"expires_at": 0.0, "data": None}
+
+
+def safe_int(value, default=0):
+    try:
+        return int(float(value))
+    except (TypeError, ValueError):
+        return default
+
+async def build_qr_on_paper_image(qr_url: str) -> BufferedInputFile:
     global QR_TEMPLATE_CACHE
 
     resp = await HTTP_CLIENT.get(qr_url)
     resp.raise_for_status()
     qr_bytes = resp.content
 
     if QR_TEMPLATE_CACHE is None:
         QR_TEMPLATE_CACHE = Image.open(QR_TEMPLATE_PATH).convert("RGBA")
 
     template = QR_TEMPLATE_CACHE.copy()
     qr_img = Image.open(BytesIO(qr_bytes)).convert("RGBA")
 
     qr_size = min(QR_PASTE_W, QR_PASTE_H)
     qr_img = qr_img.resize((qr_size, qr_size))
 
     white_bg = Image.new("RGBA", (qr_size + 20, qr_size + 20), (255, 255, 255, 255))
     white_bg.paste(qr_img, (10, 10))
 
     template.paste(white_bg, (QR_PASTE_X, QR_PASTE_Y))
 
     output = BytesIO()
     template.save(output, format="PNG")
     output.seek(0)
 
     return BufferedInputFile(
         file=output.getvalue(),
         filename="qr_thanh_toan.png"
     )
 
-async def get_fixed_apps_from_api():
+async def get_fixed_apps_from_api():
     """
     Lấy danh sách app từ API nhưng chỉ giữ lại đúng các app trong FIXED_APP_LIST.
     Vẫn lấy Cost thật từ API để tính giá bán.
     """
-    res = await otp_api.get_apps()
-    if res.get("ResponseCode") != 0:
-        return res
-
-    api_apps = res.get("Result", [])
-    api_map = {int(app["Id"]): app for app in api_apps if "Id" in app}
-
-    filtered_apps = []
-    for item in FIXED_APP_LIST:
-        app_id = int(item["Id"])
-        if app_id in api_map:
-            api_item = api_map[app_id]
-            filtered_apps.append({
-                "Id": app_id,
-                "Name": item["Name"],  # ưu tiên tên bạn tự đặt
-                "Cost": api_item.get("Cost", 0)
-            })
-
-    return {
-        "ResponseCode": 0,
-        "Msg": "OK",
-        "Result": filtered_apps
-    }
+    now = time.time()
+    if APP_LIST_CACHE["data"] and APP_LIST_CACHE["expires_at"] > now:
+        return APP_LIST_CACHE["data"]
+
+    res = await otp_api.get_apps()
+    if res.get("ResponseCode") != 0:
+        return res
+
+    api_apps = res.get("Result", [])
+    api_map = {safe_int(app.get("Id"), -1): app for app in api_apps if "Id" in app}
+
+    filtered_apps = []
+    for item in FIXED_APP_LIST:
+        app_id = safe_int(item.get("Id"), -1)
+        if app_id in api_map:
+            api_item = api_map[app_id]
+            filtered_apps.append({
+                "Id": app_id,
+                "Name": item["Name"],  # ưu tiên tên bạn tự đặt
+                "Cost": safe_int(api_item.get("Cost"), 0)
+            })
+
+    result = {
+        "ResponseCode": 0,
+        "Msg": "OK",
+        "Result": filtered_apps
+    }
+    APP_LIST_CACHE["data"] = result
+    APP_LIST_CACHE["expires_at"] = now + APP_LIST_CACHE_TTL
+    return result
 
 # --- KEYBOARDS ---
 def main_menu_keyboard(user_id):
     user = get_user(user_id)
     balance = user['balance'] if user else 0
     bal_text = "Vô hạn" if user_id == ADMIN_ID else f"{balance:,}đ"
     return InlineKeyboardMarkup(inline_keyboard=[
         [InlineKeyboardButton(text=f"💰 Số dư: {bal_text}", callback_data="refresh_bal")],
         [InlineKeyboardButton(text="📱 Thuê số OTP", callback_data="otp_list")],
         [
             InlineKeyboardButton(text="💳 Nạp tiền", callback_data="deposit"),
             InlineKeyboardButton(text="☎️ Hỗ trợ", callback_data="contact")
         ],
     ])
 
 # --- HANDLERS ---
 @dp.message(Command("start"))
 async def show_menu(m: Message):
     save_user(m.from_user)
     await m.answer(
         f"👋 Chào <b>{m.from_user.full_name}</b>!",
         reply_markup=main_menu_keyboard(m.from_user.id)
     )
 
 @dp.callback_query(F.data == "refresh_bal")
@@ -677,220 +709,216 @@ async def admin_action_handler(c: CallbackQuery):
     elif action == "admin_reject":
         user_id = int(parts[1])
         amount = int(parts[2])
 
         try:
             await bot.send_message(
                 user_id,
                 f"❌ Yêu cầu nạp <b>{amount:,}đ</b> chưa được duyệt. Vui lòng liên hệ admin nếu cần."
             )
         except Exception:
             logging.exception("Không gửi được tin nhắn từ chối cho khách")
 
         await c.message.edit_text(
             c.message.text + f"\n\n❌ Đã từ chối yêu cầu nạp {amount:,}đ"
         )
         await c.answer("Đã từ chối.")
 # --- XỬ LÝ OTP ---
 @dp.callback_query(F.data == "otp_list")
 async def otp_list_callback(c: CallbackQuery):
     save_user(c.from_user)
     res = await get_fixed_apps_from_api()
 
     if res.get("ResponseCode") == 0:
         btns = []
 
-        for app in res["Result"]:
-            try:
-                cost = int(float(app.get("Cost", 0)))
-            except:
-                cost = 0
-
-            sell_price = int(cost * 3000)
-            app_id = int(app["Id"])
+        for app in res["Result"]:
+            cost = safe_int(app.get("Cost"), 0)
+
+            sell_price = int(cost * 3000)
+            app_id = safe_int(app.get("Id"), 0)
 
             btns.append([
                 InlineKeyboardButton(
                     text=f"{app['Name']} [{app_id}] - {sell_price:,}đ",
                     callback_data=f"appinfo|{app_id}|{sell_price}|{app['Name']}"
                 )
             ])
 
         btns.append([InlineKeyboardButton(text="⬅️ Quay lại", callback_data="menu")])
 
         await c.message.edit_text(
             "<b>Chọn dịch vụ OTP</b>",
             reply_markup=InlineKeyboardMarkup(inline_keyboard=btns)
         )
     else:
         await c.answer("Lỗi kết nối API", show_alert=True)
 
 # --- XEM GHI CHÚ VÀ CHỌN NHÀ MẠNG ---
 @dp.callback_query(F.data.startswith("appinfo|"))
 async def app_info_callback(c: CallbackQuery):
     save_user(c.from_user)
     try:
         _, app_id, sell_price, app_name = c.data.split("|", 3)
     except: return await c.answer("Lỗi dữ liệu!")
 
     # Cấu trúc menu chọn Nhà mạng
     carriers = ["Viettel", "Mobi", "Vina", "VNMB", "ITelecom"]
     btns = [[InlineKeyboardButton(text="🚀 Mua ngay (Ngẫu nhiên)", callback_data=f"buy|{app_id}|{sell_price}|{app_name}")]]
     
     row = []
     for net in carriers:
         row.append(InlineKeyboardButton(text=net, callback_data=f"buy|{app_id}|{sell_price}|{app_name}|{net}"))
         if len(row) == 3:
             btns.append(row); row = []
     if row: btns.append(row)
     
     btns.append([InlineKeyboardButton(text="⬅️ Quay lại danh sách", callback_data="otp_list")])
     
     note = get_app_note(app_name)
     await c.message.edit_text(f"📱 <b>{app_name}</b>\n💰 Giá: <b>{int(sell_price):,}đ</b>\n\n{note}\n\n<i>Chọn nhà mạng cụ thể:</i>", reply_markup=InlineKeyboardMarkup(inline_keyboard=btns))
 
 @dp.callback_query(F.data.startswith("buy|"))
-async def otp_buy_callback(c: CallbackQuery):
-    save_user(c.from_user)
-    parts = c.data.split("|")
-    app_id, sell_price, app_name = parts[1], int(parts[2]), parts[3]
-    carrier = parts[4] if len(parts) > 4 else None # Nhà mạng
+async def otp_buy_callback(c: CallbackQuery):
+    save_user(c.from_user)
+    parts = c.data.split("|")
+    if len(parts) < 4:
+        return await c.answer("Dữ liệu không hợp lệ.", show_alert=True)
+    app_id, sell_price, app_name = parts[1], safe_int(parts[2], 0), parts[3]
+    carrier = parts[4] if len(parts) > 4 else None # Nhà mạng
 
     user_id = c.from_user.id
     if user_id != ADMIN_ID:
         user = get_user(user_id)
         if not user or user['balance'] < sell_price: return await c.answer("Không đủ tiền!", show_alert=True)
 
     await c.message.edit_text(f"⏳ Đang lấy số {'mạng ' + carrier if carrier else ''}...")
     res = await otp_api.request_number(app_id, carrier=carrier)
 
     if res.get("ResponseCode") == 0:
         if user_id != ADMIN_ID: update_balance(user_id, -sell_price)
         phone = res["Result"]["Number"]
         req_id = res["Result"]["Id"]
         display_phone = normalize_phone_vn(phone)
         await c.message.edit_text(f"✅ <b>ĐÃ LẤY SỐ</b>\n📱 App: <b>{app_name}</b>\n📞 Số: <code>{display_phone}</code>\n🕒 Đợi OTP...")
         asyncio.create_task(wait_for_otp(user_id, req_id, display_phone, sell_price, (user_id == ADMIN_ID), app_name))
     else:
         # Thông báo lỗi từ API
         await c.answer(f"Lỗi: {res.get('Msg')}", show_alert=True)
 
 # --- MUA LẠI SỐ CŨ (Lệnh mới) ---
 @dp.message(Command("mualai"))
 async def buy_back_number(m: Message):
     # Cú pháp: /mualai [appId] [số]
     parts = m.text.split()
     if len(parts) < 3:
         return await m.answer("Cách dùng: <code>/mualai [ID_App] [Số_điện_thoại]</code>")
 
     try:
         app_id = int(parts[1])
     except:
         return await m.answer("❌ ID App phải là số.")
 
     phone_number_raw = parts[2].strip()
     phone_number = normalize_phone_vn(phone_number_raw)
 
     if not is_valid_phone_vn(phone_number):
         return await m.answer(
             "❌ Số điện thoại không hợp lệ.\n"
             "Vui lòng nhập theo dạng <code>0xxxxxxxxx</code>"
         )
 
     # Lấy giá app từ API để check/trừ tiền giống luồng mua thường
     apps_res = await get_fixed_apps_from_api()
     if apps_res.get("ResponseCode") != 0:
         return await m.answer("❌ Không lấy được danh sách app từ API.")
 
     selected_app = None
-    for app in apps_res.get("Result", []):
-        if int(app.get("Id", 0)) == app_id:
-            selected_app = app
-            break
+    for app in apps_res.get("Result", []):
+        if safe_int(app.get("Id"), 0) == app_id:
+            selected_app = app
+            break
 
     if not selected_app:
         return await m.answer("❌ Không tìm thấy app này trong danh sách bot đang bán.")
 
-    try:
-        cost = int(float(selected_app.get("Cost", 0)))
-    except:
-        cost = 0
+    cost = safe_int(selected_app.get("Cost"), 0)
 
     sell_price = int(cost * 3000)
     app_name = selected_app.get("Name", f"App {app_id}")
 
     user_id = m.from_user.id
     is_admin = (user_id == ADMIN_ID)
 
     if not is_admin:
         user = get_user(user_id)
         current_balance = int(user["balance"]) if user else 0
 
         if current_balance < sell_price:
             return await m.answer(
                 f"❌ Không đủ tiền để mua lại số.\n"
                 f"💰 Giá mua lại: <b>{sell_price:,}đ</b>\n"
                 f"💳 Số dư hiện tại: <b>{current_balance:,}đ</b>"
             )
 
     await m.answer(
         f"⏳ Đang yêu cầu mua lại số <code>{phone_number}</code>...\n"
         f"📱 App: <b>{app_name}</b>\n"
         f"💰 Giá: <b>{sell_price:,}đ</b>"
     )
 
     res = await otp_api.request_number(app_id, number=phone_number)
 
     if res.get("ResponseCode") == 0:
         req_id = res["Result"]["Id"]
 
         if not is_admin:
             update_balance(user_id, -sell_price)
 
         await m.answer(
             f"✅ Đã kết nối lại số <code>{phone_number}</code>\n"
             f"📱 App: <b>{app_name}</b>\n"
             f"🕒 Đợi mã OTP..."
         )
 
         asyncio.create_task(
             wait_for_otp(
                 user_id=user_id,
                 req_id=req_id,
                 phone=phone_number,
                 sell_price=sell_price,
                 is_admin=is_admin,
                 app_name=app_name
             )
         )
     else:
         await m.answer(f"❌ Lỗi: {res.get('Msg')}")
-async def wait_for_otp(user_id, req_id, phone, sell_price, is_admin, app_name):
-    for _ in range(60):
-        await asyncio.sleep(7)
-        res = await otp_api.get_otp_code(req_id)
-        if res.get("ResponseCode") == 0:
-            await bot.send_message(user_id, f"🎯 <b>MÃ OTP:</b> <code>{res['Result']['Code']}</code>\n📱 App: <b>{app_name}</b>\n📞 Số: <code>{phone}</code>")
-            return
-        elif res.get("ResponseCode") == 2: break
+async def wait_for_otp(user_id, req_id, phone, sell_price, is_admin, app_name):
+    for _ in range(OTP_POLL_ATTEMPTS):
+        await asyncio.sleep(OTP_POLL_INTERVAL_SECONDS)
+        res = await otp_api.get_otp_code(req_id)
+        if res.get("ResponseCode") == 0:
+            await bot.send_message(user_id, f"🎯 <b>MÃ OTP:</b> <code>{res['Result']['Code']}</code>\n📱 App: <b>{app_name}</b>\n📞 Số: <code>{phone}</code>")
+            return
+        elif res.get("ResponseCode") == 2: break
     
     if not is_admin:
         update_balance(user_id, sell_price)
         await bot.send_message(user_id, f"❌ Hết hạn số <code>{phone}</code>. Đã hoàn <b>{sell_price:,}đ</b>.")
     else:
         await bot.send_message(user_id, f"❌ Hết hạn số <code>{phone}</code> (Admin).")
 
 @dp.callback_query(F.data == "menu")
 async def menu_back(c: CallbackQuery):
     save_user(c.from_user)
     await c.message.edit_text("🏠 <b>Menu</b>", reply_markup=main_menu_keyboard(c.from_user.id))
 
 async def main():
     init_db()
     print("Bot is running...")
     try:
         await dp.start_polling(bot)
     finally:
         await HTTP_CLIENT.aclose()
 
 if __name__ == "__main__":
-    asyncio.run(main())
\ No newline at end of file
+    asyncio.run(main())
 
EOF
)
