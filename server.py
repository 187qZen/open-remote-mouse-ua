"""PC Remote server (Windows). Run: pythonw server.py"""
import asyncio, ctypes, hmac, json, os, random, socket, sys, time
from ctypes import wintypes
from aiohttp import web

PORT = 8765
FROZEN = getattr(sys, "frozen", False)
DIR = os.path.dirname(sys.executable) if FROZEN else os.path.dirname(os.path.abspath(__file__))  # config.json
RES = getattr(sys, "_MEIPASS", DIR)  # вбудовані ресурси (index.html)
CFG = os.path.join(DIR, "config.json")
NEW_CFG = not os.path.exists(CFG)

def load_cfg():
    if os.path.exists(CFG):
        with open(CFG, encoding="utf-8") as f:
            return json.load(f)
    cfg = {"pin": "".join(random.choice("0123456789") for _ in range(6))}
    with open(CFG, "w", encoding="utf-8") as f:
        json.dump(cfg, f)
    return cfg

CONFIG = load_cfg()
u32 = ctypes.windll.user32
k32 = ctypes.windll.kernel32
dwm = ctypes.windll.dwmapi
u32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]

# ---------- input ----------
VK = {"playpause": 0xB3, "next": 0xB0, "prev": 0xB1, "stop": 0xB2,
      "mute": 0xAD, "voldown": 0xAE, "volup": 0xAF,
      "backspace": 0x08, "enter": 0x0D, "tab": 0x09, "esc": 0x1B,
      "left": 0x25, "up": 0x26, "right": 0x27, "down": 0x28, "delete": 0x2E,
      # відео (YouTube та більшість плеєрів); за кодами клавіш, тож розкладка не важлива
      "j": 0x4A, "k": 0x4B, "l": 0x4C, "f": 0x46, "c": 0x43, "m": 0x4D, "t": 0x54, "space": 0x20}
COMBOS = {"speedup": (0x10, 0xBE), "speeddown": (0x10, 0xBC),   # Shift+. / Shift+,
          "nextvid": (0x10, 0x4E), "prevvid": (0x10, 0x50)}    # Shift+N / Shift+P

def press_combo(mod, vk):
    u32.keybd_event(mod, 0, 0, 0)
    press(vk)
    u32.keybd_event(mod, 0, 2, 0)

def press(vk):
    u32.keybd_event(vk, 0, 0, 0)
    u32.keybd_event(vk, 0, 2, 0)

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]
class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]
class _U(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT)]
class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _U)]

def type_text(text):
    for ch in text:
        if ch == "\n":
            press(VK["enter"]); continue
        b = ch.encode("utf-16-le")
        for i in range(0, len(b), 2):
            code = int.from_bytes(b[i:i+2], "little")
            for flags in (0x0004, 0x0004 | 0x0002):  # UNICODE, UNICODE|KEYUP
                inp = INPUT(type=1, u=_U(ki=KEYBDINPUT(0, code, flags, 0, 0)))
                u32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))

def mouse(flags, dx=0, dy=0, data=0):
    u32.mouse_event(flags, dx, dy, data & 0xFFFFFFFF, 0)

# ---------- windows ----------
ICON_PATHS = {}   # ім'я exe -> повний шлях
ICON_CACHE = {}   # ім'я exe -> png bytes

def proc_path(hwnd):
    pid = wintypes.DWORD()
    u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    h = k32.OpenProcess(0x1000, False, pid.value)
    if not h:
        return ""
    buf = ctypes.create_unicode_buffer(520)
    size = wintypes.DWORD(520)
    k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size))
    k32.CloseHandle(h)
    return buf.value

def proc_name(hwnd):
    p = proc_path(hwnd)
    name = os.path.basename(p)
    if p and name:
        ICON_PATHS[name.lower()] = p
    return name

gdi = ctypes.windll.gdi32
shell = ctypes.windll.shell32
class SHFILEINFOW(ctypes.Structure):
    _fields_ = [("hIcon", ctypes.c_void_p), ("iIcon", ctypes.c_int), ("dwAttributes", wintypes.DWORD),
                ("szDisplayName", ctypes.c_wchar * 260), ("szTypeName", ctypes.c_wchar * 80)]
