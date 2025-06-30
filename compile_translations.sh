#!/bin/bash

TS_DIR="./localization/locales/ua"

if ! command -v pyside6-lrelease &> /dev/null; then
    echo "❌ pyside6-lrelease не знайдено. Встанови PySide6 спочатку (pip install pyside6)"
    exit 1
fi

for ts_file in "$TS_DIR"/*.qt.ts; do
    base_name=$(basename "$ts_file" .qt.ts)

    qm_file="$TS_DIR/$base_name.qm"

    echo "📄 Compiling $ts_file → $qm_file"
    pyside6-lrelease "$ts_file" -qm "$qm_file"
done

echo "✅ All .ts files compiled."
