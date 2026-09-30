#!/bin/zsh
# Builds the .app for one working copy and installs it into ~/Applications.
# Usage: build-app.sh <project dir> <port> <instance env name>
set -euo pipefail

project_dir=${1:?project dir}
port=${2:?port}
env_name=${3:?instance env name}

macos_dir=${0:A:h:h}
install_dir="$HOME/Applications"
build_dir="$macos_dir/.build/app"

if [[ $env_name == prod ]]; then
    app_name="AnythingToAnki"
    bundle_id="local.anything-to-anki"
else
    app_name="AnythingToAnki ${(C)env_name}"
    bundle_id="local.anything-to-anki.${env_name:l}"
fi
version=$(git -C "$project_dir" rev-parse --short HEAD)
bundle="$build_dir/$app_name.app"

echo "Building $app_name for $project_dir (port $port)..."
swift build --package-path "$macos_dir" -c release --product AnythingToAnki
binary="$(swift build --package-path "$macos_dir" -c release --show-bin-path)/AnythingToAnki"

[[ -e $build_dir ]] && trash "$build_dir"
mkdir -p "$bundle/Contents/MacOS" "$bundle/Contents/Resources"
cp "$binary" "$bundle/Contents/MacOS/$app_name"
sed -e "s|@APP_NAME@|$app_name|g" \
    -e "s|@BUNDLE_ID@|$bundle_id|g" \
    -e "s|@VERSION@|$version|g" \
    -e "s|@PROJECT_DIR@|$project_dir|g" \
    -e "s|@PORT@|$port|g" \
    "$macos_dir/Resources/Info.plist.template" > "$bundle/Contents/Info.plist"
plutil -lint -s "$bundle/Contents/Info.plist"

iconset="$build_dir/AppIcon.iconset"
mkdir -p "$iconset"
for size in 16 32 128 256 512; do
    sips -z $size $size "$macos_dir/Resources/AppIcon.png" --out "$iconset/icon_${size}x${size}.png" >/dev/null
    sips -z $((size * 2)) $((size * 2)) "$macos_dir/Resources/AppIcon.png" --out "$iconset/icon_${size}x${size}@2x.png" >/dev/null
done
iconutil -c icns "$iconset" -o "$bundle/Contents/Resources/AppIcon.icns"

codesign --force --sign - "$bundle"

mkdir -p "$install_dir"
[[ -e "$install_dir/$app_name.app" ]] && trash "$install_dir/$app_name.app"
mv "$bundle" "$install_dir/"
echo "Installed $install_dir/$app_name.app"