class ICONINFO(ctypes.Structure):
    _fields_ = [("fIcon", wintypes.BOOL), ("xHotspot", wintypes.DWORD), ("yHotspot", wintypes.DWORD),
                ("hbmMask", ctypes.c_void_p), ("hbmColor", ctypes.c_void_p)]
class BITMAP(ctypes.Structure):
    _fields_ = [("bmType", wintypes.LONG), ("bmWidth", wintypes.LONG), ("bmHeight", wintypes.LONG),
                ("bmWidthBytes", wintypes.LONG), ("bmPlanes", wintypes.WORD), ("bmBitsPixel", wintypes.WORD),
                ("bmBits", ctypes.c_void_p)]
class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG),
                ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
                ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]
shell.SHGetFileInfoW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, ctypes.POINTER(SHFILEINFOW), wintypes.UINT, wintypes.UINT]
shell.SHGetFileInfoW.restype = ctypes.c_size_t
u32.GetIconInfo.argtypes = [ctypes.c_void_p, ctypes.POINTER(ICONINFO)]
u32.DestroyIcon.argtypes = [ctypes.c_void_p]
u32.GetDC.restype = ctypes.c_void_p
u32.ReleaseDC.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
gdi.GetObjectW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
gdi.DeleteObject.argtypes = [ctypes.c_void_p]
gdi.GetDIBits.argtypes = [ctypes.c_void_p, ctypes.c_void_p, wintypes.UINT, wintypes.UINT,
                          ctypes.c_void_p, ctypes.c_void_p, wintypes.UINT]

