from __future__ import annotations


def build_menu(app):
    """Build the tray menu from the app's current modes + actions. Rebuilt when
    settings change so custom modes show up."""
    import pystray

    def mode_item(name):
        return pystray.MenuItem(
            name,
            lambda icon, item: app.set_mode(name),
            checked=lambda item, n=name: app.active_mode == n,
            radio=True,
        )

    items = [mode_item(n) for n in app.modes]
    items += [
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Show history", lambda icon, item: app.show_history(), default=True),
        pystray.MenuItem("Settings", lambda icon, item: app.show_settings()),
        pystray.MenuItem("Open log", lambda icon, item: app.open_log()),
        pystray.MenuItem(
            "Start on login",
            lambda icon, item: app.toggle_startup(),
            checked=lambda item: app.startup_enabled(),
        ),
        pystray.MenuItem("Reload config", lambda icon, item: app.reload()),
        pystray.MenuItem("Quit", lambda icon, item: app.quit()),
    ]
    return pystray.Menu(*items)


def make_icon(app):
    import pystray
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (64, 64), (24, 24, 28))
    d = ImageDraw.Draw(img)
    d.ellipse((20, 10, 44, 40), fill=(90, 200, 250))
    d.rectangle((30, 38, 34, 50), fill=(90, 200, 250))
    d.rectangle((24, 50, 40, 54), fill=(90, 200, 250))
    return pystray.Icon("typelessless", img, "typelessless", menu=build_menu(app))
