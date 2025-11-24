# zip all directories in the current path, excluding macOS resource forks
for dir in */; do
    (cd "$dir" && zip -r "../${dir%/}.zip" . -x '._*' -x '**/._*')
done

mkdir -p "unzipped (delete me)"
for dir in */; do
    if [ "$dir" != "unzipped (delete me)/" ]; then
        mv "$dir" "unzipped (delete me)/"
    fi
done