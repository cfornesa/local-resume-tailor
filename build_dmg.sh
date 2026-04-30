#!/bin/bash
set -e

STAGING=$(mktemp -d)
APP_NAME="Resume Tailor"
DMG_NAME="Resume Tailor.dmg"

echo "Staging..."
cp -r "$APP_NAME.app" "$STAGING/"
mkdir -p "$STAGING/$APP_NAME.app/Contents/Resources"
cp src/resume.py src/resume_core.py src/requirements.txt "$STAGING/$APP_NAME.app/Contents/Resources/"
cp "$APP_NAME.app/Contents/Resources/AppIcon.icns" "$STAGING/$APP_NAME.app/Contents/Resources/"
cp src/image.png "$STAGING/$APP_NAME.app/Contents/Resources/"
ln -s /Applications "$STAGING/Applications"

echo "Building DMG..."
hdiutil create \
    -volname "$APP_NAME" \
    -srcfolder "$STAGING" \
    -ov \
    -format UDZO \
    "$DMG_NAME"

rm -rf "$STAGING"
echo "Done: $DMG_NAME"
