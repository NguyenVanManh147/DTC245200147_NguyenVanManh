"""Local password dialog. Writes only ignored secrets/local-auth.json; never logs values."""
import datetime
import json
import pathlib
import tkinter as tk
from tkinter import messagebox

ROOT = pathlib.Path(__file__).resolve().parents[1]
folder = ROOT / 'secrets'
folder.mkdir(exist_ok=True)
window = tk.Tk()
window.title('Portfolio — nhập credentials cục bộ')
window.geometry('560x340')
window.resizable(False, False)
window.attributes('-topmost', True)
tk.Label(window, text='Mật khẩu chỉ được lưu trong secrets/ đã bị Git ignore.\nKhông đổi tài khoản khi nhấn Lưu; bước sao lưu/kiểm tra chạy riêng.', justify='left').pack(padx=18, pady=15, anchor='w')
form = tk.Frame(window)
form.pack(fill='x', padx=18)
tk.Label(form, text='Root MySQL thực tế:').grid(row=0, column=0, sticky='w', pady=7)
root_password = tk.Entry(form, show='*', width=36)
root_password.grid(row=0, column=1, padx=12)
tk.Label(form, text='WordPress username:').grid(row=1, column=0, sticky='w', pady=7)
wp_user = tk.Entry(form, width=36)
wp_user.insert(0, 'vanmanh_admin')
wp_user.grid(row=1, column=1, padx=12)
tk.Label(form, text='WordPress password:').grid(row=2, column=0, sticky='w', pady=7)
wp_password = tk.Entry(form, show='*', width=36)
wp_password.grid(row=2, column=1, padx=12)
tk.Label(window, text='Có thể để trống WordPress nếu chỉ cần xử lý root.\nKhông chụp màn hình hoặc đưa secrets/ vào Git.', justify='left').pack(padx=18, pady=12, anchor='w')

def submit():
    password = root_password.get()
    if not password:
        messagebox.showerror('Chưa có credential', 'Nhập mật khẩu root thực tế hoặc đóng cửa sổ nếu chưa sẵn sàng.')
        return
    if any(c in password for c in '\r\n\x00'):
        messagebox.showerror('Credential không hợp lệ', 'Mật khẩu không được chứa newline hoặc NUL.')
        return
    data = {'MYSQL_ROOT_CURRENT_PASSWORD': password, 'WORDPRESS_ADMIN_USER': wp_user.get(),
            'WORDPRESS_ADMIN_PASSWORD': wp_password.get(),
            'captured_at': datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=7))).isoformat()}
    path = folder / 'local-auth.json'
    temporary = folder / 'local-auth.pending.json'
    temporary.write_text(json.dumps(data), encoding='utf-8')
    temporary.replace(path)
    window.destroy()
    print('Local credentials saved privately; no account changed.', flush=True)

tk.Button(window, text='Lưu credentials cục bộ', command=submit, width=30).pack(pady=5)
root_password.focus_set()
print('Waiting for local password dialog input; nothing logged.', flush=True)
window.mainloop()
