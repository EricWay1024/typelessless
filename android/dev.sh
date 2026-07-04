#!/usr/bin/env bash
# Build the debug APK and install it on the connected device (wireless adb).
# Usage: ./dev.sh            build + install
#        ./dev.sh build      build only
set -euo pipefail

AND="$(cd "$(dirname "$0")" && pwd)"
SDK="${ANDROID_HOME:-$HOME/android-sdk}"
ADB="$SDK/platform-tools/adb"

"$AND/gradlew" -p "$AND" :app:assembleDebug --console=plain
APK="$AND/app/build/outputs/apk/debug/app-debug.apk"
echo "APK: $APK"

if [ "${1:-}" = "build" ]; then
    exit 0
fi

if ! "$ADB" get-state >/dev/null 2>&1; then
    echo "No device connected. Pair/connect first, e.g.:"
    echo "  $ADB pair <ip:pair_port> <code>"
    echo "  $ADB connect <ip:connect_port>"
    exit 1
fi

"$ADB" install -r "$APK"
echo "Installed. On the phone: Settings > System > Languages & input > on-screen keyboard"
echo "-> enable 'typelessless', then tap the keyboard 🌐 button to switch to it."
