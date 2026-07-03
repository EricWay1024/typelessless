from __future__ import annotations


def make_icon(app):
    """Build a system-tray icon: pick the mode (radio), reload config, quit.
    pystray/PIL are imported lazily."""
    import pystray
    from PIL import Image, ImageDraw

    def image():
        img = Image.new("RGB", (64, 64), (24, 24, 28))
        d = ImageDraw.Draw(img)
        d.ellipse((20, 10, 44, 40), fill=(90, 200, 250))   # mic head
        d.rectangle((30, 38, 34, 50), fill=(90, 200, 250))  # stand
        d.rectangle((24, 50, 40, 54), fill=(90, 200, 250))  # base
        return img

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
        pystray.MenuItem("Reload config", lambda icon, item: app.reload()),
        pystray.MenuItem("Quit", lambda icon, item: app.quit()),
    ]
    return pystray.Icon("typelessless", image(), "typelessless", menu=pystray.Menu(*items))