def _bits(hdc, hbm, w, h):
    bih = BITMAPINFOHEADER(40, w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
    buf = ctypes.create_string_buffer(w * h * 4)
    gdi.GetDIBits(hdc, hbm, 0, h, buf, ctypes.byref(bih), 0)
    return buf.raw

def icon_png(exe_path):
    from PIL import Image
    import io
    sfi = SHFILEINFOW()
    # 0x100 = SHGFI_ICON, 0x0 = великий (32x32)
    if not shell.SHGetFileInfoW(exe_path, 0, ctypes.byref(sfi), ctypes.sizeof(sfi), 0x100) or not sfi.hIcon:
        return None
    ii = ICONINFO()
    u32.GetIconInfo(sfi.hIcon, ctypes.byref(ii))
    try:
        bm = BITMAP()
        gdi.GetObjectW(ii.hbmColor, ctypes.sizeof(BITMAP), ctypes.byref(bm))
        w, h = bm.bmWidth, bm.bmHeight
        hdc = u32.GetDC(None)
        color = bytearray(_bits(hdc, ii.hbmColor, w, h))
        if not any(color[3::4]):  # немає альфа-каналу -> беремо маску
            mask = _bits(hdc, ii.hbmMask, w, h)
            for i in range(w * h):
                color[i*4+3] = 0 if mask[i*4] else 255
        u32.ReleaseDC(None, hdc)
        img = Image.frombuffer("RGBA", (w, h), bytes(color), "raw", "BGRA", 0, 1)
        out = io.BytesIO()
        img.save(out, "PNG")
        return out.getvalue()
    finally:
        if ii.hbmColor: gdi.DeleteObject(ii.hbmColor)
        if ii.hbmMask: gdi.DeleteObject(ii.hbmMask)
        u32.DestroyIcon(sfi.hIcon)

def list_windows():
    res = []
    fg = u32.GetForegroundWindow()
    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(hwnd, _):
        if not u32.IsWindowVisible(hwnd) or u32.GetWindow(hwnd, 4):
            return True
        if u32.GetWindowLongW(hwnd, -20) & 0x80:  # toolwindow
            return True
        cloaked = ctypes.c_int(0)
        dwm.DwmGetWindowAttribute(hwnd, 14, ctypes.byref(cloaked), 4)
        if cloaked.value:
            return True
        n = u32.GetWindowTextLengthW(hwnd)
        if n == 0:
            return True
        buf = ctypes.create_unicode_buffer(n + 1)
        u32.GetWindowTextW(hwnd, buf, n + 1)
        res.append({"id": int(hwnd), "title": buf.value, "app": proc_name(hwnd),
                    "active": hwnd == fg})
        return True
    u32.EnumWindows(cb, 0)
    return res

def activate(hwnd):
    if u32.IsIconic(hwnd):
        u32.ShowWindow(hwnd, 9)
    u32.keybd_event(0x12, 0, 0, 0); u32.keybd_event(0x12, 0, 2, 0)  # alt trick
    u32.SetForegroundWindow(hwnd)

# ---------- http ----------
FAILS = {}  # ip -> часи невдалих спроб PIN

def pin_ok(req, token):
    """Порівняння PIN у сталий час + обмеження перебору: 30 невдалих спроб за 10 хв з однієї адреси."""
    ip = req.remote or "?"
    now = time.time()
    fl = [t for t in FAILS.get(ip, []) if now - t < 600]
    if len(fl) >= 30:
        FAILS[ip] = fl
        return False
    ok = hmac.compare_digest((token or "").encode(), CONFIG["pin"].encode())
    if ok:
        FAILS.pop(ip, None)
    else:
        fl.append(now)
        FAILS[ip] = fl
    return ok

def authed(req):
    return pin_ok(req, req.headers.get("X-Token"))

@web.middleware
async def cors(request, handler):
    resp = web.Response(status=204) if request.method == "OPTIONS" else await handler(request)
    if request.path != "/ws":
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Headers"] = "X-Token, Content-Type"
        resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return resp

async def index(req):
    return web.FileResponse(os.path.join(RES, "index.html"))

async def manifest(req):
    return web.json_response({"name": "PC Remote", "short_name": "Remote", "start_url": "/",
        "display": "standalone", "background_color": "#101418", "theme_color": "#101418",
        "icons": [{"src": "/icon.svg", "sizes": "any", "type": "image/svg+xml"}]})

async def icon(req):
    svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><rect width="100" height="100" rx="22" fill="#1f6feb"/><rect x="30" y="18" width="40" height="64" rx="20" fill="none" stroke="#fff" stroke-width="6"/><line x1="50" y1="30" x2="50" y2="48" stroke="#fff" stroke-width="6" stroke-linecap="round"/></svg>'
    return web.Response(text=svg, content_type="image/svg+xml")

async def auth(req):
    return web.json_response({"ok": authed(req), "host": socket.gethostname()})

async def windows(req):
    if not authed(req): return web.Response(status=401)
    return web.json_response(list_windows())

async def icon_app(req):
    if not pin_ok(req, req.query.get("t")): return web.Response(status=401)
    name = req.query.get("app", "").lower()
    if name not in ICON_CACHE:
        path = ICON_PATHS.get(name)
        try:
            ICON_CACHE[name] = icon_png(path) if path else None
        except Exception as e:
            print("icon error", name, e)
            ICON_CACHE[name] = None
    data = ICON_CACHE[name]
    if not data: return web.Response(status=404)
    return web.Response(body=data, content_type="image/png",
                        headers={"Cache-Control": "max-age=86400"})

HELD = {"l": False}  # чи затиснута ліва кнопка миші (перетягування)

def handle(d):
    t = d.get("t")
    if t == "key" and d["k"] in VK: press(VK[d["k"]])
    elif t == "combo" and d["k"] in COMBOS: press_combo(*COMBOS[d["k"]])
    elif t == "text": type_text(d["s"])
    elif t == "move": mouse(0x0001, int(d["dx"]), int(d["dy"]))
    elif t == "down": mouse(0x0002); HELD["l"] = True
    elif t == "up": mouse(0x0004); HELD["l"] = False
    elif t == "click": mouse(0x0002); mouse(0x0004)
    elif t == "rclick": mouse(0x0008); mouse(0x0010)
    elif t == "scroll": mouse(0x0800, 0, 0, int(-d["dy"]))
    elif t == "focus": activate(int(d["id"]))
    elif t == "close": u32.PostMessageW(int(d["id"]), 0x10, 0, 0)

async def cmd(req):
    if not authed(req): return web.Response(status=401)
    handle(await req.json())
    return web.json_response({"ok": True})

async def ws_handler(req):
    if not pin_ok(req, req.query.get("t")): return web.Response(status=401)
    ws = web.WebSocketResponse(heartbeat=20)
    await ws.prepare(req)
    try:
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                try:
                    handle(json.loads(msg.data))
                except Exception as e:
                    print("ws error:", e)
    finally:
        if HELD["l"]:  # зв'язок обірвався під час перетягування, відпускаємо кнопку
            mouse(0x0004)
            HELD["l"] = False
    return ws

def lan_ips():
    ips = set()
    try:
        for i in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.add(i[4][0])
    except Exception:
        pass
    return [i for i in ips if not i.startswith("127.")]

async def start_mdns(app):
    try:
        from zeroconf import ServiceInfo
        from zeroconf.asyncio import AsyncZeroconf
        host = socket.gethostname()
        info = ServiceInfo("_http._tcp.local.", f"PC Remote {host}._http._tcp.local.",
                           addresses=[socket.inet_aton(i) for i in lan_ips()],
                           port=PORT, server=f"{host}.local.")
        app["zc"] = AsyncZeroconf()
        await app["zc"].async_register_service(info)
        app["zc_info"] = info
    except Exception as e:
        print("mDNS недоступний:", e)

async def stop_mdns(app):
    if "zc" in app:
        await app["zc"].async_unregister_service(app["zc_info"])
        await app["zc"].async_close()

def make_app():
    app = web.Application(middlewares=[cors])
    app.add_routes([web.get("/", index), web.get("/manifest.json", manifest),
                    web.get("/icon.svg", icon), web.get("/api/auth", auth),
                    web.get("/api/windows", windows), web.get("/api/icon", icon_app),
                    web.get("/ws", ws_handler), web.post("/api/cmd", cmd)])
    app.on_startup.append(start_mdns)
    app.on_cleanup.append(stop_mdns)
    return app

def info_text():
    host = socket.gethostname()
    lines = [f"Адреса: http://{host}.local:{PORT}", f"PIN: {CONFIG['pin']}"]
    lines += [f"Запасна: http://{ip}:{PORT}" for ip in lan_ips()]
    return "\n".join(lines)

STATE = {}

def server_thread():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    runner = web.AppRunner(make_app())
    loop.run_until_complete(runner.setup())
    loop.run_until_complete(web.TCPSite(runner, "0.0.0.0", PORT).start())
    STATE["loop"] = loop
    loop.run_forever()
    loop.run_until_complete(runner.cleanup())

def tray_image():
    from PIL import Image, ImageDraw
    im = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((2, 2, 62, 62), radius=14, fill=(31, 111, 235, 255))
    d.rounded_rectangle((20, 12, 44, 52), radius=12, outline="white", width=4)
    d.line((32, 20, 32, 30), fill="white", width=4)
    return im

def popup(text):
    import threading
    threading.Thread(target=lambda: u32.MessageBoxW(0, text, "PC Remote", 0x40), daemon=True).start()

def single_instance():
    kl = ctypes.WinDLL("kernel32", use_last_error=True)
    kl.CreateMutexW(None, False, "Global\\PCRemoteServerMutex")
    return ctypes.get_last_error() != 183  # ERROR_ALREADY_EXISTS

def main():
    import threading
    if not single_instance():
        u32.MessageBoxW(0, "PC Remote уже запущено.\n\n" + info_text(), "PC Remote", 0x40)
        return
    threading.Thread(target=server_thread, daemon=True).start()
    try:
        import pystray
    except ImportError:
        print(info_text())
        threading.Event().wait()  # без трею просто працюємо
        return
    def quit_(icon, item):
        if "loop" in STATE:
            STATE["loop"].call_soon_threadsafe(STATE["loop"].stop)
        icon.stop()
    menu = pystray.Menu(
        pystray.MenuItem("Показати PIN і адресу", lambda i, it: popup(info_text()), default=True),
        pystray.MenuItem("Вийти", quit_))
    icon = pystray.Icon("PCRemote", tray_image(), "PC Remote", menu)
    if NEW_CFG:
        popup("PC Remote запущено.\n\n" + info_text())
    icon.run()

if __name__ == "__main__":
    main()
